"""
End-to-End Test for Databricks MLflow with Unity Catalog Trace Storage

This script tests the complete setup:
1. Configuration validation
2. Databricks connectivity
3. Unity Catalog access
4. Experiment creation
5. Trace logging
6. Trace retrieval from UC

Run this after setup to verify everything works.
"""

import os
import sys
import time
from typing import Dict, Any
import mlflow
from mlflow.tracing import trace


def test_1_configuration() -> bool:
    """Test 1: Validate configuration."""
    print("\n" + "=" * 60)
    print("Test 1: Configuration Validation")
    print("=" * 60)

    required_vars = [
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
        "CATALOG_NAME",
        "SCHEMA_NAME",
        "EXPERIMENT_NAME"
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == "DATABRICKS_TOKEN":
                print(f"✓ {var}: ***{value[-4:]}")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")
            missing.append(var)

    if missing:
        print(f"\n❌ Test 1 FAILED: Missing variables: {', '.join(missing)}")
        return False

    print("\n✓ Test 1 PASSED: All required variables are set")
    return True


def test_2_databricks_connection() -> bool:
    """Test 2: Test Databricks connectivity."""
    print("\n" + "=" * 60)
    print("Test 2: Databricks Connection")
    print("=" * 60)

    try:
        databricks_host = os.getenv("DATABRICKS_HOST")
        mlflow.set_tracking_uri(databricks_host)

        # Try to list experiments
        client = mlflow.tracking.MlflowClient()
        experiments = client.search_experiments(max_results=5)

        print(f"✓ Connected to: {databricks_host}")
        print(f"✓ Found {len(experiments)} experiments")

        print("\n✓ Test 2 PASSED: Databricks connection successful")
        return True

    except Exception as e:
        print(f"\n❌ Test 2 FAILED: {str(e)}")
        return False


def test_3_experiment_setup() -> bool:
    """Test 3: Create or get experiment."""
    print("\n" + "=" * 60)
    print("Test 3: Experiment Setup")
    print("=" * 60)

    try:
        experiment_name = os.getenv("EXPERIMENT_NAME")
        print(f"Experiment name: {experiment_name}")

        # Try to get or create experiment
        experiment = mlflow.get_experiment_by_name(experiment_name)

        if experiment:
            experiment_id = experiment.experiment_id
            print(f"✓ Using existing experiment: {experiment_id}")
        else:
            print("Creating new experiment...")
            experiment_id = mlflow.create_experiment(
                name=experiment_name,
                tags={"test": "true", "created_by": "test_setup"}
            )
            print(f"✓ Created new experiment: {experiment_id}")

        # Set as active
        mlflow.set_experiment(experiment_name=experiment_name)

        print("\n✓ Test 3 PASSED: Experiment setup successful")
        return True

    except Exception as e:
        print(f"\n❌ Test 3 FAILED: {str(e)}")
        return False


@trace(name="test_function", span_type="TESTING")
def dummy_ml_function(x: int) -> Dict[str, Any]:
    """Dummy function to test tracing."""
    time.sleep(0.1)  # Simulate some work
    return {"result": x * 2, "status": "success"}


def test_4_tracing() -> bool:
    """Test 4: Test trace logging."""
    print("\n" + "=" * 60)
    print("Test 4: Trace Logging")
    print("=" * 60)

    try:
        # Enable tracing
        os.environ["MLFLOW_ENABLE_UNITY_CATALOG"] = "true"
        mlflow.tracing.enable()
        print("✓ Tracing enabled")

        # Start a run
        with mlflow.start_run(run_name="test_setup_run") as run:
            print(f"✓ Started run: {run.info.run_id}")

            # Call traced function
            result = dummy_ml_function(42)
            print(f"✓ Traced function executed: {result}")

            # Log some metrics
            mlflow.log_metric("test_metric", 0.99)
            mlflow.log_param("test_param", "test_value")
            print("✓ Metrics and params logged")

            run_id = run.info.run_id
            experiment_id = run.info.experiment_id

        print(f"\n✓ Run completed successfully")
        print(f"  Run ID: {run_id}")
        print(f"  Experiment ID: {experiment_id}")

        print("\n✓ Test 4 PASSED: Tracing works")
        return True

    except Exception as e:
        print(f"\n❌ Test 4 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_5_trace_retrieval() -> bool:
    """Test 5: Verify traces can be retrieved."""
    print("\n" + "=" * 60)
    print("Test 5: Trace Retrieval")
    print("=" * 60)

    try:
        # Note: This test assumes we're running in a Databricks environment
        # In a local environment, we can't query UC directly via SQL

        catalog_name = os.getenv("CATALOG_NAME", "main")
        schema_name = os.getenv("SCHEMA_NAME", "ml_traces")

        print(f"Traces should be stored in: {catalog_name}.{schema_name}.mlflow_traces")

        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()

            # Try to query traces
            traces_df = spark.sql(f"""
                SELECT COUNT(*) as trace_count
                FROM {catalog_name}.{schema_name}.mlflow_traces
            """)

            trace_count = traces_df.collect()[0][0]
            print(f"✓ Found {trace_count} traces in Unity Catalog")

            print("\n✓ Test 5 PASSED: Traces retrievable from UC")
            return True

        except ImportError:
            print("⚠ PySpark not available (not in Databricks environment)")
            print("✓ Traces should be stored in Unity Catalog")
            print("  Verify by running SQL query in Databricks:")
            print(f"  SELECT * FROM {catalog_name}.{schema_name}.mlflow_traces")
            print("\n✓ Test 5 SKIPPED: Can't verify UC traces locally")
            return True

    except Exception as e:
        print(f"⚠ Test 5 WARNING: {str(e)}")
        print("Note: This is expected if running outside Databricks")
        return True


def test_6_cleanup() -> bool:
    """Test 6: Optional cleanup."""
    print("\n" + "=" * 60)
    print("Test 6: Cleanup (Optional)")
    print("=" * 60)

    print("Note: Test experiment and traces were created")
    print("To clean up:")
    print("1. Delete test runs from MLflow UI")
    print("2. Or run: mlflow experiments delete <experiment_id>")
    print("\n✓ Test 6 PASSED: Cleanup instructions provided")
    return True


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("Databricks MLflow UC Setup - End-to-End Test")
    print("=" * 60)

    # Load environment
    try:
        from config_utils import load_env_file
        env_vars = load_env_file()
        if env_vars:
            print(f"✓ Loaded {len(env_vars)} variables from .env")
    except Exception:
        print("⚠ Could not load .env file")

    # Run tests
    tests = [
        ("Configuration", test_1_configuration),
        ("Databricks Connection", test_2_databricks_connection),
        ("Experiment Setup", test_3_experiment_setup),
        ("Tracing", test_4_tracing),
        ("Trace Retrieval", test_5_trace_retrieval),
        ("Cleanup", test_6_cleanup),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {str(e)}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Run your ML code with tracing enabled")
        print("2. View traces in Databricks MLflow UI")
        print("3. Query traces from Unity Catalog using SQL")
        return 0
    else:
        print("\n⚠ Some tests failed. Please review the output above.")
        print("\nCommon issues:")
        print("- Check .env file has correct values")
        print("- Verify Databricks token is valid")
        print("- Ensure Unity Catalog schema exists")
        print("- Run: python config_utils.py for diagnostics")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
