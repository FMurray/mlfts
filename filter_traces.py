"""Filter spans from MLflow traces and create new traces with only matching spans.

For each source trace, creates a new trace containing only the spans that match
the given span names and/or attribute filters. Span hierarchy is preserved where
possible — if a matching span's parent is also a match, the parent-child
relationship is kept; otherwise the span is reparented to the root.

Usage:
    python filter_traces.py \
        --trace-ids abc123 def456 \
        --span-names ChatModel retrieve \
        --attributes mlflow.chat_model.name=gpt-4 environment=prod

    # Filter by name only
    python filter_traces.py --trace-ids abc123 --span-names ChatModel

    # Filter by attributes only
    python filter_traces.py --trace-ids abc123 --attributes model=gpt-4
"""

import argparse

import mlflow
from mlflow import MlflowClient


def filter_and_create_traces(
    trace_ids: list[str],
    span_names: list[str] | None = None,
    attributes: dict[str, str] | None = None,
    experiment_id: str | None = None,
) -> list[str]:
    """Filter spans from traces and create new traces with only matching spans.

    Args:
        trace_ids: Source trace IDs to process.
        span_names: If provided, only include spans whose name is in this list.
        attributes: If provided, only include spans that have all of these
            key-value pairs in their attributes.
        experiment_id: Target experiment for the new traces. Defaults to the
            source trace's experiment.

    Returns:
        List of newly created trace IDs.
    """
    client = MlflowClient()
    new_trace_ids = []

    for trace_id in trace_ids:
        trace = mlflow.get_trace(trace_id=trace_id)
        if trace is None:
            print(f"Trace {trace_id} not found, skipping.")
            continue

        spans = trace.data.spans
        matching = _filter_spans(spans, span_names, attributes)

        if not matching:
            print(f"No matching spans in trace {trace_id}, skipping.")
            continue

        new_id = _create_trace_from_spans(
            client,
            source_trace=trace,
            matching_spans=matching,
            experiment_id=experiment_id,
        )
        new_trace_ids.append(new_id)
        print(
            f"Created trace {new_id} with {len(matching)} span(s) "
            f"(source: {trace_id})"
        )

    return new_trace_ids


def _filter_spans(spans, span_names, attributes):
    """Return spans that match ALL provided criteria."""
    matching = []
    for span in spans:
        if span_names and span.name not in span_names:
            continue
        if attributes:
            span_attrs = span.attributes or {}
            if not all(span_attrs.get(k) == v for k, v in attributes.items()):
                continue
        matching.append(span)
    return matching


def _create_trace_from_spans(client, source_trace, matching_spans, experiment_id):
    """Create a new trace containing only the matching spans.

    Hierarchy is preserved between matching spans. Any matching span whose
    parent is not in the matching set gets reparented under the root.
    """
    matching_ids = {s.span_id for s in matching_spans}
    sorted_spans = sorted(matching_spans, key=lambda s: s.start_time_ns)

    source_id = source_trace.info.trace_id
    target_experiment = experiment_id or source_trace.info.experiment_id

    # --- root span (first matching span by start time) ---
    root = sorted_spans[0]
    root_span = client.start_trace(
        name=root.name,
        span_type=root.span_type,
        inputs=root.inputs,
        attributes=root.attributes or {},
        tags={
            "source_trace_id": source_id,
            "filtered": "true",
        },
        experiment_id=target_experiment,
        start_time_ns=root.start_time_ns,
    )

    new_trace_id = root_span.trace_id
    id_map = {root.span_id: root_span.span_id}

    # --- child spans ---
    for span in sorted_spans[1:]:
        # Keep original parent if it's also a match, otherwise reparent to root
        if span.parent_id in matching_ids and span.parent_id in id_map:
            parent_id = id_map[span.parent_id]
        else:
            parent_id = root_span.span_id

        new_span = client.start_span(
            name=span.name,
            trace_id=new_trace_id,
            parent_id=parent_id,
            span_type=span.span_type,
            inputs=span.inputs,
            attributes=span.attributes or {},
            start_time_ns=span.start_time_ns,
        )
        id_map[span.span_id] = new_span.span_id

    # --- end child spans (reverse order so children close before parents) ---
    for span in reversed(sorted_spans[1:]):
        client.end_span(
            trace_id=new_trace_id,
            span_id=id_map[span.span_id],
            outputs=span.outputs,
            attributes=span.attributes or {},
            status=span.status.status_code.value if span.status else "OK",
            end_time_ns=span.end_time_ns,
        )

    # --- end root / trace ---
    client.end_trace(
        trace_id=new_trace_id,
        outputs=root.outputs,
        attributes=root.attributes or {},
        status=root.status.status_code.value if root.status else "OK",
        end_time_ns=root.end_time_ns,
    )

    return new_trace_id


def _parse_attributes(raw: list[str] | None) -> dict[str, str] | None:
    if not raw:
        return None
    attrs = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(f"Invalid attribute format '{item}', expected key=value")
        key, value = item.split("=", 1)
        attrs[key] = value
    return attrs


def main():
    parser = argparse.ArgumentParser(
        description="Filter spans from MLflow traces and create new traces."
    )
    parser.add_argument(
        "--trace-ids",
        nargs="+",
        required=True,
        help="One or more source trace IDs.",
    )
    parser.add_argument(
        "--span-names",
        nargs="+",
        default=None,
        help="Only include spans with these names.",
    )
    parser.add_argument(
        "--attributes",
        nargs="+",
        default=None,
        help="Only include spans with these attributes (key=value pairs).",
    )
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="Target experiment ID for new traces. Defaults to source experiment.",
    )
    args = parser.parse_args()

    attributes = _parse_attributes(args.attributes)

    if not args.span_names and not attributes:
        parser.error("Provide at least one of --span-names or --attributes.")

    new_ids = filter_and_create_traces(
        trace_ids=args.trace_ids,
        span_names=args.span_names,
        attributes=attributes,
        experiment_id=args.experiment_id,
    )
    print(f"\nCreated {len(new_ids)} new trace(s): {new_ids}")


if __name__ == "__main__":
    main()
