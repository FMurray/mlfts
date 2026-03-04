# Quick Start Guide - MLflow + Databricks + Unity Catalog

Get up and running in 5 minutes! ⚡

## Prerequisites

- Databricks workspace with Unity Catalog enabled
- Personal access token (PAT)
- Python 3.11+

## Step-by-Step Setup

### 1️⃣ Install Dependencies (1 min)

```bash
cd /Users/forrest.murray/Documents/mlfts
uv pip install -e .
```

### 2️⃣ Configure Environment (2 min)

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

Set these values in `.env`:
```bash
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...  # Get from: Workspace → Settings → Access Tokens
CATALOG_NAME=main
SCHEMA_NAME=ml_traces
EXPERIMENT_NAME=/Users/your.email@company.com/my-experiment
```

### 3️⃣ Verify Configuration (30 sec)

```bash
python config_utils.py
```

Expected output:
```
✓ All required variables are set
✓ Connected to Databricks
✓ Unity Catalog accessible
✓ Experiment exists
🎉 All checks passed!
```

### 4️⃣ Setup Unity Catalog (1 min)

**Option A: Using Databricks SQL Editor**

Copy and run from `databricks_uc_setup.sql`:
```sql
CREATE SCHEMA IF NOT EXISTS main.ml_traces;
GRANT ALL PRIVILEGES ON SCHEMA main.ml_traces TO `your-group`;
```

**Option B: Using Python (in Databricks notebook)**
```python
spark.sql("CREATE SCHEMA IF NOT EXISTS main.ml_traces")
```

### 5️⃣ Create Experiment (30 sec)

```bash
python setup_databricks_experiment.py
```

### 6️⃣ Test Everything (30 sec)

```bash
python test_setup.py
```

Expected: **6/6 tests passed** ✓

### 7️⃣ Run Example (1 min)

```bash
python databricks_tracing_example.py
```

This runs a complete ML pipeline with tracing!

## Verify Traces in Unity Catalog

### In Databricks SQL Editor:

```sql
-- View recent traces
SELECT * FROM main.ml_traces.mlflow_traces
ORDER BY start_time_ms DESC
LIMIT 10;
```

### In Databricks MLflow UI:

1. Go to: `https://your-workspace.cloud.databricks.com/#/mlflow`
2. Click on your experiment
3. Click on "Traces" tab

## Your First Traced Function

```python
import mlflow
from mlflow.tracing import trace

# Enable tracing
mlflow.set_experiment("/Users/you/my-experiment")
mlflow.tracing.enable()

# Decorate your functions
@trace(name="my_function", span_type="TRAINING")
def train_model(data):
    # Your code here
    return model

# Run with MLflow
with mlflow.start_run():
    model = train_model(data)
    mlflow.log_metric("accuracy", 0.95)
```

## What Gets Created

```
mlfts/
├── 📄 .env                           # Your credentials (create from .env.example)
├── 📄 .env.example                   # Template for credentials
│
├── 🐍 setup_databricks_experiment.py # Creates experiments in Databricks
├── 🐍 databricks_tracing_example.py  # Example ML pipeline with tracing
├── 🐍 databricks_notebook_setup.py   # Databricks notebook version
├── 🐍 config_utils.py                # Configuration helpers & diagnostics
├── 🐍 test_setup.py                  # End-to-end tests
│
├── 📊 databricks_uc_setup.sql        # SQL for Unity Catalog setup
│
├── 📖 DATABRICKS_MLFLOW_UC_SETUP.md  # Detailed documentation
├── 📖 README_DATABRICKS_UC.md        # Complete guide
└── 📖 QUICKSTART.md                  # This file
```

## Common Commands

| Task | Command |
|------|---------|
| Check configuration | `python config_utils.py` |
| Create experiment | `python setup_databricks_experiment.py` |
| Run tests | `python test_setup.py` |
| Run example | `python databricks_tracing_example.py` |
| View traces (SQL) | See `databricks_uc_setup.sql` for queries |

## Troubleshooting

### Issue: "Permission denied"
**Fix:** Ask admin to run:
```sql
GRANT ALL PRIVILEGES ON SCHEMA main.ml_traces TO `your-username`;
```

### Issue: "Can't connect to Databricks"
**Fix:**
1. Verify `DATABRICKS_HOST` includes `https://`
2. Check token is valid (create new one if expired)
3. Test: `curl -H "Authorization: Bearer $DATABRICKS_TOKEN" $DATABRICKS_HOST/api/2.0/clusters/list`

### Issue: "Traces not appearing"
**Fix:**
1. Ensure `MLFLOW_ENABLE_UNITY_CATALOG=true`
2. Call `mlflow.tracing.enable()`
3. Check schema exists: `SHOW SCHEMAS IN main;`

## Next Steps

✅ Setup complete? Now:

1. **Integrate with your code**
   - Add `@trace` decorators to functions
   - Start MLflow runs in your training scripts

2. **Create dashboards**
   - Use Databricks SQL to visualize traces
   - Monitor training performance

3. **Set up monitoring**
   - Create alerts for failures
   - Track SLAs and metrics

## Need More Help?

- 📖 **Detailed docs:** [DATABRICKS_MLFLOW_UC_SETUP.md](DATABRICKS_MLFLOW_UC_SETUP.md)
- 📖 **Full guide:** [README_DATABRICKS_UC.md](README_DATABRICKS_UC.md)
- 🔧 **Run diagnostics:** `python config_utils.py`
- 🧪 **Test setup:** `python test_setup.py`

## Example Queries

After running examples, try these in Databricks SQL:

```sql
-- Recent training runs
SELECT
  span_name,
  (end_time_ms - start_time_ms) / 1000.0 as duration_seconds,
  status
FROM main.ml_traces.mlflow_traces
WHERE span_type = 'TRAINING'
ORDER BY start_time_ms DESC
LIMIT 10;

-- Average performance by operation
SELECT
  span_name,
  COUNT(*) as executions,
  AVG((end_time_ms - start_time_ms) / 1000.0) as avg_seconds
FROM main.ml_traces.mlflow_traces
GROUP BY span_name
ORDER BY avg_seconds DESC;

-- Error rate
SELECT
  span_type,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as errors,
  SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate_pct
FROM main.ml_traces.mlflow_traces
GROUP BY span_type;
```

---

**⏱️ Total setup time: ~5-7 minutes**

**Questions?** Check the detailed guides or run `python config_utils.py` for diagnostics.
