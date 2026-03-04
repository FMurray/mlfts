import hashlib
import json
import os
import sys

# Add hooks dir to path so we can import the script directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks"))
from log_cc_environment import snapshot_environment, _write_sidecar


def test_snapshot_with_claude_md(tmp_path):
    """snapshot_environment captures git SHA, CLAUDE.md hash+content, skills hash."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Instructions\nBe helpful.")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "foo").mkdir()
    (skills_dir / "foo" / "SKILL.md").write_text("skill foo")

    result = snapshot_environment(project_dir=str(tmp_path))

    expected_md_hash = hashlib.sha256(b"# Instructions\nBe helpful.").hexdigest()
    # Skills hash now includes relpath and uses \0 delimiter
    expected_skills_input = "foo/SKILL.md\nskill foo"
    expected_skills_hash = hashlib.sha256(expected_skills_input.encode("utf-8")).hexdigest()

    assert result["claude_md_hash"] == expected_md_hash
    assert result["claude_md_content"] == "# Instructions\nBe helpful."
    assert result["skills_hash"] == expected_skills_hash
    assert result["snapshot_timestamp"]
    assert "git_sha" in result
    assert "git_dirty" in result
    # prompt_name/prompt_version may be None if MLflow not configured
    assert "prompt_name" in result
    assert "prompt_version" in result


def test_snapshot_no_claude_md(tmp_path):
    """When CLAUDE.md doesn't exist, hash is 'none' and content is empty."""
    result = snapshot_environment(project_dir=str(tmp_path))
    assert result["claude_md_hash"] == "none"
    assert result["claude_md_content"] == ""
    assert result["prompt_name"] is None
    assert result["prompt_version"] is None


def test_snapshot_no_skills_dir(tmp_path):
    """When skills dir doesn't exist, skills_hash is 'none'."""
    result = snapshot_environment(project_dir=str(tmp_path))
    assert result["skills_hash"] == "none"


def test_skills_hash_deterministic_with_multiple_skills(tmp_path):
    """Skills hash is deterministic regardless of os.walk order."""
    skills_dir = tmp_path / "skills"
    (skills_dir / "beta").mkdir(parents=True)
    (skills_dir / "alpha").mkdir(parents=True)
    (skills_dir / "beta" / "SKILL.md").write_text("skill beta")
    (skills_dir / "alpha" / "SKILL.md").write_text("skill alpha")

    result = snapshot_environment(project_dir=str(tmp_path))

    # Should always sort by relpath: alpha/SKILL.md before beta/SKILL.md
    expected = "alpha/SKILL.md\nskill alpha\0beta/SKILL.md\nskill beta"
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    assert result["skills_hash"] == expected_hash


def test_skills_hash_empty_dir(tmp_path):
    """Skills dir exists but has no SKILL.md files."""
    (tmp_path / "skills").mkdir()
    result = snapshot_environment(project_dir=str(tmp_path))
    assert result["skills_hash"] == "none"


def test_write_sidecar(tmp_path):
    """_write_sidecar creates .claude/mlflow/env_{session_id}.json."""
    _write_sidecar(str(tmp_path), "sess-123", {"git_sha": "abc"})
    sidecar = tmp_path / ".claude" / "mlflow" / "env_sess-123.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["session_id"] == "sess-123"
    assert data["git_sha"] == "abc"
