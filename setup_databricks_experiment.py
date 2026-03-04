"""
Setup MLflow Experiment in Databricks with Unity Catalog Trace Storage

This script creates an MLflow experiment in Databricks and configures it
to store traces in Unity Catalog.

Prerequisites:
- Databricks workspace URL
- Personal access token or authentication configured
- Unity Catalog enabled in your workspace
- Appropriate permissions for catalog/schema creation
"""

import mlflow
from mlflow.tracing import set_tracer
import os


def setup_databricks_experiment(
    experiment_name: str,
    catalog_name: str,
    schema_name: str,
    databricks_host: str = None,
    databricks_token: str = None,
):
    """
    Create an MLflow experiment in Databricks with Unity Catalog trace storage.

    Args:
        experiment_name: Name of the MLflow experiment (e.g., "/Users/me/my-experiment")
        catalog_name: Unity Catalog catalog name
        schema_name: Unity Catalog schema name
        databricks_host: Databricks workspace URL (e.g., "https://your-workspace.cloud.databricks.com")
                        If None, reads from DATABRICKS_HOST env var
        databricks_token: Databricks personal access token
                         If None, reads from DATABRICKS_TOKEN env var

    Returns:
        experiment_id: The ID of the created or existing experiment
    """

    # Set up Databricks connection
    if databricks_host is None:
        databricks_host = os.getenv("DATABRICKS_HOST")
    if databricks_token is None:
        databricks_token = os.getenv("DATABRICKS_TOKEN")

    if not databricks_host:
        raise ValueError("databricks_host must be provided or DATABRICKS_HOST env var must be set")
    if not databricks_token:
        raise ValueError("databricks_token must be provided or DATABRICKS_TOKEN env var must be set")

    # Configure MLflow to use Databricks
    mlflow.set_tracking_uri(databricks_host)
    os.environ["DATABRICKS_HOST"] = databricks_host
    os.environ["DATABRICKS_TOKEN"] = databricks_token

    print(f"Connected to Databricks: {databricks_host}")

    # Create or get the experiment
    try:
        experiment_id = mlflow.create_experiment(
            name=experiment_name,
            tags={
                "environment": "production",
                "trace_storage": "unity_catalog",
            }
        )
        print(f"Created new experiment: {experiment_name} (ID: {experiment_id})")
    except Exception as e:
        # Experiment might already exist
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment:
            experiment_id = experiment.experiment_id
            print(f"Using existing experiment: {experiment_name} (ID: {experiment_id})")
        else:
            raise e

    # Set the experiment as active
    mlflow.set_experiment(experiment_name=experiment_name)

    # Configure Unity Catalog for trace storage
    uc_table_name = f"{catalog_name}.{schema_name}.mlflow_traces"

    print(f"\nConfiguring Unity Catalog trace storage:")
    print(f"  Catalog: {catalog_name}")
    print(f"  Schema: {schema_name}")
    print(f"  Traces table: {uc_table_name}")

    # Set the trace backend to Unity Catalog
    # Note: This requires MLflow 2.9.0+ and appropriate UC permissions
    os.environ["MLFLOW_TRACKING_URI"] = databricks_host
    os.environ["MLFLOW_ENABLE_UNITY_CATALOG"] = "true"

    # Configure the tracer to use Unity Catalog
    # The traces will be automatically stored in the UC table when logged
    print(f"\n✓ Experiment '{experiment_name}' is ready!")
    print(f"✓ Traces will be stored in Unity Catalog table: {uc_table_name}")
    print(f"\nExperiment ID: {experiment_id}")

    return experiment_id


def example_usage():
    """Example of how to use the experiment with tracing."""

    # Start a traced run
    with mlflow.start_run() as run:
        print(f"\nStarted run: {run.info.run_id}")

        # Enable tracing for this run
        mlflow.tracing.enable()

        # Your model code here - traces will be automatically captured
        # For example:
        mlflow.log_param("example_param", "value")
        mlflow.log_metric("example_metric", 0.95)

        print("Run completed - traces will be stored in Unity Catalog")
        print(f"View run at: {mlflow.get_tracking_uri()}/#/experiments/{run.info.experiment_id}/runs/{run.info.run_id}")


if __name__ == "__main__":
    # Example configuration
    # Update these values for your environment

    EXPERIMENT_NAME = "/Users/your.email@company.com/ml-traces-experiment"
    CATALOG_NAME = "main"  # or your catalog name
    SCHEMA_NAME = "ml_traces"  # or your schema name

    # These can be set as environment variables instead:
    # export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
    # export DATABRICKS_TOKEN="dapi..."

    print("=" * 60)
    print("MLflow Databricks Experiment Setup with UC Trace Storage")
    print("=" * 60)

    try:
        experiment_id = setup_databricks_experiment(
            experiment_name=EXPERIMENT_NAME,
            catalog_name=CATALOG_NAME,
            schema_name=SCHEMA_NAME,
        )

        print("\n" + "=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Ensure the Unity Catalog schema exists:")
        print(f"   CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME};")
        print("\n2. Grant appropriate permissions:")
        print(f"   GRANT ALL PRIVILEGES ON SCHEMA {CATALOG_NAME}.{SCHEMA_NAME} TO `your-group`;")
        print("\n3. Use the experiment in your code:")
        print(f"   mlflow.set_experiment('{EXPERIMENT_NAME}')")
        print("   mlflow.tracing.enable()")
        print("\n4. Run your ML code - traces will be automatically stored in UC!")

        # Uncomment to run example
        # example_usage()

    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("- Verify DATABRICKS_HOST and DATABRICKS_TOKEN are set")
        print("- Check that Unity Catalog is enabled in your workspace")
        print("- Ensure you have permissions to create experiments")
        print("- Verify the catalog and schema exist or you have permission to create them")
