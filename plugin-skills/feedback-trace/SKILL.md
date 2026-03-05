---
name: feedback
description: Logs feedback (assessments) on an MLflow trace. Use when the user wants to rate, review, or add feedback to a trace after it has been logged. Triggers on "feedback on trace", "rate this trace", "thumbs up", "thumbs down", "add feedback", "review trace quality", "log feedback".
---

# Log Feedback on an MLflow Trace

Run `${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py` to log human feedback (assessments) on traces.

## Examples

**Positive feedback on the most recent trace:**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py feedback --name thumbs_up --value true
```

**Quality rating with rationale:**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py feedback --name quality --value good --rationale "great answer"
```

**Feedback on a specific trace:**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py feedback --trace-id tr-abc123 --name quality --value poor --rationale "hallucinated the API endpoint"
```

**List recent traces (to find a trace ID):**
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/trace_annotate.py list
```

## Arguments

### `feedback` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| `--name` | Yes | Feedback name (e.g. `quality`, `thumbs_up`, `relevance`) |
| `--value` | Yes | Feedback value (e.g. `good`, `poor`, `true`, `5`) |
| `--trace-id` | No | Trace ID (default: most recent trace) |
| `--rationale` | No | Free-text explanation of the feedback |

### `list` subcommand

| Arg | Required | Description |
|-----|----------|-------------|
| `--max-results` | No | Number of traces to show (default: 10) |

## Notes

- Feedback is stored as **assessments** on the trace's `info.assessments` array
- A `has_feedback=true` tag is automatically set for searchability
- Search for traces with feedback: `mlflow traces search --filter-string "tag.has_feedback = 'true'"`
- Multiple feedback entries can be added to the same trace (e.g., both `quality` and `relevance`)
- The `source_type='HUMAN'` indicates this feedback came from a human reviewer via Claude Code
- Common feedback patterns:
  - `thumbs_up` / `thumbs_down` for quick binary feedback
  - `quality:good` / `quality:poor` for quality assessment
  - `rating:1-5` for numeric scales
