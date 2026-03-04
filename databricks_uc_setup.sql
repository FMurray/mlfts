-- ============================================================================
-- Unity Catalog Setup for MLflow Trace Storage
-- ============================================================================
-- This script creates the necessary Unity Catalog schema and tables
-- for storing MLflow traces.
--
-- Run this in a Databricks SQL editor or notebook with appropriate permissions.
-- ============================================================================

-- ============================================================================
-- Step 1: Create the catalog (if it doesn't exist)
-- ============================================================================
-- Note: You typically use an existing catalog like 'main'
-- Uncomment if you need to create a new catalog:

-- CREATE CATALOG IF NOT EXISTS main
-- COMMENT 'Main catalog for ML operations';

-- USE CATALOG main;


-- ============================================================================
-- Step 2: Create the schema for ML traces
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS main.ml_traces
COMMENT 'Schema for storing MLflow traces and experiment metadata';

-- Verify schema creation
DESCRIBE SCHEMA EXTENDED main.ml_traces;


-- ============================================================================
-- Step 3: Grant permissions to users/groups
-- ============================================================================
-- Replace 'your-group' with your actual group name or service principal

-- Grant catalog-level permissions
GRANT USE CATALOG ON CATALOG main TO `your-group`;

-- Grant schema-level permissions
GRANT USE SCHEMA ON SCHEMA main.ml_traces TO `your-group`;
GRANT CREATE TABLE ON SCHEMA main.ml_traces TO `your-group`;

-- Grant table-level permissions (these will apply to all tables in the schema)
GRANT SELECT ON SCHEMA main.ml_traces TO `your-group`;
GRANT INSERT ON SCHEMA main.ml_traces TO `your-group`;
GRANT MODIFY ON SCHEMA main.ml_traces TO `your-group`;

-- Optionally, grant to specific users
-- GRANT ALL PRIVILEGES ON SCHEMA main.ml_traces TO `user@company.com`;


-- ============================================================================
-- Step 4: Create the traces table (Optional - MLflow creates this automatically)
-- ============================================================================
-- MLflow typically creates this table automatically, but you can pre-create it
-- with this schema for more control:

CREATE TABLE IF NOT EXISTS main.ml_traces.mlflow_traces (
  request_id STRING NOT NULL COMMENT 'Unique identifier for the trace request',
  trace_id STRING COMMENT 'MLflow trace ID',
  span_id STRING NOT NULL COMMENT 'Unique identifier for the span',
  span_name STRING COMMENT 'Name of the traced operation',
  span_type STRING COMMENT 'Type of span: WORKFLOW, TRAINING, EVALUATION, etc.',
  parent_span_id STRING COMMENT 'Parent span ID for nested traces',
  start_time_ms BIGINT COMMENT 'Start timestamp in milliseconds',
  end_time_ms BIGINT COMMENT 'End timestamp in milliseconds',
  status STRING COMMENT 'Span status: OK, ERROR, etc.',
  attributes MAP<STRING, STRING> COMMENT 'Custom attributes as key-value pairs',
  events ARRAY<STRUCT<
    name: STRING,
    timestamp_ms: BIGINT,
    attributes: MAP<STRING, STRING>
  >> COMMENT 'Array of events that occurred during the span',
  request_metadata MAP<STRING, STRING> COMMENT 'Metadata about the trace request',
  execution_order INT COMMENT 'Execution order of spans',
  inputs STRING COMMENT 'JSON string of input data',
  outputs STRING COMMENT 'JSON string of output data',
  tags MAP<STRING, STRING> COMMENT 'User-defined tags',
  experiment_id STRING COMMENT 'MLflow experiment ID',
  timestamp TIMESTAMP COMMENT 'Record creation timestamp'
)
USING DELTA
COMMENT 'MLflow traces stored in Unity Catalog'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
);

-- Create partitions for better query performance (optional)
-- ALTER TABLE main.ml_traces.mlflow_traces
-- ADD PARTITION FIELD days(timestamp);


-- ============================================================================
-- Step 5: Create additional metadata tables (Optional)
-- ============================================================================

-- Table for experiment metadata
CREATE TABLE IF NOT EXISTS main.ml_traces.experiments (
  experiment_id STRING NOT NULL,
  experiment_name STRING,
  artifact_location STRING,
  lifecycle_stage STRING,
  creation_time TIMESTAMP,
  last_update_time TIMESTAMP,
  tags MAP<STRING, STRING>,
  PRIMARY KEY (experiment_id)
)
USING DELTA
COMMENT 'MLflow experiment metadata';

-- Table for run metadata
CREATE TABLE IF NOT EXISTS main.ml_traces.runs (
  run_id STRING NOT NULL,
  experiment_id STRING,
  run_name STRING,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  status STRING,
  artifact_uri STRING,
  lifecycle_stage STRING,
  user_id STRING,
  tags MAP<STRING, STRING>,
  PRIMARY KEY (run_id)
)
USING DELTA
COMMENT 'MLflow run metadata';


-- ============================================================================
-- Step 6: Create views for common queries (Optional but recommended)
-- ============================================================================

-- View for recent traces
CREATE OR REPLACE VIEW main.ml_traces.recent_traces AS
SELECT
  request_id,
  trace_id,
  span_name,
  span_type,
  start_time_ms,
  end_time_ms,
  (end_time_ms - start_time_ms) / 1000.0 as duration_seconds,
  status,
  experiment_id,
  timestamp
FROM main.ml_traces.mlflow_traces
WHERE timestamp >= CURRENT_DATE() - INTERVAL 30 DAYS
ORDER BY start_time_ms DESC;

-- View for training performance
CREATE OR REPLACE VIEW main.ml_traces.training_performance AS
SELECT
  span_name,
  COUNT(*) as execution_count,
  AVG((end_time_ms - start_time_ms) / 1000.0) as avg_duration_seconds,
  MIN((end_time_ms - start_time_ms) / 1000.0) as min_duration_seconds,
  MAX((end_time_ms - start_time_ms) / 1000.0) as max_duration_seconds,
  SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as error_count,
  MAX(timestamp) as last_execution
FROM main.ml_traces.mlflow_traces
WHERE span_type = 'TRAINING'
GROUP BY span_name;

-- View for error traces
CREATE OR REPLACE VIEW main.ml_traces.error_traces AS
SELECT
  request_id,
  trace_id,
  span_name,
  span_type,
  status,
  attributes,
  timestamp,
  (end_time_ms - start_time_ms) / 1000.0 as duration_seconds
FROM main.ml_traces.mlflow_traces
WHERE status = 'ERROR'
ORDER BY timestamp DESC;

-- View for trace lineage
CREATE OR REPLACE VIEW main.ml_traces.trace_lineage AS
SELECT
  t.trace_id,
  t.span_id,
  t.span_name,
  t.span_type,
  t.parent_span_id,
  p.span_name as parent_span_name,
  t.start_time_ms,
  t.end_time_ms
FROM main.ml_traces.mlflow_traces t
LEFT JOIN main.ml_traces.mlflow_traces p
  ON t.parent_span_id = p.span_id
  AND t.trace_id = p.trace_id
ORDER BY t.trace_id, t.start_time_ms;


-- ============================================================================
-- Step 7: Verify setup
-- ============================================================================

-- Show all tables in the schema
SHOW TABLES IN main.ml_traces;

-- Show grants on the schema
SHOW GRANTS ON SCHEMA main.ml_traces;

-- Verify the traces table structure
DESCRIBE TABLE EXTENDED main.ml_traces.mlflow_traces;


-- ============================================================================
-- Example Queries
-- ============================================================================

-- Query 1: Get all traces from the last 7 days
-- SELECT * FROM main.ml_traces.recent_traces
-- WHERE timestamp >= CURRENT_DATE() - INTERVAL 7 DAYS
-- LIMIT 100;

-- Query 2: Analyze training performance
-- SELECT * FROM main.ml_traces.training_performance
-- ORDER BY execution_count DESC;

-- Query 3: Find slow operations (> 10 seconds)
-- SELECT
--   span_name,
--   (end_time_ms - start_time_ms) / 1000.0 as duration_seconds,
--   status,
--   timestamp
-- FROM main.ml_traces.mlflow_traces
-- WHERE (end_time_ms - start_time_ms) / 1000.0 > 10
-- ORDER BY duration_seconds DESC
-- LIMIT 50;

-- Query 4: Trace hierarchy for a specific trace_id
-- SELECT * FROM main.ml_traces.trace_lineage
-- WHERE trace_id = 'your-trace-id-here';


-- ============================================================================
-- Maintenance Commands (Run periodically)
-- ============================================================================

-- Optimize tables for better query performance
-- OPTIMIZE main.ml_traces.mlflow_traces;

-- Vacuum old files (removes files older than retention period)
-- VACUUM main.ml_traces.mlflow_traces RETAIN 168 HOURS; -- 7 days

-- Analyze table statistics for query optimization
-- ANALYZE TABLE main.ml_traces.mlflow_traces COMPUTE STATISTICS FOR ALL COLUMNS;


-- ============================================================================
-- Cleanup Commands (Use with caution!)
-- ============================================================================

-- Drop the entire schema and all its contents
-- DROP SCHEMA IF EXISTS main.ml_traces CASCADE;

-- Drop specific table
-- DROP TABLE IF EXISTS main.ml_traces.mlflow_traces;

-- Revoke permissions
-- REVOKE ALL PRIVILEGES ON SCHEMA main.ml_traces FROM `your-group`;
