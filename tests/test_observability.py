import json
import logging
from collections import deque

from fastapi.testclient import TestClient

from app import observability
from app.main import app


def test_structured_events_include_safe_fields_and_exclude_content(caplog):
    caplog.set_level(logging.INFO, logger="app.telemetry")
    observability.emit_event(
        logging.INFO,
        "http_request_completed",
        request_id="req-123",
        tenant_id="tenant-123",
        user_id="user-123",
        conversation_id="conv-123",
        intent="refund",
        retrieval_count=2,
        evidence_score=0.8,
        answer_latency_ms=120.5,
        llm_latency_ms=75.2,
        escalated=False,
        query="private customer message",
        api_key="secret-key",
        password="secret-password",
        document_content="confidential document text",
    )

    event = json.loads(observability._JsonFormatter().format(caplog.records[-1]))

    assert event["event"] == "http_request_completed"
    assert event["request_id"] == "req-123"
    assert event["tenant_id"] == "tenant-123"
    assert event["user_id"] == "user-123"
    assert event["conversation_id"] == "conv-123"
    assert event["retrieval_count"] == 2
    assert "private customer message" not in json.dumps(event)
    assert "secret-key" not in json.dumps(event)
    assert "secret-password" not in json.dumps(event)
    assert "confidential document text" not in json.dumps(event)


def test_high_escalation_rate_emits_alert_after_minimum_sample(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app.telemetry")
    monkeypatch.setattr(
        observability,
        "_escalation_outcomes",
        deque(maxlen=observability.ESCALATION_RATE_WINDOW),
    )
    monkeypatch.setattr(observability, "_last_escalation_alert", 0.0)

    for _ in range(observability.ESCALATION_RATE_MIN_SAMPLES):
        observability.record_escalation_outcome(True)

    events = [
        json.loads(observability._JsonFormatter().format(record))
        for record in caplog.records
    ]
    sample_count, escalation_rate = observability.escalation_monitor_state()

    assert sample_count == observability.ESCALATION_RATE_MIN_SAMPLES
    assert escalation_rate == 1.0
    assert events[-1]["event"] == "high_escalation_rate"
    assert events[-1]["sample_count"] == observability.ESCALATION_RATE_MIN_SAMPLES
    assert events[-1]["escalation_rate"] == 1.0


def test_unauthorized_request_is_correlated_and_does_not_log_bearer_token(caplog):
    caplog.set_level(logging.WARNING, logger="app.telemetry")
    bearer_token = "sensitive-invalid-token"
    response = TestClient(app).get(
        "/api/v1/chat/start",
        headers={"Authorization": f"Bearer {bearer_token}"},
    )

    event = json.loads(observability._JsonFormatter().format(caplog.records[-1]))

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == event["request_id"]
    assert event["status_code"] == 401
    assert event["error_type"] == "AuthenticationError"
    assert event["path"] == "/api/v1/chat/start"
    assert bearer_token not in json.dumps(event)
