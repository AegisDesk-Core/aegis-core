import hashlib
import json
import math
import re
from os import environ
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import get_env
from app.graph.state import SupportState

try:
    from langchain_mistralai import MistralAIEmbeddings
except Exception: 
    MistralAIEmbeddings = None


class LocalHashEmbeddings(Embeddings):
    """Deterministic local embeddings for offline indexing and retrieval."""

    size = 384

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.size
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def _get_embeddings():
    # Prefer the local/offline fallback by default. Remote embedding providers may
    # trigger external model downloads and auth warnings unless a real token is
    # configured and intentionally enabled. Keep the app deterministic in local
    # environments without requiring Hugging Face access.
    provider = (get_env("EMBEDDING_PROVIDER") or "local").strip().lower()

    if provider == "mistral":
        api_key = get_env("MISTRAL_API_KEY")
        if api_key:
            environ["MISTRAL_API_KEY"] = api_key
        if MistralAIEmbeddings is not None:
            try:
                return MistralAIEmbeddings(model="mistral-embed")
            except Exception:
                pass

    return LocalHashEmbeddings()


DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
VECTORSTORE_DIR = Path(__file__).resolve().parents[2] / "data" / "vectorstore"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100


def _pdf_tenant_id(pdf_path: Path) -> str:
    """Use tenant-123__file.pdf for explicit tenancy; default local PDFs to demo tenant."""
    prefix = pdf_path.stem.split("__", 1)[0]
    return prefix if prefix.startswith("tenant-") else "tenant-123"


def _file_fingerprint(pdf_path: Path) -> str:
    digest = hashlib.sha256()
    with pdf_path.open("rb") as document:
        for block in iter(lambda: document.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _embedding_signature() -> str:
    provider = (get_env("EMBEDDING_PROVIDER") or "local").strip().lower()
    model = "mistral-embed" if provider == "mistral" else "local-hash-384"
    return f"{provider}:{model}"


def _load_pdf_documents(pdf_path: Path, tenant_id: str) -> list[Document]:
    reader = PdfReader(str(pdf_path))
    return [
        Document(
            page_content=page.extract_text() or "",
            metadata={
                "source": pdf_path.name,
                "page": page_number,
                "tenant_id": tenant_id,
            },
        )
        for page_number, page in enumerate(reader.pages, start=1)
        if page.extract_text()
    ]


def _build_or_load_store(pdf_path: Path, embeddings, splitter):
    tenant_id = _pdf_tenant_id(pdf_path)
    store_path = VECTORSTORE_DIR / f"{tenant_id}__{pdf_path.stem}"
    manifest_path = store_path / "manifest.json"
    manifest = {
        "source": pdf_path.name,
        "fingerprint": _file_fingerprint(pdf_path),
        "tenant_id": tenant_id,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding": _embedding_signature(),
    }

    if manifest_path.exists() and (store_path / "index.faiss").exists():
        try:
            cached_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if cached_manifest == manifest:
                return FAISS.load_local(
                    str(store_path),
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
        except (OSError, ValueError, TypeError):
            pass

    documents = _load_pdf_documents(pdf_path, tenant_id)
    chunks = splitter.split_documents(documents)
    if not chunks:
        return None

    store_path.mkdir(parents=True, exist_ok=True)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(str(store_path))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return vectorstore


def _build_vectorstores():
    embeddings = _get_embeddings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    vectorstores = {}

    for pdf_path in sorted(DOCUMENTS_DIR.glob("*.pdf")):
        vectorstore = _build_or_load_store(pdf_path, embeddings, splitter)
        if vectorstore is not None:
            vectorstores.setdefault(_pdf_tenant_id(pdf_path), []).append(vectorstore)

    return vectorstores


VECTORSTORES = _build_vectorstores()


def retrieve(state: SupportState):
    tenant_id = state.get("tenant_id") or "unknown"
    query = state.get("rewritten_query") or state.get("query") or ""
    stores = VECTORSTORES.get(tenant_id, [])

    if not stores:
        state["retrieved_docs"] = []
        return {"retrieved_docs": []}

    results = []
    for store in stores:
        results.extend(store.similarity_search_with_score(query, k=5))
    results.sort(key=lambda item: item[1])

    retrieved = [
        {
            "content": doc.page_content,
            "metadata": {
                "source": doc.metadata.get("source", "policy"),
                "page": doc.metadata.get("page", 1),
                "tenant_id": doc.metadata.get("tenant_id", tenant_id),
            },
            # FAISS returns squared L2 distance; normalized vectors map it to
            # cosine similarity with 1 - distance / 2.
            "score": round(max(0.0, 1.0 - (float(distance) / 2.0)), 4),
        }
        for doc, distance in results[:5]
    ]

    state["retrieved_docs"] = retrieved
    return {"retrieved_docs": retrieved}