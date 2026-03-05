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
    """Return the trace ID of the most recent session trace, or exit with error."""
    import mlflow

    # Exclude env_snapshot companion traces created by skip_skill_traces.py
    traces = mlflow.search_traces(
        filter_string="tag.`cc_env.type` != 'env_snapshot'",
        order_by=["timestamp_ms DESC"],
        max_results=1,
        return_type="list",
    )
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

    # Build table rows
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

    # Calculate column widths
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

    # Tag for searchability
    mlflow.set_trace_tag(trace_id=trace_id, key="has_feedback", value="true")
    print(f"Set tag has_feedback=true on trace {trace_id}")

    print(f"\nTracking URI: {mlflow.get_tracking_uri()}")


# ── CLI ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Annotate MLflow traces with tags or feedback")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List recent traces")
    p_list.add_argument("--max-results", type=int, default=10, help="Number of traces to show (default: 10)")

    # tag
    p_tag = subparsers.add_parser("tag", help="Tag a trace with key=value pairs")
    p_tag.add_argument("--trace-id", help="Trace ID (default: most recent)")
    p_tag.add_argument("tags", nargs="*", help="Tags as key=value pairs")

    # feedback
    p_feedback = subparsers.add_parser("feedback", help="Log feedback on a trace")
    p_feedback.add_argument("--trace-id", help="Trace ID (default: most recent)")
    p_feedback.add_argument("--name", required=True, help="Feedback name (e.g. quality, thumbs_up)")
    p_feedback.add_argument("--value", required=True, help="Feedback value (e.g. good, bad, 5)")
    p_feedback.add_argument("--rationale", help="Optional rationale for the feedback")

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
