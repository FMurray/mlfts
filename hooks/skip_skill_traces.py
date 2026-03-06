#!/usr/bin/env python3
"""Pre-filter for the MLflow Stop hook: skip tracing for this plugins' skills.

This script is a transparent proxy. It reads the Claude Code hook input,
checks if the current turn is an invocation of an MLflow skill that would
pollute the session with administrative traces, and either:
  - Short-circuits with a success response (skip trace)
  - Delegates to the real hook command unchanged (normal turn)

It has ZERO dependency on MLflow internals — it only reads a JSONL file
and checks for a string pattern. The real hook command is passed as argv.

Usage in .claude/settings.json (use $CLAUDE_PROJECT_DIR for portable paths):
  "command": "uv run python \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/skip_skill_traces.py -- uv run python -c \"from mlflow.claude_code.hooks import stop_hook_handler; stop_hook_handler()\""
"""

import json
import os
import subprocess
import sys

# Skills whose invocations should NOT produce session traces.
# These interact with the tracing server and would pollute the session.
SKIP_SKILLS = {
    "feedback-trace",
    "tag-trace",
}


def _should_skip(data):
    """Check if this Stop event should skip tracing."""
    # Never interfere when stop_hook_active is set — this means Claude is
    # continuing from a previous stop hook and we must let it resolve.
    if data.get("stop_hook_active"):
        return False

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return False

    try:
        with open(transcript_path) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except Exception:
        return False

    for entry in reversed(entries):
        if entry.get("type") != "user" or entry.get("toolUseResult"):
            continue
        content = entry.get("message", {}).get("content", "")
        if isinstance(content, list):
            text = "\n".join(
                p.get("text", "")
                for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        else:
            text = str(content)

        text = text.lstrip()
        if not text.startswith("Base directory for this skill:"):
            return False

        # Extract skill name from the path on the first line:
        # "Base directory for this skill: /some/path/to/feedback-trace"
        first_line = text.split("\n", 1)[0]
        skill_path = first_line.split(":", 1)[1].strip()
        skill_name = os.path.basename(skill_path)
        return skill_name in SKIP_SKILLS

    return False


def _enrich_trace_from_sidecar(project_dir, session_id):
    """Read and delete the environment sidecar file. Returns env data dict or None."""
    sidecar_path = os.path.join(
        project_dir, ".claude", "mlflow", f"env_{session_id}.json"
    )
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
    """Find the trace for this session and apply environment tags + prompt linkage.

    Sets trace tags for short metadata (git SHA, hashes).
    Creates a companion 'env_snapshot' trace with auto-linked prompt
    (load_prompt inside a traced context triggers automatic linking).
    """
    try:
        import mlflow
        from mlflow import MlflowClient

        client = MlflowClient()

        traces = mlflow.search_traces(
            filter_string=f"metadata.mlflow.trace.session = '{session_id}'",
            order_by=["timestamp_ms DESC"],
            max_results=1,
        )
        if traces.empty:
            return

        trace_id = traces.iloc[0]["trace_id"]

        # Short metadata as trace tags on the session trace
        for key in (
            "git_sha",
            "git_dirty",
            "claude_md_hash",
            "skills_hash",
            "snapshot_timestamp",
        ):
            value = env_data.get(key, "none")
            client.set_trace_tag(trace_id, f"cc_env.{key}", str(value))

        prompt_name = env_data.get("prompt_name")
        prompt_version = env_data.get("prompt_version")
        if prompt_name and prompt_version:
            prompt_uri = f"prompts:/{prompt_name}/{prompt_version}"
            client.set_trace_tag(trace_id, "cc_env.prompt_uri", prompt_uri)

            # Create a companion trace that auto-links the prompt via load_prompt().
            # This is needed because the session trace is created by stop_hook_handler
            # in a subprocess, and we can't inject load_prompt into its trace context.
            _create_env_snapshot_trace(
                client, session_id, trace_id, prompt_uri, env_data
            )
    except Exception:
        pass  # Never let enrichment failures break the hook


def _create_env_snapshot_trace(
    client, session_id, session_trace_id, prompt_uri, env_data
):
    """Create a lightweight companion trace with auto-linked prompt.

    Calling load_prompt() inside mlflow.start_span() triggers automatic
    prompt-to-trace linking that's visible in the Databricks UI.
    """
    try:
        import mlflow

        @mlflow.trace(name="env_snapshot", span_type="UNKNOWN")
        def _snapshot():
            # load_prompt inside a traced context triggers auto-linking
            mlflow.genai.load_prompt(prompt_uri)
            return {
                "session_id": session_id,
                "session_trace_id": session_trace_id,
                "git_sha": env_data.get("git_sha", "none"),
                "claude_md_hash": env_data.get("claude_md_hash", "none"),
            }

        _snapshot()

        # Tag the companion trace so it can be found alongside the session trace
        companion_traces = mlflow.search_traces(
            order_by=["timestamp_ms DESC"],
            max_results=1,
        )
        if not companion_traces.empty:
            companion_id = companion_traces.iloc[0]["trace_id"]
            if companion_id != session_trace_id:
                client.set_trace_tag(companion_id, "cc_env.type", "env_snapshot")
                client.set_trace_tag(companion_id, "cc_env.session_id", session_id)
                client.set_trace_tag(
                    companion_id, "cc_env.session_trace_id", session_trace_id
                )
                # Also cross-reference from session trace
                client.set_trace_tag(
                    session_trace_id, "cc_env.snapshot_trace_id", companion_id
                )
    except Exception:
        pass


def main():
    hook_input = sys.stdin.read()
    data = json.loads(hook_input)

    if _should_skip(data):
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    # Delegate to the real hook command (everything after --)
    separator = sys.argv.index("--") if "--" in sys.argv else 0
    real_cmd = sys.argv[separator + 1 :]
    if not real_cmd:
        print(json.dumps({"continue": True}))
        return

    result = subprocess.run(real_cmd, input=hook_input, capture_output=True, text=True)

    # Enrich trace with environment snapshot (best-effort, never blocks)
    try:
        session_id = data.get("session_id")
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", ""))
        if session_id and project_dir:
            env_data = _enrich_trace_from_sidecar(project_dir, session_id)
            if env_data:
                _apply_env_to_trace(session_id, env_data)
    except Exception:
        pass

    sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
