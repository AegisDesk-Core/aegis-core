import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from time import monotonic
from typing import Any


SAFE_FIELDS = {
    "request_id",
    "tenant_id",
    "user_id",
    "conversation_id",
    "intent",
    "retrieval_count",
    "evidence_score",
    "answer_latency_ms",
    "llm_latency_ms",
    "escalated",
    "error_type",
    "status_code",
    "method",
    "path",
    "elapsed_ms",
    "threshold_ms",
    "chunk_count",
    "escalation_rate",
    "sample_count",
    "vector_search_ms",
}

SLOW_DOCUMENT_PROCESSING_MS = 5_000
SLOW_VECTOR_SEARCH_MS = 500
ESCALATION_RATE_MIN_SAMPLES = 10
ESCALATION_RATE_THRESHOLD = 0.5
ESCALATION_RATE_WINDOW = 1_000
ESCALATION_ALERT_COOLDOWN_SECONDS = 300


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": record.msg,
        }
        event.update({
            key: value
            for key, value in getattr(record, "fields", {}).items()
            if key in SAFE_FIELDS
        })
        return json.dumps(event, separators=(",", ":"), ensure_ascii=True)


logger = logging.getLogger("app.telemetry")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)

_escalation_outcomes: deque[bool] = deque(maxlen=ESCALATION_RATE_WINDOW)
_escalation_lock = threading.Lock()
_last_escalation_alert = 0.0


def emit_event(level: int, event: str, **fields: Any) -> None:
    safe_fields = {key: value for key, value in fields.items() if key in SAFE_FIELDS}
    logger.log(level, event, extra={"fields": safe_fields})


def record_escalation_outcome(escalated: bool) -> None:
    global _last_escalation_alert

    now = monotonic()
    with _escalation_lock:
        _escalation_outcomes.append(escalated)
        sample_count = len(_escalation_outcomes)
        escalation_rate = sum(_escalation_outcomes) / sample_count
        should_alert = (
            sample_count >= ESCALATION_RATE_MIN_SAMPLES
            and escalation_rate >= ESCALATION_RATE_THRESHOLD
            and now - _last_escalation_alert >= ESCALATION_ALERT_COOLDOWN_SECONDS
        )
        if should_alert:
            _last_escalation_alert = now

    if should_alert:
        emit_event(
            logging.WARNING,
            "high_escalation_rate",
            escalation_rate=round(escalation_rate, 4),
            sample_count=sample_count,
        )


def escalation_monitor_state() -> tuple[int, float]:
    with _escalation_lock:
        sample_count = len(_escalation_outcomes)
        rate = sum(_escalation_outcomes) / sample_count if sample_count else 0.0
        return sample_count, rate


def slow_document_processing_threshold_ms() -> int:
    return int(os.getenv("SLOW_DOCUMENT_PROCESSING_MS", SLOW_DOCUMENT_PROCESSING_MS))


def slow_vector_search_threshold_ms() -> int:
    return int(os.getenv("SLOW_VECTOR_SEARCH_MS", SLOW_VECTOR_SEARCH_MS))
