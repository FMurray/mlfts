# MLflow with Databricks and Unity Catalog Trace Storage

Complete setup for running MLflow experiments in Databricks with Unity Catalog as the backend for trace storage.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Databricks credentials
nano .env  # or use your favorite editor
```

Required configuration:
```bash
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
CATALOG_NAME=main
SCHEMA_NAME=ml_traces
EXPERIMENT_NAME=/Users/your.email@company.com/my-experiment
```

### 3. Verify Configuration

```bash
python config_utils.py
```

This will run diagnostics and verify:
- ✓ All required environment variables are set
- ✓ Databricks connection is working
- ✓ Unity Catalog is accessible
- ✓ Experiment exists or can be created

### 4. Setup Unity Catalog

Run the SQL script in a Databricks SQL editor or notebook:

```sql
-- See: databricks_uc_setup.sql
CREATE SCHEMA IF NOT EXISTS main.ml_traces;
GRANT ALL PRIVILEGES ON SCHEMA main.ml_traces TO `your-group`;
```

### 5. Create MLflow Experiment

```bash
python setup_databricks_experiment.py
```

### 6. Run Example

```bash
python databricks_tracing_example.py
```

## 📁 File Structure

```
mlfts/
├── setup_databricks_experiment.py    # Main setup script
├── databricks_tracing_example.py     # Example ML pipeline with tracing
├── databricks_notebook_setup.py      # Databricks notebook version
├── databricks_uc_setup.sql           # SQL setup for Unity Catalog
├── config_utils.py                   # Configuration helper utilities
├── .env.example                      # Environment template
├── DATABRICKS_MLFLOW_UC_SETUP.md     # Detailed documentation
└── README_DATABRICKS_UC.md           # This file
```

## 📚 Documentation

- **[DATABRICKS_MLFLOW_UC_SETUP.md](DATABRICKS_MLFLOW_UC_SETUP.md)** - Complete setup guide
- **[databricks_uc_setup.sql](databricks_uc_setup.sql)** - SQL scripts for Unity Catalog

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Databricks workspace URL | `https://your-workspace.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | Personal access token | `dapi...` |
| `CATALOG_NAME` | Unity Catalog catalog | `main` |
| `SCHEMA_NAME` | Schema for traces | `ml_traces` |
| `EXPERIMENT_NAME` | MLflow experiment name | `/Users/me/experiment` |
| `MLFLOW_ENABLE_UNITY_CATALOG` | Enable UC backend | `true` |

### Python API

```python
import os
import mlflow
from mlflow.tracing import trace

# Configure
os.environ["DATABRICKS_HOST"] = "https://your-workspace.cloud.databricks.com"
os.environ["DATABRICKS_TOKEN"] = "dapi..."
os.environ["MLFLOW_ENABLE_UNITY_CATALOG"] = "true"

# Set experiment
mlflow.set_experiment("/Users/me/my-experiment")
mlflow.tracing.enable()

# Use tracing
@trace(name="my_function", span_type="TRAINING")
def my_function():
    # Your code here
    pass

# Run with MLflow
with mlflow.start_run():
    result = my_function()
    mlflow.log_metric("accuracy", 0.95)
```

## 🎯 Usage Examples

### Basic Tracing

```python
from mlflow.tracing import trace

@trace(name="preprocess", span_type="PREPROCESSING")
def preprocess_data(data):
    # Automatically traced
    return processed_data

@trace(name="train", span_type="TRAINING")
def train_model(data):
    # Automatically traced
    return model
```

### Manual Spans

```python
import mlflow

with mlflow.start_run():
    with mlflow.tracing.start_span("data_loading") as span:
        data = load_data()
        span.set_attribute("rows", len(data))

    with mlflow.tracing.start_span("training") as span:
        model = train(data)
        span.set_attribute("model_type", "rf")
```

### Querying Traces

```sql
-- Recent traces
SELECT * FROM main.ml_traces.mlflow_traces
ORDER BY start_time_ms DESC
LIMIT 10;

-- Training performance
SELECT
  span_name,
  AVG((end_time_ms - start_time_ms) / 1000.0) as avg_seconds
FROM main.ml_traces.mlflow_traces
WHERE span_type = 'TRAINING'
GROUP BY span_name;

-- Error traces
SELECT * FROM main.ml_traces.mlflow_traces
WHERE status = 'ERROR'
ORDER BY timestamp DESC;
```

## 🔍 Diagnostics

Run diagnostics to check your setup:

```bash
python config_utils.py
```

Output example:
```
✓ All required variables are set
✓ Connected to Databricks
✓ Unity Catalog accessible
✓ Experiment exists
🎉 All checks passed!
```

## 📦 Dependencies

Core dependencies (from `pyproject.toml`):
- `mlflow>=3.9.0` - MLflow with tracing support
- `databricks-sdk>=0.20.0` - Databricks SDK
- `pandas>=2.0.0` - Data manipulation
- `numpy>=1.24.0` - Numerical computing
- `scikit-learn>=1.3.0` - ML algorithms

Optional development dependencies:
- `pytest>=7.0.0` - Testing
- `jupyter>=1.0.0` - Notebooks
- `ipython>=8.0.0` - Interactive Python

## 🎓 Key Concepts

### Trace Hierarchy

```
Workflow (span_type: WORKFLOW)
├── Preprocessing (span_type: PREPROCESSING)
│   ├── Load Data
│   └── Transform
├── Training (span_type: TRAINING)
│   ├── Feature Selection
│   └── Model Fitting
└── Evaluation (span_type: EVALUATION)
    ├── Predict
    └── Score
```

### Span Types

- `WORKFLOW` - End-to-end pipeline
- `TRAINING` - Model training
- `EVALUATION` - Model evaluation
- `PREPROCESSING` - Data preprocessing
- `FEATURE_ENGINEERING` - Feature generation
- `INFERENCE` - Model inference

### Unity Catalog Benefits

1. **Centralized Storage** - All traces in one location
2. **SQL Queries** - Query traces with standard SQL
3. **Access Control** - Unity Catalog permissions
4. **Data Governance** - Audit and lineage tracking
5. **Scalability** - Delta Lake backend

## 🔐 Security Best Practices

1. **Never commit secrets**
   ```bash
   # Add to .gitignore
   .env
   *.token
   ```

2. **Use service principals for production**
   ```bash
   DATABRICKS_CLIENT_ID=your-sp-client-id
   DATABRICKS_CLIENT_SECRET=your-sp-secret
   ```

3. **Rotate tokens regularly**
   - Create new tokens monthly
   - Revoke old tokens

4. **Grant minimal permissions**
   ```sql
   -- Only grant what's needed
   GRANT USE SCHEMA ON SCHEMA main.ml_traces TO `ml-team`;
   GRANT SELECT, INSERT ON TABLE main.ml_traces.mlflow_traces TO `ml-team`;
   ```

## 🐛 Troubleshooting

### Connection Issues

**Problem:** Can't connect to Databricks

**Solutions:**
1. Verify `DATABRICKS_HOST` is correct (include `https://`)
2. Check token is valid: Workspace → User Settings → Access Tokens
3. Ensure token hasn't expired

### Permission Errors

**Problem:** Permission denied on Unity Catalog

**Solutions:**
1. Verify you have access to the catalog:
   ```sql
   SHOW GRANTS ON CATALOG main;
   ```
2. Check schema permissions:
   ```sql
   SHOW GRANTS ON SCHEMA main.ml_traces;
   ```
3. Contact workspace admin to grant permissions

### Traces Not Appearing

**Problem:** Traces not showing up in Unity Catalog

**Solutions:**
1. Verify `MLFLOW_ENABLE_UNITY_CATALOG=true`
2. Check tracing is enabled: `mlflow.tracing.enable()`
3. Verify the schema exists:
   ```sql
   SHOW SCHEMAS IN main;
   ```
4. Check for errors in trace logs

## 📊 Monitoring & Observability

### Create Dashboards

Use Databricks SQL dashboards to visualize:
- Trace execution times
- Error rates
- Model performance over time
- Pipeline throughput

### Set Up Alerts

Configure alerts for:
- Failed traces (status = 'ERROR')
- Slow operations (duration > threshold)
- Unusual patterns

### Example Alert Query

```sql
SELECT COUNT(*) as error_count
FROM main.ml_traces.mlflow_traces
WHERE status = 'ERROR'
  AND timestamp >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
HAVING error_count > 10;
```

## 🚀 Next Steps

1. **Integrate with CI/CD**
   - Add tracing to your ML pipelines
   - Monitor training jobs
   - Track model performance

2. **Create Custom Dashboards**
   - Visualize trace data
   - Monitor ML operations
   - Track SLAs

3. **Implement Monitoring**
   - Set up alerts
   - Create SLIs/SLOs
   - Track business metrics

4. **Scale Your Operations**
   - Automate experiment creation
   - Standardize tracing patterns
   - Document best practices

## 📖 Additional Resources

- [MLflow Documentation](https://mlflow.org/docs/latest/)
- [Unity Catalog Guide](https://docs.databricks.com/unity-catalog/)
- [MLflow Tracing](https://mlflow.org/docs/latest/tracing.html)
- [Databricks MLflow](https://docs.databricks.com/mlflow/)

## 🤝 Contributing

Contributions welcome! Please:
1. Test your changes
2. Update documentation
3. Follow existing patterns
4. Add examples

## 📄 License

This project follows your organization's licensing terms.

## ⚡ Performance Tips

1. **Batch operations** - Process multiple traces together
2. **Use partitioning** - Partition tables by date for faster queries
3. **Optimize queries** - Add appropriate filters and indexes
4. **Archive old data** - Vacuum old trace data regularly

```sql
-- Optimize table
OPTIMIZE main.ml_traces.mlflow_traces;

-- Vacuum old data (7+ days)
VACUUM main.ml_traces.mlflow_traces RETAIN 168 HOURS;
```

## 🎯 Common Workflows

### Development
```bash
# 1. Setup environment
python config_utils.py

# 2. Create experiment
python setup_databricks_experiment.py

# 3. Run development code with tracing
python your_ml_code.py

# 4. Query traces
# Use Databricks SQL to analyze
```

### Production
```bash
# 1. Use service principal credentials
export DATABRICKS_CLIENT_ID=...
export DATABRICKS_CLIENT_SECRET=...

# 2. Run production pipeline
python production_pipeline.py

# 3. Monitor via dashboards
# Set up alerts for failures
```

---

**Need help?** Check the [detailed documentation](DATABRICKS_MLFLOW_UC_SETUP.md) or run diagnostics with `python config_utils.py`
