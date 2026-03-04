# Reproducibility System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Tag every MLflow trace with the Claude Code environment state (git SHA, CLAUDE.md content/hash, skills hash) captured at session start, enabling compliance analysis across instruction versions.

**Architecture:** A SessionStart hook writes environment snapshots to a JSON sidecar file. The existing Stop hook wrapper reads the sidecar after trace creation and enriches the trace with tags and span attributes. Two files change, one file is created.

**Tech Stack:** Python stdlib (hashlib, subprocess, json), MLflow client API (`set_trace_tag`, `set_span_attribute` — to be verified)

---

### Task 1: Create `log_cc_environment.py` — the SessionStart hook

**Files:**
- Create: `.claude/hooks/log_cc_environment.py`
- Test: `tests/test_log_cc_environment.py`

**Step 1: Write the failing test for `snapshot_environment()`**

Create `tests/test_log_cc_environment.py`:

```python
import hashlib
import json
import os
import tempfile

from claude.hooks.log_cc_environment import snapshot_environment


def test_snapshot_with_claude_md(tmp_path):
    """snapshot_environment captures git SHA, CLAUDE.md hash+content, skills hash."""
    # Set up a fake project dir with CLAUDE.md
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Instructions\nBe helpful.")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "foo" / "SKILL.md").parent.mkdir()
    (skills_dir / "foo" / "SKILL.md").write_text("skill foo")

    result = snapshot_environment(project_dir=str(tmp_path))

    expected_md_hash = hashlib.sha256(b"# Instructions\nBe helpful.").hexdigest()
    expected_skills_hash = hashlib.sha256(b"skill foo").hexdigest()

    assert result["claude_md_hash"] == expected_md_hash
    assert result["claude_md_content"] == "# Instructions\nBe helpful."
    assert result["skills_hash"] == expected_skills_hash
    assert result["snapshot_timestamp"]  # non-empty ISO string
    # git_sha may be "none" if tmp_path isn't a repo — that's fine
    assert "git_sha" in result
    assert "git_dirty" in result


def test_snapshot_no_claude_md(tmp_path):
    """When CLAUDE.md doesn't exist, hash is 'none' and content is empty."""
    result = snapshot_environment(project_dir=str(tmp_path))
    assert result["claude_md_hash"] == "none"
    assert result["claude_md_content"] == ""


def test_snapshot_no_skills_dir(tmp_path):
    """When skills dir doesn't exist, skills_hash is 'none'."""
    result = snapshot_environment(project_dir=str(tmp_path))
    assert result["skills_hash"] == "none"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run pytest tests/test_log_cc_environment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claude.hooks'`

**Step 3: Implement `snapshot_environment()` in `log_cc_environment.py`**

Create `.claude/hooks/log_cc_environment.py`:

```python
#!/usr/bin/env python3
"""SessionStart hook: snapshot Claude Code environment for reproducibility.

Captures git SHA, CLAUDE.md hash + content, and skills directory hash.
Writes a sidecar JSON file that the Stop hook reads to enrich traces.

Zero MLflow dependency — pure stdlib + subprocess for fast startup.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def snapshot_environment(project_dir: str) -> dict:
    """Capture environment state for the given project directory.

    Returns a dict with git_sha, git_dirty, claude_md_hash,
    claude_md_content, skills_hash, and snapshot_timestamp.
    """
    git_sha, git_dirty = _git_state(project_dir)
    claude_md_hash, claude_md_content = _claude_md_state(project_dir)
    skills_hash = _skills_hash(project_dir)

    return {
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "claude_md_hash": claude_md_hash,
        "claude_md_content": claude_md_content,
        "skills_hash": skills_hash,
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _git_state(project_dir: str) -> tuple[str, str]:
    """Return (sha, dirty_flag). Both 'none' if not a git repo."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if sha.returncode != 0:
            return "none", "none"

        dirty = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=project_dir,
            capture_output=True,
            timeout=5,
        )
        return sha.stdout.strip(), str(dirty.returncode != 0).lower()
    except Exception:
        return "none", "none"


def _claude_md_state(project_dir: str) -> tuple[str, str]:
    """Return (hash, content). Hash is 'none' and content '' if missing."""
    path = os.path.join(project_dir, "CLAUDE.md")
    try:
        with open(path) as f:
            content = f.read()
        h = hashlib.sha256(content.encode()).hexdigest()
        return h, content
    except FileNotFoundError:
        return "none", ""


def _skills_hash(project_dir: str) -> str:
    """SHA-256 of sorted concatenation of all SKILL.md files. 'none' if no skills dir."""
    skills_dir = os.path.join(project_dir, "skills")
    if not os.path.isdir(skills_dir):
        return "none"

    parts = []
    for root, _dirs, files in os.walk(skills_dir):
        for fname in sorted(files):
            if fname == "SKILL.md":
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    parts.append(f.read())

    if not parts:
        return "none"

    combined = "".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()


def _write_sidecar(project_dir: str, session_id: str, env_data: dict):
    """Write environment snapshot to sidecar JSON."""
    mlflow_dir = os.path.join(project_dir, ".claude", "mlflow")
    os.makedirs(mlflow_dir, exist_ok=True)
    sidecar_path = os.path.join(mlflow_dir, f"env_{session_id}.json")

    env_data["session_id"] = session_id
    with open(sidecar_path, "w") as f:
        json.dump(env_data, f)


def main():
    hook_input = json.loads(sys.stdin.read())
    session_id = hook_input.get("session_id", "unknown")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", hook_input.get("cwd", os.getcwd()))

    env_data = snapshot_environment(project_dir)
    _write_sidecar(project_dir, session_id, env_data)

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
```

**Step 4: Fix test imports — tests need to import from hook script path**

The tests can't use `claude.hooks.log_cc_environment` as a module path since it's not a package. Update the test to use `importlib` or add the hook to `sys.path`.

Update `tests/test_log_cc_environment.py` import to:

```python
import sys
import os

# Add hooks dir to path so we can import the script directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks"))
from log_cc_environment import snapshot_environment
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run pytest tests/test_log_cc_environment.py -v`
Expected: 3 PASS

**Step 6: Write test for sidecar file writing**

Add to `tests/test_log_cc_environment.py`:

```python
from log_cc_environment import _write_sidecar


def test_write_sidecar(tmp_path):
    """_write_sidecar creates .claude/mlflow/env_{session_id}.json."""
    _write_sidecar(str(tmp_path), "sess-123", {"git_sha": "abc"})
    sidecar = tmp_path / ".claude" / "mlflow" / "env_sess-123.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["session_id"] == "sess-123"
    assert data["git_sha"] == "abc"
```

**Step 7: Run tests**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run pytest tests/test_log_cc_environment.py -v`
Expected: 4 PASS

**Step 8: Commit**

```bash
git add .claude/hooks/log_cc_environment.py tests/test_log_cc_environment.py
git commit -m "feat: add SessionStart hook for environment snapshots"
```

---

### Task 2: Extend `skip_skill_traces.py` with trace enrichment

**Files:**
- Modify: `.claude/hooks/skip_skill_traces.py`
- Test: `tests/test_skip_skill_traces.py`

**Context:** After `stop_hook_handler()` creates a trace and returns `{"continue": true}` to stdout, `skip_skill_traces.py` currently just relays that output. We need to intercept after the subprocess completes, read the sidecar, find the trace by session ID, and enrich it.

**Key challenge:** `stop_hook_handler()` doesn't return the trace ID in its stdout. We need to find the trace. Options:
- Search MLflow for the most recent trace tagged with this session's ID
- The trace has metadata `mlflow.trace.session` = session_id

**Step 1: Write failing test for `_enrich_trace_from_sidecar()`**

Create `tests/test_skip_skill_traces.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run pytest tests/test_skip_skill_traces.py -v`
Expected: FAIL — `ImportError: cannot import name '_enrich_trace_from_sidecar'`

**Step 3: Implement `_enrich_trace_from_sidecar()` and update `main()`**

Add to `.claude/hooks/skip_skill_traces.py` (after line 70, before `main()`):

```python
def _enrich_trace_from_sidecar(project_dir, session_id):
    """Read and delete the environment sidecar file. Returns env data dict or None."""
    sidecar_path = os.path.join(project_dir, ".claude", "mlflow", f"env_{session_id}.json")
    try:
        with open(sidecar_path) as f:
            env_data = json.load(f)
        os.remove(sidecar_path)
        return env_data
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _apply_env_to_trace(session_id, env_data):
    """Find the trace for this session and apply environment tags + attributes."""
    try:
        import mlflow
        from mlflow import MlflowClient

        client = MlflowClient()

        # Find the most recent trace for this session
        traces = mlflow.search_traces(
            filter_string=f"metadata.`mlflow.trace.session` = '{session_id}'",
            order_by=["timestamp_ms DESC"],
            max_results=1,
        )
        if traces.empty:
            return

        trace_id = traces.iloc[0]["trace_id"]

        # Set queryable trace tags
        client.set_trace_tag(trace_id, "cc_env.git_sha", env_data.get("git_sha", "none"))
        client.set_trace_tag(trace_id, "cc_env.claude_md_hash", env_data.get("claude_md_hash", "none"))

        # Find root span and set rich attributes
        trace = mlflow.get_trace(trace_id)
        if trace and trace.data.spans:
            root_span = trace.data.spans[0]
            for key in ("git_sha", "git_dirty", "claude_md_hash", "claude_md_content", "skills_hash", "snapshot_timestamp"):
                value = env_data.get(key, "")
                client.set_span_attribute(
                    trace_id, root_span.span_id, f"cc_env.{key}", value
                )
    except Exception:
        pass  # Never let enrichment failures break the hook
```

Then update `main()` in `skip_skill_traces.py` to call enrichment after the subprocess:

Replace the current `main()` (lines 73-96) with:

```python
def main():
    hook_input = sys.stdin.read()
    data = json.loads(hook_input)

    if _should_skip(data):
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    # Delegate to the real hook command (everything after --)
    separator = sys.argv.index("--") if "--" in sys.argv else 0
    real_cmd = sys.argv[separator + 1:]
    if not real_cmd:
        print(json.dumps({"continue": True}))
        return

    result = subprocess.run(real_cmd, input=hook_input, capture_output=True, text=True)

    # Enrich trace with environment snapshot (best-effort, never blocks)
    session_id = data.get("session_id")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", ""))
    if session_id and project_dir:
        env_data = _enrich_trace_from_sidecar(project_dir, session_id)
        if env_data:
            _apply_env_to_trace(session_id, env_data)

    sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.exit(result.returncode)
```

**Step 4: Run tests**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run pytest tests/test_skip_skill_traces.py tests/test_log_cc_environment.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add .claude/hooks/skip_skill_traces.py tests/test_skip_skill_traces.py
git commit -m "feat: enrich MLflow traces with environment snapshot from sidecar"
```

---

### Task 3: Update `.claude/settings.json` to register SessionStart hook

**Files:**
- Modify: `.claude/settings.json`

**Step 1: Add SessionStart hook**

Update `.claude/settings.json` from:

```json
{
  "hooks": {
    "Stop": [...]
  },
  "environment": {
    "MLFLOW_CLAUDE_TRACING_ENABLED": "true"
  }
}
```

To:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run python \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/log_cc_environment.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run python \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/skip_skill_traces.py -- uv run python -c \"from mlflow.claude_code.hooks import stop_hook_handler; stop_hook_handler()\""
          }
        ]
      }
    ]
  },
  "environment": {
    "MLFLOW_CLAUDE_TRACING_ENABLED": "true"
  }
}
```

**Step 2: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: register SessionStart hook for environment snapshots"
```

---

### Task 4: Verify MLflow API compatibility

**Files:** None (research task)

**Step 1: Verify `set_trace_tag` exists**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run python -c "from mlflow import MlflowClient; c = MlflowClient(); print(hasattr(c, 'set_trace_tag'))"`
Expected: `True`

**Step 2: Verify `set_span_attribute` exists**

Run: `cd /Users/forrest.murray/Documents/mlfts && uv run python -c "from mlflow import MlflowClient; c = MlflowClient(); print(hasattr(c, 'set_span_attribute'))"`

If `set_span_attribute` doesn't exist, check for alternatives:
Run: `cd /Users/forrest.murray/Documents/mlfts && uv run python -c "from mlflow import MlflowClient; c = MlflowClient(); print([m for m in dir(c) if 'span' in m.lower() or 'attribute' in m.lower()])"`

**Step 3: Adapt `_apply_env_to_trace()` if API differs**

If `set_span_attribute` is not available, fall back to storing all data as trace tags (with truncation for long values like claude_md_content) or use `log_param` / `log_artifact` on the associated run.

---

### Task 5: Manual end-to-end smoke test

**Step 1: Start a new Claude Code session in this project**

The SessionStart hook should fire. Check that a sidecar file was created:
```bash
ls .claude/mlflow/env_*.json
cat .claude/mlflow/env_*.json | python -m json.tool
```

**Step 2: End the session (or let it stop naturally)**

The Stop hook should fire, create a trace, and enrich it.

**Step 3: Verify trace has environment tags**

```python
import mlflow
traces = mlflow.search_traces(max_results=1, order_by=["timestamp_ms DESC"])
print(traces[["trace_id", "tags"]].to_string())
# Should see cc_env.git_sha and cc_env.claude_md_hash in tags
```

**Step 4: Verify sidecar was cleaned up**

```bash
ls .claude/mlflow/env_*.json  # Should be empty / no match
```

**Step 5: Commit any fixes from smoke test**

```bash
git add -u
git commit -m "fix: adjustments from smoke test"
```
