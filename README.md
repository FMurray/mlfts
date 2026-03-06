# mlfts — MLflow Tracing & Evaluation for AI Coding Agents

`mlfts` extends mlflow tracing for coding agents (currently Claude Code) with tools to evaluate, judge, and improve agent quality over time.

## What It Does

**Trace** — Enriches existing traces with git state, prompt versions, and environment metadata for reproduibility.

**Version** — Your `CLAUDE.md` instructions are registered as versioned prompts in MLflow's Prompt Registry, linked to each session trace. Correlate quality changes with prompt changes.

**Evaluate** — Run LLM judges and custom scorers against traced sessions. Build evaluation datasets, define quality metrics, and track agent improvement systematically.

**Feedback** — Tag and annotate traces directly from Claude Code. Log human assessments, flag issues, and build labeled datasets for evaluation.

## Architecture

```
SessionStart hook                    Stop hook
┌─────────────────────┐              ┌─────────────────────────────────┐
│ log_cc_environment.py│              │ skip_skill_traces.py            │
│                     │              │   ├─ filters skill invocations  │
│ • git SHA + dirty   │   sidecar   │   ├─ delegates to MLflow hook   │
│ • CLAUDE.md hash    │──── .json ──▶│   ├─ applies cc_env.* tags     │
│ • skills hash       │              │   └─ creates companion trace   │
│ • register prompt   │              │       (links prompt version)   │
└─────────────────────┘              └─────────────────────────────────┘

                    Post-session
┌──────────────────────────────────────────────────┐
│ Evaluation & Quality Improvement                 │
│   ├─ LLM judges score session quality            │
│   ├─ Custom scorers for domain-specific metrics  │
│   ├─ Aggregated metrics (latency, tokens, errors)│
│   └─ Human feedback loop via skills              │
└──────────────────────────────────────────────────┘
```

**Key design choices:**
- **Sidecar pattern** — SessionStart writes a JSON file keyed by session ID; the Stop hook reads and deletes it (hooks can't share memory)
- **Fail-safe** — all hook functions swallow exceptions so they never break your Claude Code session
- **Skill trace suppression** — `/tag` and `/feedback` invocations are filtered out to keep session traces clean

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Databricks workspace with Unity Catalog enabled
- Databricks CLI profile configured

### Install

Add the marketplace source and install the plugin:

```
/plugin marketplace add <repo-url>
/plugin install mlfts
```

Then configure your tracking URI and experiment name in `.claude/settings.local.json`:

```json
{
  "environment": {
    "MLFLOW_TRACKING_URI": "databricks",
    "MLFLOW_EXPERIMENT_NAME": "/Users/<your-email>/my-experiment",
    "DATABRICKS_CONFIG_PROFILE": "your-profile"
  }
}
```

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

### Verify

```bash
uv run pytest tests/ -v
```

## Usage

Once installed, tracing happens automatically. Just use Claude Code normally.

### Tag a trace

```
/tag key1=value1 key2=value2
```

### Log feedback

```
/feedback --name quality --value 5 --rationale "Great session"
```

### Evaluate sessions

Use the `agent-evaluation` skill to run LLM judges against traced sessions — define scorers, build evaluation datasets, and track quality metrics over time.

### Query traces in SQL

```sql
SELECT * FROM main.ml_traces.mlflow_traces
ORDER BY start_time_ms DESC
LIMIT 10;
```

## Skills

### Tracing & Annotation

| Skill | Description |
|-------|-------------|
| `feedback-trace` | Log human feedback/assessments on traces |
| `tag-trace` | Add key=value tags to traces |
| `instrumenting-with-mlflow-tracing` | Add tracing to Python/TypeScript code |

### Analysis & Debugging

| Skill | Description |
|-------|-------------|
| `analyze-mlflow-trace` | Debug and investigate a single trace |
| `analyze-mlflow-chat-session` | Analyze multi-turn chat sessions |
| `retrieving-mlflow-traces` | Search and filter traces |
| `querying-mlflow-metrics` | Aggregated metrics (latency, tokens, errors) |

### Evaluation & Quality

| Skill | Description |
|-------|-------------|
| `agent-evaluation` | Evaluate agent quality with LLM judges and custom scorers |

## Project Structure

```
mlfts/
├── .claude-plugin/
│   ├── plugin.json                  # Plugin config (hooks, env, metadata)
│   ├── marketplace.json             # Marketplace registry
│   ├── hooks/
│   │   ├── log_cc_environment.py    # SessionStart hook
│   │   └── skip_skill_traces.py     # Stop hook (proxy + enrichment)
│   └── skills/
│       ├── tag-trace/               # Tag traces with key=value pairs
│       └── feedback-trace/          # Log human feedback on traces
├── .claude/
│   ├── settings.json                # Project-level config
│   └── skills/                      # Upstream MLflow skills (submodule)
├── skills/                          # MLflow skills source library
├── tests/                           # Unit tests for hooks
├── CLAUDE.md                        # Project instructions (versioned as prompt)
├── QUICKSTART.md                    # 5-minute setup guide
└── pyproject.toml                   # Dependencies and project metadata
```

## How Prompt Versioning Works

`CLAUDE.md` is registered as a versioned prompt in MLflow's Prompt Registry. Each session trace is tagged with `cc_env.prompt_uri` pointing to the exact version used. A companion "env_snapshot" trace auto-links the prompt version in the Databricks UI.

This lets you correlate session quality with specific prompt versions — the foundation for systematic prompt engineering on coding agents.

## Testing

```bash
uv run pytest tests/ -v
```

## Further Reading

- [QUICKSTART.md](QUICKSTART.md) — 5-minute setup guide
- [DATABRICKS_MLFLOW_UC_SETUP.md](DATABRICKS_MLFLOW_UC_SETUP.md) — Detailed Databricks and Unity Catalog setup
- [README_DATABRICKS_UC.md](README_DATABRICKS_UC.md) — Complete Unity Catalog reference
