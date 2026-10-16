from contextlib import nullcontext
from uuid import uuid4

from app.services import document_service


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, document_id):
        self.document_id = document_id
        self.statements = []

    def execute(self, query, parameters):
        self.statements.append((query, parameters))
        if "status = 'processing'" in query:
            return FakeCursor((self.document_id,))
        return FakeCursor(None)


def test_index_job_claims_pending_document_before_indexing(monkeypatch, tmp_path):
    document_id = uuid4()
    connection = FakeConnection(document_id)
    indexed = []
    monkeypatch.setattr(document_service, "get_connection", lambda: nullcontext(connection))

    def index_pdf(path, *, tenant_id, document_id):
        assert "status = 'processing'" in connection.statements[0][0]
        indexed.append((path, tenant_id, document_id))
        return 2

    monkeypatch.setattr(document_service, "index_document", index_pdf)
    monkeypatch.setattr(document_service, "sleep", lambda _seconds: None)

    document_service.process_document_job(tmp_path / "document.pdf", "tenant-123", document_id)

    assert indexed == [(tmp_path / "document.pdf", "tenant-123", document_id)]
    assert len(connection.statements) == 1


def test_index_job_marks_document_failed_when_indexing_fails(monkeypatch, tmp_path):
    document_id = uuid4()
    connection = FakeConnection(document_id)
    events = []
    monkeypatch.setattr(document_service, "get_connection", lambda: nullcontext(connection))
    def fail_index(*_args, **_kwargs):
        raise ValueError("invalid PDF")

    monkeypatch.setattr(document_service, "index_document", fail_index)
    monkeypatch.setattr(document_service, "emit_event", lambda *args, **kwargs: events.append((args, kwargs)))
    monkeypatch.setattr(document_service, "sleep", lambda _seconds: None)

    document_service.process_document_job(
        tmp_path / "empty.pdf",
        "tenant-123",
        document_id,
        max_attempts=2,
    )

    assert any("status = 'failed'" in query for query, _ in connection.statements)
    assert events


def test_index_job_does_not_start_if_pending_document_was_deleted(monkeypatch, tmp_path):
    document_id = uuid4()
    connection = FakeConnection(document_id)
    connection.execute = lambda query, parameters: (
        connection.statements.append((query, parameters)) or FakeCursor(None)
    )
    indexed = []
    monkeypatch.setattr(document_service, "get_connection", lambda: nullcontext(connection))
    monkeypatch.setattr(
        document_service,
        "index_document",
        lambda *args, **kwargs: indexed.append((args, kwargs)),
    )

    document_service.process_document_job(tmp_path / "deleted.pdf", "tenant-123", document_id)

    assert not indexed
    assert len(connection.statements) == 1


def test_upload_validation_requires_pdf_signature_and_suffix():
    safe_filename, content_hash = document_service.validate_document_upload(
        r"C:\customer\policy.pdf",
        b"%PDF-1.7 sample",
    )

    assert safe_filename == "policy.pdf"
    assert content_hash


def test_upload_validation_rejects_non_pdf_and_oversized_content():
    try:
        document_service.validate_document_upload("policy.txt", b"not a PDF")
    except document_service.DocumentUploadError as error:
        assert error.status_code == 415
    else:
        raise AssertionError("Non-PDF uploads must be rejected.")

    try:
        document_service.validate_document_upload(
            "policy.pdf",
            b"%PDF-" + b"x" * document_service.MAX_DOCUMENT_BYTES,
        )
    except document_service.DocumentUploadError as error:
        assert error.status_code == 413
    else:
        raise AssertionError("Oversized uploads must be rejected.")
