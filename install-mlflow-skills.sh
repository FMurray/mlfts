#!/usr/bin/env bash
set -euo pipefail

# MLflow Trace Tag & Feedback Skills for Claude Code
# Usage: curl -fsSL <gist-raw-url> | bash
#
# Prerequisites: mlflow autolog already configured (mlflow autolog claude)

ROOT="${PWD}"
SETTINGS="${ROOT}/.claude/settings.json"
LOCAL_SETTINGS="${ROOT}/.claude/settings.local.json"

# ── Detect available runners ────────────────────────────────

HAS_UV=false
HAS_PYTHON=false
command -v uv &>/dev/null && HAS_UV=true
command -v python &>/dev/null && HAS_PYTHON=true
command -v python3 &>/dev/null && HAS_PYTHON=true

if ! $HAS_UV && ! $HAS_PYTHON; then
  echo "Error: Neither uv nor python found. Install one first." >&2
  exit 1
fi

# ── Prompt helper (reads from /dev/tty so curl|bash works) ──

prompt() {
  local msg="$1" default="$2" var=""
  if [ -n "$default" ]; then
    printf "%s [%s]: " "$msg" "$default" >/dev/tty
  else
    printf "%s: " "$msg" >/dev/tty
  fi
  read -r var </dev/tty || true
  echo "${var:-$default}"
}

echo "" >/dev/tty
echo "=== MLflow Trace Skills Installer ===" >/dev/tty
echo "" >/dev/tty

# ── Choose runner ───────────────────────────────────────────

if $HAS_UV && $HAS_PYTHON; then
  echo "Detected both uv and python." >/dev/tty
  echo "  1) uv run python" >/dev/tty
  echo "  2) python" >/dev/tty
  printf "Which runner? [1]: " >/dev/tty
  read -r choice </dev/tty || true
  if [ "${choice:-1}" = "2" ]; then
    RUNNER="python"
  else
    RUNNER="uv run python"
  fi
elif $HAS_UV; then
  RUNNER="uv run python"
else
  RUNNER="python"
fi

echo "Using: ${RUNNER}" >/dev/tty

# ── Ensure mlflow is installed ──────────────────────────────

if ! $RUNNER -c "import mlflow" &>/dev/null 2>&1; then
  echo "mlflow not found. Installing..." >/dev/tty
  if [ "$RUNNER" = "uv run python" ]; then
    uv pip install mlflow
  else
    pip install mlflow
  fi
fi

# ── Ensure MLFLOW_CLAUDE_TRACING_ENABLED in settings.json ───
# setup_mlflow() is a no-op without this in settings.json → "environment"

mkdir -p "${ROOT}/.claude"

$RUNNER -c "
import json
from pathlib import Path

path = Path('$SETTINGS')
config = {}
if path.exists():
    with open(path) as f:
        config = json.load(f)

env = config.setdefault('environment', {})
if env.get('MLFLOW_CLAUDE_TRACING_ENABLED') != 'true':
    env['MLFLOW_CLAUDE_TRACING_ENABLED'] = 'true'
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
    print('Set MLFLOW_CLAUDE_TRACING_ENABLED=true in settings.json')
else:
    print('MLFLOW_CLAUDE_TRACING_ENABLED already set')
" 2>&1 | while read -r line; do echo "  $line" >/dev/tty; done

# ── Prompt for Databricks profile and experiment name ───────

echo "" >/dev/tty
echo "MLflow tracking URI uses your Databricks CLI profile." >/dev/tty
echo "Format: databricks://<profile-name>" >/dev/tty
echo "Leave blank to use Databricks unified auth instead." >/dev/tty
echo "" >/dev/tty

PROFILE=$(prompt "Databricks CLI profile name" "")

if [ -n "$PROFILE" ]; then
  TRACKING_URI="databricks://${PROFILE}"
else
  TRACKING_URI="databricks"
  # Check for unified auth env vars
  echo "" >/dev/tty
  echo "No profile specified — using Databricks unified auth." >/dev/tty
  MISSING_AUTH=""
  if [ -z "${DATABRICKS_HOST:-}" ]; then
    MISSING_AUTH="${MISSING_AUTH}  DATABRICKS_HOST\n"
  fi
  if [ -z "${DATABRICKS_TOKEN:-}" ] && [ -z "${DATABRICKS_CLIENT_ID:-}" ]; then
    MISSING_AUTH="${MISSING_AUTH}  DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID/SECRET\n"
  fi
  if [ -n "$MISSING_AUTH" ]; then
    echo "INFO: Unified auth env vars not detected in current shell:" >/dev/tty
    printf "$MISSING_AUTH" >/dev/tty
    echo "Make sure these are set in your environment or Databricks CLI config." >/dev/tty
  else
    echo "Unified auth env vars detected." >/dev/tty
  fi
  echo "" >/dev/tty
fi

EXPERIMENT_NAME=$(prompt "MLFLOW_EXPERIMENT_NAME" "${MLFLOW_EXPERIMENT_NAME:-}")

if [ -z "$EXPERIMENT_NAME" ]; then
  echo "Error: MLFLOW_EXPERIMENT_NAME is required." >&2
  exit 1
fi

# ── Write settings.local.json → "env" ──────────────────────
# Claude Code exports "env" as real OS env vars to child processes.
# mlflow's get_env_var() picks them up via os.getenv() fallback.

if [ -f "$LOCAL_SETTINGS" ]; then
  $RUNNER -c "
import json
with open('$LOCAL_SETTINGS') as f:
    data = json.load(f)
env = data.setdefault('env', {})
env['MLFLOW_TRACKING_URI'] = '$TRACKING_URI'
env['MLFLOW_EXPERIMENT_NAME'] = '$EXPERIMENT_NAME'
with open('$LOCAL_SETTINGS', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
else
  cat > "$LOCAL_SETTINGS" << JSONEOF
{
  "env": {
    "MLFLOW_TRACKING_URI": "${TRACKING_URI}",
    "MLFLOW_EXPERIMENT_NAME": "${EXPERIMENT_NAME}"
  }
}
JSONEOF
fi

echo "" >/dev/tty
echo "Wrote to ${LOCAL_SETTINGS}:" >/dev/tty
echo "  MLFLOW_TRACKING_URI=${TRACKING_URI}" >/dev/tty
echo "  MLFLOW_EXPERIMENT_NAME=${EXPERIMENT_NAME}" >/dev/tty

# ── Write the shared Python script ─────────────────────────

write_script() {
  local dir="$1"
  mkdir -p "$dir"
  cat > "${dir}/trace_annotate.py" << 'PYEOF'
#!/usr/bin/env python3
"""Annotate MLflow traces with tags or feedback."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone


def setup():
    """Initialize MLflow tracking and disable tracing for this script's own calls."""
    from mlflow.claude_code.tracing import setup_mlflow

    setup_mlflow()

    import mlflow.tracing

    mlflow.tracing.disable()


def get_recent_traces(max_results: int = 10):
    """Return recent traces ordered by timestamp descending."""
    import mlflow

    return mlflow.search_traces(
        order_by=["timestamp_ms DESC"],
        max_results=max_results,
        return_type="list",
    )


def get_most_recent_trace_id() -> str:
    """Return the trace ID of the most recent trace, or exit with error."""
    traces = get_recent_traces(max_results=1)
    if not traces:
        print("Error: No traces found in the current experiment.", file=sys.stderr)
        sys.exit(1)
    return traces[0].info.trace_id


def format_timestamp(ts_ms: int) -> str:
    """Format epoch milliseconds as human-readable UTC string."""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def truncate(text: str, length: int = 60) -> str:
    """Truncate text to a given length with ellipsis."""
    if not text:
        return ""
    text = text.replace("\n", " ")
    return text[:length] + "..." if len(text) > length else text


# ── Subcommands ──────────────────────────────────────────────


def cmd_list(args):
    """List recent traces."""
    import mlflow

    traces = get_recent_traces(max_results=args.max_results)
    if not traces:
        print("No traces found in the current experiment.")
        return

    headers = ["Trace ID", "Timestamp", "Status", "Input Preview"]
    rows = []
    for t in traces:
        info = t.info
        input_preview = ""
        if t.data and t.data.request:
            input_preview = truncate(str(t.data.request))
        rows.append([
            info.trace_id,
            format_timestamp(info.timestamp_ms),
            info.status,
            input_preview,
        ])

    widths = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)

    print(fmt.format(*headers))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*row))

    print(f"\nTracking URI: {mlflow.get_tracking_uri()}")


def cmd_tag(args):
    """Tag a trace with key=value pairs."""
    import mlflow

    trace_id = args.trace_id or get_most_recent_trace_id()

    if not args.tags:
        print("Error: No tags provided. Use key=value pairs.", file=sys.stderr)
        sys.exit(1)

    for pair in args.tags:
        if "=" not in pair:
            print(f"Error: Invalid tag format '{pair}'. Expected key=value.", file=sys.stderr)
            sys.exit(1)
        key, value = pair.split("=", 1)
        mlflow.set_trace_tag(trace_id=trace_id, key=key, value=value)
        print(f"Set tag {key}={value} on trace {trace_id}")

    print(f"\nTracking URI: {mlflow.get_tracking_uri()}")


def cmd_feedback(args):
    """Log feedback on a trace."""
    import mlflow
    from mlflow.entities.assessment_source import AssessmentSource

    trace_id = args.trace_id or get_most_recent_trace_id()

    mlflow.log_feedback(
        trace_id=trace_id,
        name=args.name,
        value=args.value,
        rationale=args.rationale,
        source=AssessmentSource(
            source_type="HUMAN",
            source_id="claude_code_user",
        ),
    )
    print(f"Logged feedback {args.name}={args.value} on trace {trace_id}")

    mlflow.set_trace_tag(trace_id=trace_id, key="has_feedback", value="true")
    print(f"Set tag has_feedback=true on trace {trace_id}")

    print(f"\nTracking URI: {mlflow.get_tracking_uri()}")


# ── CLI ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Annotate MLflow traces with tags or feedback")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list", help="List recent traces")
    p_list.add_argument("--max-results", type=int, default=10)

    p_tag = subparsers.add_parser("tag", help="Tag a trace with key=value pairs")
    p_tag.add_argument("--trace-id", help="Trace ID (default: most recent)")
    p_tag.add_argument("tags", nargs="*", help="Tags as key=value pairs")

    p_feedback = subparsers.add_parser("feedback", help="Log feedback on a trace")
    p_feedback.add_argument("--trace-id", help="Trace ID (default: most recent)")
    p_feedback.add_argument("--name", required=True)
    p_feedback.add_argument("--value", required=True)
    p_feedback.add_argument("--rationale")

    args = parser.parse_args()

    try:
        setup()

        if args.command == "list":
            cmd_list(args)
        elif args.command == "tag":
            cmd_tag(args)
        elif args.command == "feedback":
            cmd_feedback(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF
}

# Write script into both skill directories
write_script "${ROOT}/.claude/skills/tag-trace/scripts"
write_script "${ROOT}/.claude/skills/feedback-trace/scripts"

# ── Tag skill ───────────────────────────────────────────────

mkdir -p "${ROOT}/.claude/skills/tag-trace"
cat > "${ROOT}/.claude/skills/tag-trace/SKILL.md" << SKILLEOF
---
name: tag
description: Tags an MLflow trace or session with key-value pairs. Use when the user wants to add tags, labels, or metadata to a trace after it has been logged. Triggers on "tag trace", "tag this trace", "add tag", "label trace", "tag session".
---

# Tag an MLflow Trace

Run \`.claude/skills/tag-trace/scripts/trace_annotate.py\` to add key-value tags to traces.

## Examples

**Tag the most recent trace:**
\`\`\`bash
${RUNNER} .claude/skills/tag-trace/scripts/trace_annotate.py tag quality=good
\`\`\`

**Multiple tags:**
\`\`\`bash
${RUNNER} .claude/skills/tag-trace/scripts/trace_annotate.py tag sprint=42 reviewer=alice bug=true
\`\`\`

**Tag a specific trace:**
\`\`\`bash
${RUNNER} .claude/skills/tag-trace/scripts/trace_annotate.py tag --trace-id tr-abc123 quality=good
\`\`\`

**List recent traces (to find a trace ID):**
\`\`\`bash
${RUNNER} .claude/skills/tag-trace/scripts/trace_annotate.py list
\`\`\`

## Arguments

### \`tag\` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| \`tags\` | Yes | One or more \`key=value\` pairs (positional) |
| \`--trace-id\` | No | Trace ID to tag (default: most recent trace) |

### \`list\` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| \`--max-results\` | No | Number of traces to show (default: 10) |

## Notes

- Tags are string key-value pairs stored on the trace's \`info.tags\` dictionary
- Tags can be used for filtering: \`mlflow traces search --filter-string "tag.<key> = '<value>'"\`
- Common tag patterns: \`quality:good\`, \`reviewed:true\`, \`sprint:42\`, \`bug:true\`
SKILLEOF

# ── Feedback skill ──────────────────────────────────────────

mkdir -p "${ROOT}/.claude/skills/feedback-trace"
cat > "${ROOT}/.claude/skills/feedback-trace/SKILL.md" << SKILLEOF
---
name: feedback
description: Logs feedback (assessments) on an MLflow trace. Use when the user wants to rate, review, or add feedback to a trace after it has been logged. Triggers on "feedback on trace", "rate this trace", "thumbs up", "thumbs down", "add feedback", "review trace quality", "log feedback".
---

# Log Feedback on an MLflow Trace

Run \`.claude/skills/feedback-trace/scripts/trace_annotate.py\` to log human feedback (assessments) on traces.

## Examples

**Positive feedback on the most recent trace:**
\`\`\`bash
${RUNNER} .claude/skills/feedback-trace/scripts/trace_annotate.py feedback --name thumbs_up --value true
\`\`\`

**Quality rating with rationale:**
\`\`\`bash
${RUNNER} .claude/skills/feedback-trace/scripts/trace_annotate.py feedback --name quality --value good --rationale "great answer"
\`\`\`

**Feedback on a specific trace:**
\`\`\`bash
${RUNNER} .claude/skills/feedback-trace/scripts/trace_annotate.py feedback --trace-id tr-abc123 --name quality --value poor --rationale "hallucinated the API endpoint"
\`\`\`

**List recent traces (to find a trace ID):**
\`\`\`bash
${RUNNER} .claude/skills/feedback-trace/scripts/trace_annotate.py list
\`\`\`

## Arguments

### \`feedback\` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| \`--name\` | Yes | Feedback name (e.g. \`quality\`, \`thumbs_up\`, \`relevance\`) |
| \`--value\` | Yes | Feedback value (e.g. \`good\`, \`poor\`, \`true\`, \`5\`) |
| \`--trace-id\` | No | Trace ID (default: most recent trace) |
| \`--rationale\` | No | Free-text explanation of the feedback |

### \`list\` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| \`--max-results\` | No | Number of traces to show (default: 10) |

## Notes

- Feedback is stored as **assessments** on the trace's \`info.assessments\` array
- A \`has_feedback=true\` tag is automatically set for searchability
- Search for traces with feedback: \`mlflow traces search --filter-string "tag.has_feedback = 'true'"\`
- Multiple feedback entries can be added to the same trace (e.g., both \`quality\` and \`relevance\`)
- The \`source_type='HUMAN'\` indicates this feedback came from a human reviewer via Claude Code
- Common feedback patterns:
  - \`thumbs_up\` / \`thumbs_down\` for quick binary feedback
  - \`quality:good\` / \`quality:poor\` for quality assessment
  - \`rating:1-5\` for numeric scales
SKILLEOF

# ── Hook filter: skip tracing for skill invocations ──────────
# The Stop hook creates a trace for every Claude turn. Without this filter,
# feedback-trace and tag-trace skill invocations pollute the session with
# administrative traces. This proxy sits in front of the real hook, detects
# skill turns by reading the transcript (pure file I/O, zero MLflow imports),
# and short-circuits before the real hook runs.

mkdir -p "${ROOT}/.claude/hooks"
cat > "${ROOT}/.claude/hooks/skip_skill_traces.py" << 'HOOKEOF'
#!/usr/bin/env python3
"""Pre-filter for the MLflow Stop hook: skip tracing for specific skill invocations."""

import json
import os
import subprocess
import sys

SKIP_SKILLS = {
    "feedback-trace",
    "tag-trace",
}


def _should_skip(data):
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
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        else:
            text = str(content)

        text = text.lstrip()
        if not text.startswith("Base directory for this skill:"):
            return False

        first_line = text.split("\n", 1)[0]
        skill_path = first_line.split(":", 1)[1].strip()
        skill_name = os.path.basename(skill_path)
        return skill_name in SKIP_SKILLS

    return False


def main():
    hook_input = sys.stdin.read()
    data = json.loads(hook_input)

    if _should_skip(data):
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    separator = sys.argv.index("--") if "--" in sys.argv else 0
    real_cmd = sys.argv[separator + 1:]
    if not real_cmd:
        print(json.dumps({"continue": True}))
        return

    result = subprocess.run(real_cmd, input=hook_input, capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
HOOKEOF

echo "  Wrote .claude/hooks/skip_skill_traces.py" >/dev/tty

# ── Wrap the Stop hook with the filter ───────────────────────
# Finds the existing MLflow Stop hook command and prepends the filter proxy.
# If no Stop hook exists yet, creates one with the filter wrapping the handler.

$RUNNER -c "
import json
from pathlib import Path

FILTER = '\"\$CLAUDE_PROJECT_DIR\"/.claude/hooks/skip_skill_traces.py'
MLFLOW_MARKER = 'mlflow.claude_code.hooks'

path = Path('$SETTINGS')
config = {}
if path.exists():
    with open(path) as f:
        config = json.load(f)

hooks_cfg = config.setdefault('hooks', {})
stop_groups = hooks_cfg.setdefault('Stop', [])

# Find the MLflow hook and wrap it (or confirm already wrapped)
found = False
for group in stop_groups:
    for hook in group.get('hooks', []):
        cmd = hook.get('command', '')
        if MLFLOW_MARKER not in cmd:
            continue
        found = True
        if FILTER not in cmd:
            hook['command'] = '$RUNNER ' + FILTER + ' -- ' + cmd

if not found:
    # No existing MLflow hook found — create one with the filter
    real_cmd = '$RUNNER -c \"from mlflow.claude_code.hooks import stop_hook_handler; stop_hook_handler()\"'
    stop_groups.append({
        'hooks': [{
            'type': 'command',
            'command': '$RUNNER ' + FILTER + ' -- ' + real_cmd,
        }]
    })

with open(path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

print('Stop hook wrapped with skill filter')
" 2>&1 | while read -r line; do echo "  $line" >/dev/tty; done

# ── Done ─────────────────────────────────────────────────────

echo "" >/dev/tty
echo "Installed:" >/dev/tty
echo "  .claude/settings.json           -> MLFLOW_CLAUDE_TRACING_ENABLED=true" >/dev/tty
echo "  .claude/settings.json           -> Stop hook with skill filter" >/dev/tty
echo "  .claude/settings.local.json     -> MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME" >/dev/tty
echo "  .claude/skills/tag-trace/       -> /tag" >/dev/tty
echo "  .claude/skills/feedback-trace/  -> /feedback" >/dev/tty
echo "  .claude/hooks/skip_skill_traces.py" >/dev/tty
echo "" >/dev/tty
echo "Try it: claude -> /tag or /feedback" >/dev/tty
