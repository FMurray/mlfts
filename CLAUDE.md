# mlfts — MLflow Tracing for Claude Code Sessions

## Project Overview

This project integrates MLflow tracing with Claude Code to capture, evaluate, and improve AI coding assistant sessions.

## Key Rules

- Always use `uv run` to execute Python scripts (not raw `python`)
- MLflow tracking URI is set to Databricks — do not create local experiments
- The `.claude/hooks/` directory contains session lifecycle hooks — do not modify without understanding the full hook chain
- Use the `skills/` directory skills for MLflow operations (tracing, evaluation, feedback)
- Never commit `.env` files or Databricks tokens

## Architecture

- **SessionStart hook** (`log_cc_environment.py`): Snapshots git SHA, CLAUDE.md hash, skills hash into a sidecar JSON
- **Stop hook** (`skip_skill_traces.py`): Creates MLflow trace from transcript, enriches with environment tags, links CLAUDE.md prompt version
- **Skills**: MLflow operations exposed as Claude Code skills (feedback, tagging, analysis, evaluation)

## Testing

Run tests with: `uv run pytest tests/ -v`
