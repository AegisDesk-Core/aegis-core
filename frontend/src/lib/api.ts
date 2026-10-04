import { ConnectionStatus, Source } from "./types";

interface RawSource {
  filename?: string;
  document?: string;
  page?: number | string;
  excerpt?: string;
  text?: string;
  score?: number;
}

export interface AskParams {
  baseUrl: string;
  token: string;
  sessionId: string;
  message: string;
  history: Array<{ role: string; content: string }>;
  demoMode?: boolean;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export async function deleteConversation(baseUrl: string, token: string, sessionId: string): Promise<boolean> {
  const cleanUrl = baseUrl.replace(/\/+$/, "");
  const response = await fetch(`${cleanUrl}/api/v1/conversations/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `DELETE failed with status ${response.status}`);
  }

  return true;
}

// Check backend health & token validation
export async function checkBackendStatus(baseUrl: string, token: string): Promise<ConnectionStatus> {
  const cleanUrl = baseUrl.replace(/\/+$/, "");
  try {
    const healthRes = await fetch(`${cleanUrl}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(3500)
    }).catch(() => null);

    if (!healthRes || !healthRes.ok) {
      return "offline";
    }

    if (!token) {
      return "sign_in_required";
    }

    const authRes = await fetch(`${cleanUrl}/api/v1/chat/start`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(3500)
    }).catch(() => null);

    if (authRes && authRes.ok) {
      return "authenticated";
    } else {
      return "invalid_token";
    }
  } catch {
    return "offline";
  }
}

// Ask question endpoint with live FastAPI request or realistic mock fallback
export async function askQuestion(params: AskParams): Promise<AskResponse> {
  const { baseUrl, token, sessionId, message, history, demoMode } = params;

  if (demoMode) {
    return generateMockResponse(message);
  }

  const cleanUrl = baseUrl.replace(/\/+$/, "");
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const res = await fetch(`${cleanUrl}/api/v1/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders
    },
    body: JSON.stringify({
      message,
      conversation_id: sessionId,
      history: history.slice(-10)
    })
  });

  if (res.status === 401) {
    throw new Error("AUTHENTICATION_FAILED");
  }

  if (!res.ok) {
    let detail = "";
    try {
      const errorBody = (await res.json()) as { detail?: string };
      detail = errorBody.detail || "";
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(`SERVER_ERROR_${res.status}${detail ? `:${detail}` : ""}`);
  }

  const data = await res.json();
  const answer = data.answer || "(No response content returned by the server.)";
  const rawSources = data.citations || data.sources || [];
  const sources: Source[] = rawSources.map((s: RawSource) => ({
    filename: s.filename || s.document || "source",
    page: s.page,
    excerpt: s.excerpt || s.text || "",
    score: s.score
  }));

  return { answer, sources };
}

// Realistic mock responses for frontend testing and demo
function generateMockResponse(query: string): Promise<AskResponse> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const q = query.toLowerCase();
      if (q.includes("pricing") || q.includes("cost")) {
        resolve({
          answer:
            "Based on the **Enterprise Services Agreement**, pricing is structured across three primary tiers:\n\n" +
            "- **Standard Tier**: $1,200/mo billed annually. Includes up to 100,000 queries and standard 99.5% uptime.\n" +
            "- **Enterprise Tier**: $3,800/mo. Dedicated vector compute, custom index sharding, and 99.99% SLA guarantee.\n" +
            "- **Volume Overages**: Charged at $0.008 per indexed document page beyond tier quota.\n\n" +
            "Discounts of 15% apply automatically for multi-year commitments.",
          sources: [
            {
              filename: "enterprise_pricing_guide_2024.pdf",
              page: 4,
              excerpt: "Section 3.2: Enterprise Tier pricing schedules, overage formulas, and guaranteed SLA billing cycles.",
              score: 0.94
            },
            {
              filename: "commercial_terms_addendum.docx",
              page: 12,
              excerpt: "Volume commitments exceeding 500k documents qualify for tiered schedule D discounts.",
              score: 0.88
            }
          ]
        });
      } else if (q.includes("summarize") || q.includes("main points")) {
        resolve({
          answer:
            "Here is an executive synthesis of the knowledge archive:\n\n" +
            "1. **Architecture Overview**: The platform implements hybrid semantic-lexical retrieval using BM25 and dense embedding rerankers.\n" +
            "2. **Data Isolation**: Strict multi-tenant isolation guarantees document encryptions per tenant UUID with isolated vector namespaces.\n" +
            "3. **Compliance & Audit**: SOC2 Type II compliance controls are enforced on all ingestion pipelines and chunking microservices.",
          sources: [
            {
              filename: "system_architecture_whitepaper.pdf",
              page: 1,
              excerpt: "Executive overview of the hybrid search pipeline and dual retrieval stages.",
              score: 0.96
            },
            {
              filename: "compliance_audit_report_q3.pdf",
              page: 7,
              excerpt: "SOC2 Type II validation parameters for data in transit and rest.",
              score: 0.91
            }
          ]
        });
      } else {
        resolve({
          answer:
            `According to the index records regarding **"${query}"**:\n\n` +
            `The connected tenant repository documents explicit operational guidelines and verified procedures. All responses are directly retrieved from the indexed knowledge base with strict citation provenance.\n\n` +
            `Key parameters have been extracted and verified against the current documents.`,
          sources: [
            {
              filename: "tenant_knowledge_base_v1.pdf",
              page: 2,
              excerpt: `Verified matching excerpt for: "${query.slice(0, 40)}..."`,
              score: 0.92
            },
            {
              filename: "service_level_agreement.pdf",
              page: 8,
              excerpt: "Standard operating procedures and resolution escalation matrices.",
              score: 0.85
            }
          ]
        });
      }
    }, 750);
  });
}

// Sample knowledge documents displayed in the sidebar
export const DEFAULT_DOCUMENTS: Array<{ id: string; filename: string; status: 'ready' | 'indexing' | 'error'; size: string }> = [
];
