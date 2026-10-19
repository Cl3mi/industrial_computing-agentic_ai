"""Append-only JSON-lines audit log."""

import json
from datetime import datetime, timezone
from pathlib import Path


def append_event(log_path, event_type: str, details: str) -> dict:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_text(log_path) -> str:
    path = Path(log_path)
    return path.read_text(encoding="utf-8") if path.exists() else ""
