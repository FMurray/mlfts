# Databricks notebook source
# MAGIC %md
# MAGIC # MLflow Experiment Setup with Unity Catalog Trace Storage
# MAGIC
# MAGIC This notebook sets up MLflow experiments in Databricks with Unity Catalog for trace storage.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Unity Catalog enabled
# MAGIC - Appropriate permissions on catalog and schema
# MAGIC - MLflow 2.9.0+ installed
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Configure parameters
# MAGIC 2. Create Unity Catalog schema
# MAGIC 3. Create MLflow experiment
# MAGIC 4. Run example with tracing
# MAGIC 5. Query traces from UC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------

# Configure your parameters here
CATALOG_NAME = "main"
SCHEMA_NAME = "ml_traces"
EXPERIMENT_NAME = f"/Users/{spark.sql('SELECT current_user()').collect()[0][0]}/ml-traces-experiment"

print(f"Configuration:")
print(f"  Catalog: {CATALOG_NAME}")
print(f"  Schema: {SCHEMA_NAME}")
print(f"  Experiment: {EXPERIMENT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Unity Catalog Schema

# COMMAND ----------

# Create schema if it doesn't exist
spark.sql(f"""
CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}
COMMENT 'Schema for MLflow traces'
""")

# Verify schema creation
display(spark.sql(f"DESCRIBE SCHEMA EXTENDED {CATALOG_NAME}.{SCHEMA_NAME}"))

print(f"✓ Schema {CATALOG_NAME}.{SCHEMA_NAME} is ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Setup MLflow Experiment

# COMMAND ----------

import mlflow
import os

# Configure MLflow to use Unity Catalog
os.environ["MLFLOW_ENABLE_UNITY_CATALOG"] = "true"

# Create or get experiment
try:
    experiment_id = mlflow.create_experiment(
        name=EXPERIMENT_NAME,
        tags={
            "environment": "production",
            "trace_storage": "unity_catalog",
            "catalog": CATALOG_NAME,
            "schema": SCHEMA_NAME
        }
    )
    print(f"✓ Created new experiment: {EXPERIMENT_NAME}")
except Exception as e:
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    experiment_id = experiment.experiment_id
    print(f"✓ Using existing experiment: {EXPERIMENT_NAME}")

print(f"  Experiment ID: {experiment_id}")

# Set as active experiment
mlflow.set_experiment(experiment_name=EXPERIMENT_NAME)

# Enable tracing
mlflow.tracing.enable()
print(f"✓ Tracing enabled")
print(f"✓ Traces will be stored in: {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Example: ML Pipeline with Tracing

# COMMAND ----------

from mlflow.tracing import trace
from typing import Dict, Any
import pandas as pd
import numpy as np

@trace(name="load_data", span_type="PREPROCESSING")
def load_data() -> pd.DataFrame:
    """Load sample data."""
    np.random.seed(42)
    df = pd.DataFrame({
        'feature_1': np.random.randn(1000),
        'feature_2': np.random.randn(1000),
        'feature_3': np.random.randn(1000),
        'target': np.random.randint(0, 2, 1000)
    })
    return df

@trace(name="preprocess_data", span_type="PREPROCESSING")
def preprocess_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Preprocess the data."""
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    X = df.drop('target', axis=1)
    y = df['target']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    return {
        'X_train': X_train_scaled,
        'X_test': X_test_scaled,
        'y_train': y_train,
        'y_test': y_test,
        'scaler': scaler
    }

@trace(name="train_model", span_type="TRAINING")
def train_model(data: Dict[str, Any]) -> Any:
    """Train a simple model."""
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42
    )

    model.fit(data['X_train'], data['y_train'])
    return model

@trace(name="evaluate_model", span_type="EVALUATION")
def evaluate_model(model: Any, data: Dict[str, Any]) -> Dict[str, float]:
    """Evaluate the model."""
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    y_pred = model.predict(data['X_test'])

    metrics = {
        'accuracy': accuracy_score(data['y_test'], y_pred),
        'precision': precision_score(data['y_test'], y_pred),
        'recall': recall_score(data['y_test'], y_pred),
        'f1_score': f1_score(data['y_test'], y_pred)
    }

    return metrics

@trace(name="ml_pipeline", span_type="WORKFLOW")
def run_pipeline() -> Dict[str, float]:
    """Complete ML pipeline."""
    # Load data
    df = load_data()

    # Preprocess
    data = preprocess_data(df)

    # Train
    model = train_model(data)

    # Evaluate
    metrics = evaluate_model(model, data)

    return metrics

# COMMAND ----------

# Run the pipeline with MLflow tracking and tracing
with mlflow.start_run(run_name="example_pipeline_with_traces") as run:
    print(f"Started run: {run.info.run_id}")

    # Run the pipeline - all decorated functions will be traced
    metrics = run_pipeline()

    # Log metrics
    mlflow.log_metrics(metrics)

    # Log parameters
    mlflow.log_params({
        "model_type": "RandomForestClassifier",
        "n_estimators": 100,
        "max_depth": 10
    })

    print(f"\n✓ Pipeline completed successfully!")
    print(f"  Accuracy: {metrics['accuracy']:.4f}")
    print(f"  F1 Score: {metrics['f1_score']:.4f}")
    print(f"\n✓ Traces stored in Unity Catalog")
    print(f"  Run ID: {run.info.run_id}")
    print(f"  Experiment ID: {run.info.experiment_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Query Traces from Unity Catalog

# COMMAND ----------

# Query recent traces
traces_df = spark.sql(f"""
SELECT
    request_id,
    trace_id,
    span_name,
    span_type,
    start_time_ms,
    end_time_ms,
    (end_time_ms - start_time_ms) / 1000.0 as duration_seconds,
    status,
    timestamp
FROM {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces
ORDER BY start_time_ms DESC
LIMIT 20
""")

display(traces_df)

# COMMAND ----------

# Query training spans only
training_spans_df = spark.sql(f"""
SELECT
    span_name,
    COUNT(*) as execution_count,
    AVG((end_time_ms - start_time_ms) / 1000.0) as avg_duration_seconds,
    MAX((end_time_ms - start_time_ms) / 1000.0) as max_duration_seconds,
    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as error_count
FROM {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces
WHERE span_type = 'TRAINING'
GROUP BY span_name
ORDER BY execution_count DESC
""")

display(training_spans_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. View Trace Lineage

# COMMAND ----------

# Get the most recent trace_id
latest_trace = spark.sql(f"""
SELECT DISTINCT trace_id
FROM {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces
ORDER BY start_time_ms DESC
LIMIT 1
""").collect()

if latest_trace:
    trace_id = latest_trace[0][0]
    print(f"Analyzing trace: {trace_id}")

    # Query the full trace hierarchy
    trace_hierarchy = spark.sql(f"""
    SELECT
        span_id,
        span_name,
        span_type,
        parent_span_id,
        (end_time_ms - start_time_ms) / 1000.0 as duration_seconds,
        status
    FROM {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces
    WHERE trace_id = '{trace_id}'
    ORDER BY start_time_ms
    """)

    display(trace_hierarchy)
else:
    print("No traces found")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Performance Analysis

# COMMAND ----------

# Analyze performance by span type
performance_df = spark.sql(f"""
SELECT
    span_type,
    COUNT(*) as total_executions,
    AVG((end_time_ms - start_time_ms) / 1000.0) as avg_duration,
    MIN((end_time_ms - start_time_ms) / 1000.0) as min_duration,
    MAX((end_time_ms - start_time_ms) / 1000.0) as max_duration,
    PERCENTILE((end_time_ms - start_time_ms) / 1000.0, 0.5) as median_duration,
    PERCENTILE((end_time_ms - start_time_ms) / 1000.0, 0.95) as p95_duration
FROM {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces
GROUP BY span_type
ORDER BY avg_duration DESC
""")

display(performance_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Error Analysis

# COMMAND ----------

# Find error traces
error_traces = spark.sql(f"""
SELECT
    request_id,
    trace_id,
    span_name,
    span_type,
    status,
    attributes,
    timestamp
FROM {CATALOG_NAME}.{SCHEMA_NAME}.mlflow_traces
WHERE status = 'ERROR'
ORDER BY timestamp DESC
LIMIT 10
""")

display(error_traces)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC You have successfully:
# MAGIC 1. ✓ Created Unity Catalog schema for traces
# MAGIC 2. ✓ Set up MLflow experiment
# MAGIC 3. ✓ Ran ML pipeline with automatic tracing
# MAGIC 4. ✓ Stored traces in Unity Catalog
# MAGIC 5. ✓ Queried and analyzed traces using SQL
# MAGIC
# MAGIC **Next Steps:**
# MAGIC - Integrate tracing into your production ML pipelines
# MAGIC - Create dashboards for trace analysis
# MAGIC - Set up alerts for performance degradation or errors
# MAGIC - Use trace data for debugging and optimization
# MAGIC
# MAGIC **Resources:**
# MAGIC - [MLflow Tracing Documentation](https://mlflow.org/docs/latest/tracing.html)
# MAGIC - [Unity Catalog Documentation](https://docs.databricks.com/unity-catalog/index.html)
# MAGIC - [Databricks MLflow Integration](https://docs.databricks.com/mlflow/index.html)
