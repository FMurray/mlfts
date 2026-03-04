import logging
import os
import time

from databricks.sdk import WorkspaceClient

import mlflow

logging.basicConfig(level=logging.INFO)

mlflow.set_tracking_uri("databricks")
mlflow.set_experiment(experiment_id="2517718719903786")

# Set env vars for litellm's databricks provider
w = WorkspaceClient()
os.environ["DATABRICKS_API_BASE"] = f"{w.config.host}/serving-endpoints"
os.environ["DATABRICKS_API_KEY"] = w.config.oauth_token().access_token

from mlflow.genai.judges import make_judge

satisfaction_scorer = make_judge(
    name="coding_agent_satisfaction",
    instructions=(
        "Evaluate whether the user's goals in this {{ trace }} were achieved. "
        "This is a coding agent — long pauses between tool calls are expected "
        "as the agent waits for user input or approval. Do NOT treat idle time "
        "or long wall-clock durations as failures. Focus on whether the agent: "
        "understood the coding task, produced correct code, and reached a "
        "satisfactory resolution."
    ),
    model="databricks:/databricks-claude-sonnet-4-6",
    feedback_value_type=bool,
)

start = time.time()
result = mlflow.genai.discover_issues(
    sample_size=50,
    satisfaction_scorer=satisfaction_scorer,
    judge_model="databricks:/databricks-claude-sonnet-4-6",
    analysis_model="databricks:/databricks-gpt-5-2",
)
elapsed = time.time() - start

print(f"\nDone in {elapsed:.1f}s — {len(result.issues)} issues found\n")
print(result.summary)

for issue in result.issues:
    print(f"\n--- {issue.name} ({issue.frequency:.0%}, confidence: {issue.confidence}/100) ---")
    print(f"  {issue.description}")
    print(f"  Root cause: {issue.root_cause}")
    print(f"  Examples: {issue.example_trace_ids[:3]}")
