"""
Configuration utilities for Databricks MLflow with Unity Catalog.

This module provides helper functions to:
- Load and validate configuration
- Test Databricks connectivity
- Verify Unity Catalog permissions
- Check MLflow experiment setup
"""

import os
from typing import Dict, Optional, Tuple
import mlflow
from pathlib import Path


def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """
    Load environment variables from a .env file.

    Args:
        env_file: Path to the .env file

    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    env_path = Path(env_file)

    if not env_path.exists():
        print(f"Warning: {env_file} not found")
        print("Copy .env.example to .env and fill in your values")
        return env_vars

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Handle variable expansion like ${DATABRICKS_HOST}
                    if value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]
                        value = env_vars.get(var_name, os.getenv(var_name, ""))
                    env_vars[key] = value
                    os.environ[key] = value

    return env_vars


def validate_config() -> Tuple[bool, list]:
    """
    Validate that all required configuration is present.

    Returns:
        Tuple of (is_valid, list of missing variables)
    """
    required_vars = [
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
        "CATALOG_NAME",
        "SCHEMA_NAME",
        "EXPERIMENT_NAME"
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    return len(missing) == 0, missing


def test_databricks_connection() -> bool:
    """
    Test connectivity to Databricks workspace.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        databricks_host = os.getenv("DATABRICKS_HOST")
        databricks_token = os.getenv("DATABRICKS_TOKEN")

        if not databricks_host or not databricks_token:
            print("❌ DATABRICKS_HOST or DATABRICKS_TOKEN not set")
            return False

        # Set tracking URI
        mlflow.set_tracking_uri(databricks_host)

        # Try to list experiments (this will fail if credentials are invalid)
        client = mlflow.tracking.MlflowClient()
        experiments = client.search_experiments(max_results=1)

        print(f"✓ Connected to Databricks: {databricks_host}")
        return True

    except Exception as e:
        print(f"❌ Failed to connect to Databricks: {str(e)}")
        return False


def verify_unity_catalog_access() -> bool:
    """
    Verify that Unity Catalog is accessible with the configured catalog and schema.

    Returns:
        True if UC is accessible, False otherwise
    """
    try:
        from pyspark.sql import SparkSession

        catalog_name = os.getenv("CATALOG_NAME", "main")
        schema_name = os.getenv("SCHEMA_NAME", "ml_traces")

        # Note: This requires running in a Databricks environment with Spark available
        spark = SparkSession.builder.getOrCreate()

        # Try to access the schema
        spark.sql(f"USE CATALOG {catalog_name}")
        result = spark.sql(f"SHOW SCHEMAS IN {catalog_name}").collect()
        schemas = [row[0] for row in result]

        if schema_name in schemas:
            print(f"✓ Unity Catalog accessible: {catalog_name}.{schema_name}")
            return True
        else:
            print(f"❌ Schema {schema_name} not found in catalog {catalog_name}")
            print(f"   Available schemas: {', '.join(schemas)}")
            return False

    except ImportError:
        print("⚠ PySpark not available - skipping Unity Catalog verification")
        print("   (This check only works in a Databricks environment)")
        return True  # Don't fail if not in Databricks
    except Exception as e:
        print(f"❌ Failed to verify Unity Catalog access: {str(e)}")
        return False


def check_experiment_exists(experiment_name: Optional[str] = None) -> bool:
    """
    Check if the MLflow experiment exists.

    Args:
        experiment_name: Name of the experiment (uses EXPERIMENT_NAME env var if not provided)

    Returns:
        True if experiment exists, False otherwise
    """
    try:
        if experiment_name is None:
            experiment_name = os.getenv("EXPERIMENT_NAME")

        if not experiment_name:
            print("❌ EXPERIMENT_NAME not set")
            return False

        experiment = mlflow.get_experiment_by_name(experiment_name)

        if experiment:
            print(f"✓ Experiment exists: {experiment_name}")
            print(f"  Experiment ID: {experiment.experiment_id}")
            print(f"  Lifecycle stage: {experiment.lifecycle_stage}")
            return True
        else:
            print(f"❌ Experiment not found: {experiment_name}")
            print("   Run setup_databricks_experiment.py to create it")
            return False

    except Exception as e:
        print(f"❌ Failed to check experiment: {str(e)}")
        return False


def print_config_summary():
    """Print a summary of the current configuration."""
    print("=" * 60)
    print("Configuration Summary")
    print("=" * 60)

    config_items = [
        ("Databricks Host", os.getenv("DATABRICKS_HOST", "Not set")),
        ("Databricks Token", "***" + os.getenv("DATABRICKS_TOKEN", "")[-4:] if os.getenv("DATABRICKS_TOKEN") else "Not set"),
        ("Catalog Name", os.getenv("CATALOG_NAME", "Not set")),
        ("Schema Name", os.getenv("SCHEMA_NAME", "Not set")),
        ("Experiment Name", os.getenv("EXPERIMENT_NAME", "Not set")),
        ("UC Enabled", os.getenv("MLFLOW_ENABLE_UNITY_CATALOG", "Not set")),
        ("Claude Tracing", os.getenv("MLFLOW_CLAUDE_TRACING_ENABLED", "Not set")),
    ]

    for label, value in config_items:
        print(f"{label:.<25} {value}")

    print("=" * 60)


def run_full_diagnostics():
    """Run all diagnostic checks."""
    print("\n" + "=" * 60)
    print("Running Databricks MLflow UC Configuration Diagnostics")
    print("=" * 60 + "\n")

    # Step 1: Load environment
    print("Step 1: Loading environment variables...")
    env_vars = load_env_file()
    if env_vars:
        print(f"✓ Loaded {len(env_vars)} variables from .env")
    else:
        print("⚠ No .env file found, using system environment variables")
    print()

    # Step 2: Validate config
    print("Step 2: Validating configuration...")
    is_valid, missing = validate_config()
    if is_valid:
        print("✓ All required variables are set")
    else:
        print(f"❌ Missing required variables: {', '.join(missing)}")
    print()

    # Step 3: Print config summary
    print_config_summary()
    print()

    # Step 4: Test Databricks connection
    print("Step 3: Testing Databricks connection...")
    db_connected = test_databricks_connection()
    print()

    # Step 5: Verify Unity Catalog
    print("Step 4: Verifying Unity Catalog access...")
    uc_accessible = verify_unity_catalog_access()
    print()

    # Step 6: Check experiment
    print("Step 5: Checking MLflow experiment...")
    experiment_exists = check_experiment_exists()
    print()

    # Summary
    print("=" * 60)
    print("Diagnostic Summary")
    print("=" * 60)
    checks = [
        ("Configuration Valid", is_valid),
        ("Databricks Connected", db_connected),
        ("Unity Catalog Accessible", uc_accessible),
        ("Experiment Exists", experiment_exists),
    ]

    for label, passed in checks:
        status = "✓" if passed else "❌"
        print(f"{status} {label}")

    all_passed = all(passed for _, passed in checks)
    print("=" * 60)

    if all_passed:
        print("\n🎉 All checks passed! Your environment is ready.")
    else:
        print("\n⚠ Some checks failed. Please review the output above.")

    return all_passed


if __name__ == "__main__":
    # Run diagnostics when executed directly
    run_full_diagnostics()
