import json

from mcp_server import auditlog


def test_append_creates_file_and_returns_record(tmp_path):
    path = tmp_path / "sub" / "audit.log"
    rec = auditlog.append_event(path, "quote", "800 x BRG-6204 quoted")
    assert rec["event_type"] == "quote"
    assert rec["details"] == "800 x BRG-6204 quoted"
    assert rec["timestamp"].endswith("+00:00")
    assert json.loads(path.read_text().splitlines()[0]) == rec


def test_append_is_append_only(tmp_path):
    path = tmp_path / "audit.log"
    auditlog.append_event(path, "a", "one")
    auditlog.append_event(path, "b", "two")
    lines = path.read_text().splitlines()
    assert [json.loads(line)["event_type"] for line in lines] == ["a", "b"]


def test_read_text_empty_when_missing(tmp_path):
    assert auditlog.read_text(tmp_path / "none.log") == ""
