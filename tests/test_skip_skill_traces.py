import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks"))
from skip_skill_traces import _enrich_trace_from_sidecar


def test_enrich_reads_sidecar_and_deletes(tmp_path):
    """_enrich_trace_from_sidecar reads env data and removes the sidecar file."""
    sidecar_dir = tmp_path / ".claude" / "mlflow"
    sidecar_dir.mkdir(parents=True)
    sidecar = sidecar_dir / "env_sess-42.json"
    sidecar.write_text(json.dumps({
        "session_id": "sess-42",
        "git_sha": "abc123",
        "git_dirty": "false",
        "claude_md_hash": "deadbeef",
        "claude_md_content": "# Rules",
        "skills_hash": "cafebabe",
        "snapshot_timestamp": "2026-03-03T10:00:00+00:00",
    }))

    env_data = _enrich_trace_from_sidecar(str(tmp_path), "sess-42")

    assert env_data is not None
    assert env_data["git_sha"] == "abc123"
    assert env_data["claude_md_content"] == "# Rules"
    assert not sidecar.exists()  # cleaned up


def test_enrich_missing_sidecar(tmp_path):
    """Returns None when no sidecar exists."""
    result = _enrich_trace_from_sidecar(str(tmp_path), "no-such-session")
    assert result is None
