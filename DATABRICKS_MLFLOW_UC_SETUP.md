# MLflow with Databricks and Unity Catalog Trace Storage

This guide explains how to set up MLflow experiments in Databricks with Unity Catalog for trace storage.

## Overview

This setup allows you to:
- Create MLflow experiments in Databricks
- Store MLflow traces in Unity Catalog tables
- Query and analyze traces using SQL
- Track ML model training, evaluation, and inference with full observability

## Prerequisites

1. **Databricks Workspace**
   - Unity Catalog enabled
   - Workspace URL (e.g., `https://your-workspace.cloud.databricks.com`)

2. **Authentication**
   - Personal Access Token (PAT) or service principal credentials
   - Appropriate permissions for experiment and UC table creation

3. **Unity Catalog Setup**
   - A catalog (default: `main`)
   - A schema for traces (default: `ml_traces`)
   - Permissions: `USE CATALOG`, `USE SCHEMA`, `CREATE TABLE`, `SELECT`, `INSERT`

4. **Python Environment**
   - Python 3.11+
   - MLflow 3.9.0+ (already in pyproject.toml)

## Quick Start

### 1. Set Environment Variables

```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="dapi..."
```

### 2. Create Unity Catalog Schema

Run the SQL script to create the required schema and tables:

```sql
-- See: databricks_uc_setup.sql
CREATE SCHEMA IF NOT EXISTS main.ml_traces;
GRANT ALL PRIVILEGES ON SCHEMA main.ml_traces TO `your-group`;
```

### 3. Setup Experiment

```python
from setup_databricks_experiment import setup_databricks_experiment

experiment_id = setup_databricks_experiment(
    experiment_name="/Users/your.email@company.com/my-experiment",
    catalog_name="main",
    schema_name="ml_traces"
)
```

### 4. Run ML Code with Tracing

```python
import mlflow
from mlflow.tracing import trace

# Enable tracing
mlflow.tracing.enable()

# Your ML code here - traces are automatically captured
@trace(name="train_model", span_type="TRAINING")
def train_model(data):
    # Training logic
    return {"accuracy": 0.95}

with mlflow.start_run():
    results = train_model(data)
    mlflow.log_metrics(results)
```

## File Guide

### Setup Scripts

- **`setup_databricks_experiment.py`**
  - Creates MLflow experiment in Databricks
  - Configures Unity Catalog trace storage
  - Run this first to set up your environment

- **`databricks_tracing_example.py`**
  - Example ML pipeline with tracing
  - Shows automatic and manual tracing patterns
  - Demonstrates nested spans and trace queries

- **`databricks_uc_setup.sql`**
  - SQL commands to create Unity Catalog schema
  - Grant necessary permissions
  - Create trace tables if needed

### Configuration Files

- **`pyproject.toml`**
  - Project dependencies (MLflow 3.9.0+)

- **`.claude/settings.json`**
  - Claude Code integration with MLflow tracing

## Unity Catalog Trace Schema

Traces are automatically stored in Unity Catalog with the following structure:

```
{catalog}.{schema}.mlflow_traces
├── request_id      (STRING)    - Unique identifier for the trace
├── trace_id        (STRING)    - MLflow trace ID
├── span_id         (STRING)    - Span identifier
├── span_name       (STRING)    - Name of the traced operation
├── span_type       (STRING)    - Type: WORKFLOW, TRAINING, EVALUATION, etc.
├── parent_span_id  (STRING)    - Parent span for nested traces
├── start_time_ms   (BIGINT)    - Start timestamp
├── end_time_ms     (BIGINT)    - End timestamp
├── status          (STRING)    - OK, ERROR, etc.
├── attributes      (MAP)       - Custom attributes
├── events          (ARRAY)     - Trace events
└── request_metadata (MAP)      - Metadata about the request
```

## Querying Traces

### View Recent Traces

```sql
SELECT
  request_id,
  span_name,
  span_type,
  status,
  (end_time_ms - start_time_ms) / 1000.0 as duration_seconds
FROM main.ml_traces.mlflow_traces
ORDER BY start_time_ms DESC
LIMIT 10;
```

### Analyze Training Performance

```sql
SELECT
  span_name,
  AVG((end_time_ms - start_time_ms) / 1000.0) as avg_duration_seconds,
  COUNT(*) as execution_count,
  SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as error_count
FROM main.ml_traces.mlflow_traces
WHERE span_type = 'TRAINING'
GROUP BY span_name
ORDER BY avg_duration_seconds DESC;
```

### Find Failed Traces

```sql
SELECT
  request_id,
  trace_id,
  span_name,
  status,
  attributes
FROM main.ml_traces.mlflow_traces
WHERE status = 'ERROR'
ORDER BY start_time_ms DESC;
```

## Best Practices

### 1. Experiment Naming

Use hierarchical names for better organization:
```python
experiment_name = "/Users/your.email@company.com/project/model-name"
```

### 2. Span Types

Use appropriate span types for different operations:
- `WORKFLOW` - End-to-end pipelines
- `TRAINING` - Model training
- `EVALUATION` - Model evaluation
- `PREPROCESSING` - Data preprocessing
- `INFERENCE` - Model inference
- `FEATURE_ENGINEERING` - Feature generation

### 3. Custom Attributes

Add context to your traces:
```python
with mlflow.tracing.start_span("model_training") as span:
    span.set_attribute("model_type", "random_forest")
    span.set_attribute("num_features", 100)
    span.set_attribute("dataset_size", 10000)
```

### 4. Error Handling

Traces automatically capture errors:
```python
@trace(name="risky_operation")
def risky_operation():
    try:
        # Your code
        pass
    except Exception as e:
        mlflow.tracing.get_current_span().set_status("ERROR")
        mlflow.tracing.get_current_span().set_attribute("error", str(e))
        raise
```

## Permissions

Required Unity Catalog permissions:

```sql
-- Grant catalog access
GRANT USE CATALOG ON CATALOG main TO `your-group`;

-- Grant schema access
GRANT USE SCHEMA ON SCHEMA main.ml_traces TO `your-group`;

-- Grant table operations
GRANT SELECT, INSERT, CREATE TABLE ON SCHEMA main.ml_traces TO `your-group`;
```

## Troubleshooting

### Issue: "Unity Catalog not enabled"

**Solution:** Verify Unity Catalog is enabled in your workspace:
```python
import mlflow
client = mlflow.tracking.MlflowClient()
# Should not raise an error
```

### Issue: "Permission denied"

**Solution:** Check your Unity Catalog permissions:
```sql
SHOW GRANTS ON SCHEMA main.ml_traces;
```

### Issue: "Experiment not found"

**Solution:** Verify the experiment was created:
```python
experiment = mlflow.get_experiment_by_name("/Users/you/experiment")
print(experiment.experiment_id if experiment else "Not found")
```

### Issue: "Traces not appearing in UC"

**Solution:**
1. Verify `MLFLOW_ENABLE_UNITY_CATALOG=true` is set
2. Check trace backend configuration
3. Verify schema and table exist
4. Check write permissions

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: ML Pipeline with Traces

on: [push]

jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run training with tracing
        env:
          DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
          DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_TOKEN }}
        run: python databricks_tracing_example.py
```

## Additional Resources

- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [Unity Catalog Documentation](https://docs.databricks.com/unity-catalog/index.html)
- [MLflow Tracing Guide](https://mlflow.org/docs/latest/tracing.html)
- [Databricks MLflow Integration](https://docs.databricks.com/mlflow/index.html)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review MLflow and Databricks documentation
3. Contact your Databricks workspace administrator for permission issues
