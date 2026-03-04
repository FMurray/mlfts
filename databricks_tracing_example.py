"""
Example: Using MLflow Tracing with Unity Catalog in Databricks

This script demonstrates how to log traces to Unity Catalog when running
ML experiments in Databricks.
"""

import mlflow
from mlflow.tracing import trace
import os
from typing import Dict, Any


def setup_environment(
    experiment_name: str,
    catalog_name: str = "main",
    schema_name: str = "ml_traces"
):
    """
    Configure MLflow to use Databricks with Unity Catalog trace storage.

    Args:
        experiment_name: Name of the experiment
        catalog_name: Unity Catalog catalog name
        schema_name: Unity Catalog schema name
    """
    # Set experiment
    mlflow.set_experiment(experiment_name)

    # Enable Unity Catalog
    os.environ["MLFLOW_ENABLE_UNITY_CATALOG"] = "true"

    # Enable tracing
    mlflow.tracing.enable()

    print(f"✓ Configured experiment: {experiment_name}")
    print(f"✓ Traces will be stored in: {catalog_name}.{schema_name}.mlflow_traces")


@trace(name="preprocess_data", span_type="PREPROCESSING")
def preprocess_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example preprocessing function with automatic tracing.
    The @trace decorator will automatically capture this function's execution.
    """
    # Simulate preprocessing
    processed_data = {
        "features": data.get("features", []),
        "normalized": True,
        "timestamp": "2024-01-01"
    }
    return processed_data


@trace(name="train_model", span_type="TRAINING")
def train_model(data: Dict[str, Any]) -> Dict[str, float]:
    """
    Example training function with automatic tracing.
    """
    # Simulate model training
    metrics = {
        "accuracy": 0.95,
        "precision": 0.93,
        "recall": 0.92
    }
    return metrics


@trace(name="evaluate_model", span_type="EVALUATION")
def evaluate_model(model_metrics: Dict[str, float]) -> Dict[str, Any]:
    """
    Example evaluation function with automatic tracing.
    """
    # Simulate evaluation
    evaluation_results = {
        "test_accuracy": 0.94,
        "validation_accuracy": 0.93,
        "training_metrics": model_metrics
    }
    return evaluation_results


@trace(name="ml_pipeline", span_type="WORKFLOW")
def run_ml_pipeline(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete ML pipeline with nested tracing.
    Each function call will be captured as a span in the trace.
    """
    # Preprocess
    processed_data = preprocess_data(input_data)

    # Train
    model_metrics = train_model(processed_data)

    # Evaluate
    results = evaluate_model(model_metrics)

    return results


def example_with_manual_spans():
    """
    Example showing manual span creation for more control.
    """
    with mlflow.start_run(run_name="manual_tracing_example") as run:
        print(f"\nStarted run: {run.info.run_id}")

        # Create a parent span
        with mlflow.tracing.start_span("data_loading") as span:
            # Simulate data loading
            data = {"features": [1, 2, 3, 4, 5]}
            span.set_attribute("data_size", len(data["features"]))

            # Create a nested span
            with mlflow.tracing.start_span("data_validation") as validation_span:
                is_valid = len(data["features"]) > 0
                validation_span.set_attribute("is_valid", is_valid)

        # Log the results
        mlflow.log_param("input_size", len(data["features"]))
        mlflow.log_metric("validation_result", 1.0 if is_valid else 0.0)

        print("✓ Trace logged to Unity Catalog")
        return run.info.run_id


def example_with_automatic_tracing():
    """
    Example showing automatic tracing with decorated functions.
    """
    with mlflow.start_run(run_name="auto_tracing_example") as run:
        print(f"\nStarted run: {run.info.run_id}")

        # Input data
        input_data = {
            "features": [1.0, 2.0, 3.0, 4.0, 5.0],
            "labels": [0, 1, 0, 1, 1]
        }

        # Run the pipeline - all decorated functions will be traced
        results = run_ml_pipeline(input_data)

        # Log final results
        mlflow.log_metrics(results["training_metrics"])
        mlflow.log_params({"pipeline": "ml_pipeline", "auto_traced": True})

        print("✓ Complete pipeline trace logged to Unity Catalog")
        print(f"  Accuracy: {results['test_accuracy']}")
        return run.info.run_id


def query_traces_from_uc(catalog_name: str, schema_name: str):
    """
    Example of how to query traces from Unity Catalog using SQL.

    Run this in a Databricks notebook or SQL editor:
    """
    query = f"""
    SELECT
        request_id,
        trace_id,
        span_name,
        span_type,
        start_time_ms,
        end_time_ms,
        status,
        request_metadata,
        attributes
    FROM {catalog_name}.{schema_name}.mlflow_traces
    WHERE span_type = 'TRAINING'
    ORDER BY start_time_ms DESC
    LIMIT 10
    """

    print("\nTo query traces from Unity Catalog, run this SQL:")
    print("=" * 60)
    print(query)
    print("=" * 60)


if __name__ == "__main__":
    # Configuration
    EXPERIMENT_NAME = "/Users/your.email@company.com/ml-traces-experiment"
    CATALOG_NAME = "main"
    SCHEMA_NAME = "ml_traces"

    print("=" * 60)
    print("MLflow Tracing with Unity Catalog - Example")
    print("=" * 60)

    # Setup
    setup_environment(
        experiment_name=EXPERIMENT_NAME,
        catalog_name=CATALOG_NAME,
        schema_name=SCHEMA_NAME
    )

    print("\n--- Running Example 1: Automatic Tracing ---")
    try:
        run_id_1 = example_with_automatic_tracing()
        print(f"✓ Run completed: {run_id_1}")
    except Exception as e:
        print(f"Error in example 1: {e}")

    print("\n--- Running Example 2: Manual Tracing ---")
    try:
        run_id_2 = example_with_manual_spans()
        print(f"✓ Run completed: {run_id_2}")
    except Exception as e:
        print(f"Error in example 2: {e}")

    print("\n" + "=" * 60)
    print("Examples Complete!")
    print("=" * 60)

    # Show how to query traces
    query_traces_from_uc(CATALOG_NAME, SCHEMA_NAME)

    print("\nView your experiments in Databricks:")
    print(f"- Experiments: {mlflow.get_tracking_uri()}/#/experiments")
    print(f"- Traces: {mlflow.get_tracking_uri()}/#/traces")
    print(f"\nTraces are stored in Unity Catalog at:")
    print(f"  {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces")
