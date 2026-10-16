from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app import api
from app.main import app


client = TestClient(app)


def test_all_tenant_sensitive_routes_reject_missing_authentication():
    document_id = "00000000-0000-0000-0000-000000000001"
    requests = [
        client.get("/api/v1/chat/start"),
        client.post("/api/v1/ask", json={"message": "hello", "conversation_id": "conversation"}),
        client.post(
            "/api/v1/documents",
            files={"file": ("policy.pdf", b"%PDF-1.7", "application/pdf")},
        ),
        client.get("/api/v1/documents"),
        client.get(f"/api/v1/documents/{document_id}"),
        client.delete(f"/api/v1/documents/{document_id}"),
        client.post(f"/api/v1/documents/{document_id}/reindex"),
        client.get("/api/v1/conversations"),
        client.get("/api/v1/conversations/conversation"),
        client.get("/api/v1/conversations/conversation/messages"),
        client.delete("/api/v1/conversations/conversation"),
        client.post(
            "/api/v1/feedback",
            json={
                "conversation_id": document_id,
                "message_id": document_id,
                "rating": 5,
            },
        ),
    ]

    assert [response.status_code for response in requests] == [401] * len(requests)


def test_admin_metrics_reject_missing_authentication():
    response = client.get("/api/v1/admin/metrics")

    assert response.status_code == 401


def test_tenant_token_cannot_access_admin_metrics(monkeypatch):
    monkeypatch.setenv("API_ADMIN_TOKEN", "separate-admin-secret")
    response = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": "Bearer demo-tenant"},
    )

    assert response.status_code == 403


def test_admin_credential_cannot_be_reused_as_a_tenant_token(monkeypatch):
    monkeypatch.setenv("API_ADMIN_TOKEN", "demo-tenant")
    response = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": "Bearer demo-tenant"},
    )

    assert response.status_code == 503


def test_health_endpoint_remains_public():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_document_upload_returns_dashboard_friendly_job_response(monkeypatch):
    document_id = uuid4()
    scheduled_jobs = []
    saved_tenants = []

    def save_upload(**kwargs):
        saved_tenants.append(kwargs["tenant_id"])
        return (
            (document_id, "returns-policy.pdf", "pending", None, None),
            Path("tenant-document.pdf"),
            False,
        )

    monkeypatch.setattr(
        api,
        "save_document_upload",
        save_upload,
    )
    monkeypatch.setattr(
        api,
        "process_document_job",
        lambda *args: scheduled_jobs.append(args),
    )

    response = client.post(
        "/api/v1/documents",
        headers={"Authorization": "Bearer demo-tenant"},
        data={"tenant_id": "tenant-attacker"},
        files={"file": ("returns-policy.pdf", b"%PDF-1.7 content", "application/pdf")},
    )

    assert response.status_code == 202
    assert response.json() == {
        "document_id": str(document_id),
        "filename": "returns-policy.pdf",
        "status": "pending",
    }
    assert scheduled_jobs == [
        (Path("tenant-document.pdf"), "tenant-123", document_id)
    ]
    assert saved_tenants == ["tenant-123"]
