"""Test trace tagging and feedback with search on Databricks."""

import os

os.environ["DATABRICKS_CONFIG_PROFILE"] = "field-eng"

import mlflow
from mlflow.entities import AssessmentSource, AssessmentSourceType

mlflow.set_tracking_uri("databricks")
mlflow.set_experiment("/Shared/feedback-test")


@mlflow.trace
def my_agent(prompt):
    return f"Response to: {prompt}"


# Trace 1: with feedback + tag
result1 = my_agent("hello world")
mlflow.flush_trace_async_logging()
trace1_id = mlflow.get_last_active_trace_id()
print(f"Trace 1 ID: {trace1_id}")

mlflow.log_feedback(
    trace_id=trace1_id,
    name="user_rating",
    value="positive",
    source=AssessmentSource(
        source_type=AssessmentSourceType.HUMAN, source_id="user_123"
    ),
)
mlflow.set_trace_tag(trace_id=trace1_id, key="has_feedback", value="true")
mlflow.set_trace_tag(trace_id=trace1_id, key="feedback_user_rating", value="positive")
print("Trace 1: feedback + tags logged")

# Trace 2: no feedback, no tag
result2 = my_agent("no feedback here")
mlflow.flush_trace_async_logging()
trace2_id = mlflow.get_last_active_trace_id()
print(f"Trace 2 ID: {trace2_id} (no feedback)")

# Trace 3: with feedback + tag
result3 = my_agent("another rated one")
mlflow.flush_trace_async_logging()
trace3_id = mlflow.get_last_active_trace_id()
print(f"Trace 3 ID: {trace3_id}")

mlflow.log_feedback(
    trace_id=trace3_id,
    name="user_rating",
    value="negative",
    source=AssessmentSource(
        source_type=AssessmentSourceType.HUMAN, source_id="user_456"
    ),
)
mlflow.set_trace_tag(trace_id=trace3_id, key="has_feedback", value="true")
mlflow.set_trace_tag(trace_id=trace3_id, key="feedback_user_rating", value="negative")
print("Trace 3: feedback + tags logged")

# --- Search tests ---

print("\n=== Search: tag.has_feedback = 'true' (should find 2) ===")
tagged = mlflow.search_traces(filter_string="tag.has_feedback = 'true'")
print(f"Found {len(tagged)} traces")
print(tagged.columns.tolist())
print(tagged.head())

print("\n=== Search: tag.feedback_user_rating = 'positive' (should find 1) ===")
positive = mlflow.search_traces(filter_string="tag.feedback_user_rating = 'positive'")
print(f"Found {len(positive)} traces")
print(positive.head())

print("\n=== Search: tag.feedback_user_rating = 'negative' (should find 1) ===")
negative = mlflow.search_traces(filter_string="tag.feedback_user_rating = 'negative'")
print(f"Found {len(negative)} traces")
print(negative.head())

print("\n=== Search: all traces (should find 3) ===")
all_traces = mlflow.search_traces()
print(f"Total traces: {len(all_traces)}")
