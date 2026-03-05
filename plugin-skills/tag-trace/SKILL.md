---
name: tag
description: Tags an MLflow trace or session with key-value pairs. Use when the user wants to add tags, labels, or metadata to a trace after it has been logged. Triggers on "tag trace", "tag this trace", "add tag", "label trace", "tag session".
---

# Tag an MLflow Trace

Run `${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py` to add key-value tags to traces.

## Examples

**Tag the most recent trace:**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py tag quality=good
```

**Multiple tags:**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py tag sprint=42 reviewer=alice bug=true
```

**Tag a specific trace:**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py tag --trace-id tr-abc123 quality=good
```

**List recent traces (to find a trace ID):**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py list
```

## Arguments

### `tag` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| `tags` | Yes | One or more `key=value` pairs (positional) |
| `--trace-id` | No | Trace ID to tag (default: most recent trace) |

### `list` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| `--max-results` | No | Number of traces to show (default: 10) |

## Notes

- Tags are string key-value pairs stored on the trace's `info.tags` dictionary
- Tags can be used for filtering: `mlflow traces search --filter-string "tag.<key> = '<value>'"`
- Common tag patterns: `quality:good`, `reviewed:true`, `sprint:42`, `bug:true`
- The git SHA is auto-tagged on every trace by the Stop hook — no need to manually tag it
