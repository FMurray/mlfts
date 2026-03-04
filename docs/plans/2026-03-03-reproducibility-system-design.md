# Lightweight Reproducibility System for Claude Code + MLflow

## Problem

Instruction rot is hard to track because there's no record of what CLAUDE.md said when a session ran. Without that, you can't distinguish "Claude violated this instruction" from "this instruction didn't exist yet," and you can't measure whether a CLAUDE.md change improved compliance.

## Solution

Tag each MLflow trace with the environment state captured at session start. Every trace links to the exact instruction context that was active when the session began.

## Architecture

```
SessionStart hook fires
  -> log_cc_environment.py reads session_id from stdin
  -> Computes: git SHA, CLAUDE.md hash + content, skills dir hash
  -> Writes sidecar: .claude/mlflow/env_{session_id}.json

[... session runs ...]

Stop hook fires
  -> skip_skill_traces.py delegates to stop_hook_handler()
  -> stop_hook_handler() creates the trace
  -> skip_skill_traces.py reads sidecar, enriches trace with environment data
  -> Sidecar cleaned up
```

## Components

### 1. `log_cc_environment.py` (new file, `.claude/hooks/`)

SessionStart hook script. Zero MLflow dependency for fast startup.

**Inputs:** Hook stdin JSON containing `session_id`

**Actions:**
- Resolve project dir from `$CLAUDE_PROJECT_DIR`
- `git rev-parse HEAD` for commit SHA
- `git diff --quiet` for dirty flag
- SHA-256 of CLAUDE.md content (or `none` if absent)
- SHA-256 of sorted skills SKILL.md concatenation
- Read full CLAUDE.md text

**Output:** Writes `.claude/mlflow/env_{session_id}.json`:
```json
{
  "session_id": "abc123",
  "git_sha": "a1b2c3d4...",
  "git_dirty": false,
  "claude_md_hash": "sha256:...",
  "claude_md_content": "# Project Instructions\n...",
  "skills_hash": "sha256:...",
  "snapshot_timestamp": "2026-03-03T10:00:00Z"
}
```

Returns `{"continue": true}` to stdout.

### 2. `skip_skill_traces.py` (extended, `.claude/hooks/`)

After delegating to `stop_hook_handler()`:
- Read sidecar `.claude/mlflow/env_{session_id}.json`
- Use `MlflowClient` to set trace tags and root span attributes
- Delete the sidecar file

### 3. `.claude/settings.json` (modified)

Add `SessionStart` hook entry pointing to `log_cc_environment.py`.

## Data Model

### Trace tags (queryable via `mlflow.search_traces()`)

| Tag | Value | Purpose |
|-----|-------|---------|
| `cc_env.git_sha` | 40-char commit hash | Link to codebase version |
| `cc_env.claude_md_hash` | SHA-256 or `none` | Fast comparison across sessions |

### Root span attributes (full data for judges)

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `cc_env.git_sha` | commit hash | Codebase version |
| `cc_env.git_dirty` | boolean | Working tree state |
| `cc_env.claude_md_hash` | SHA-256 or `none` | Instruction fingerprint |
| `cc_env.claude_md_content` | full text | Judge access to instructions |
| `cc_env.skills_hash` | SHA-256 | Skills configuration fingerprint |
| `cc_env.snapshot_timestamp` | ISO 8601 | When snapshot was taken |

## Graceful Handling

- No CLAUDE.md: hash = `none`, content = `""`
- No git repo: SHA = `none`, dirty = `none`
- No sidecar at stop time: skip enrichment silently
- Non-zero exit from start hook: Claude Code continues normally

## Usage for Compliance Analysis

With this in place, you can query:

```python
# "Did compliance improve after CLAUDE.md commit abc123?"
traces = mlflow.search_traces(
    filter_string="tags.`cc_env.git_sha` = 'abc123'"
)

# Compare satisfaction scores across instruction versions
for trace in traces:
    root_span = trace.data.spans[0]
    claude_md = root_span.attributes.get("cc_env.claude_md_content")
    # Feed to judge alongside trace for compliance evaluation
```

## Known Limitations

- **Trace pollution from feedback skills:** Handled by existing `skip_skill_traces.py` filter. Sessions still appear as separate turns; pragmatic fix is post-processing at eval time.
- **Mid-session CLAUDE.md edits:** Not captured. Snapshot reflects session start only. Could add stop-time snapshot as future enhancement.
- **Skills content not stored:** Only a hash of the skills dir. If needed, could extend sidecar to include skill content.
