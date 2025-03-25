import datetime
import json
import os
from pathlib import Path

import pendulum
import pytest
from airflow import DAG
from airflow.utils.module_loading import import_string

from dagfactory.dagbuilder import DagBuilder
from dagfactory.exceptions import DagFactoryException

# Try to import HttpOperator with fallbacks for different Airflow versions
try:
    from airflow.providers.http.operators.http import HttpOperator
except ImportError:
    try:
        from airflow.operators.http_operator import SimpleHttpOperator as HttpOperator
    except ImportError:
        HttpOperator = None

# Get current directory and project root
here = Path(__file__).parent
PROJECT_ROOT_PATH = str(here.parent)
UTC = pendulum.timezone("UTC")

# Test constants
HTTP_OPERATOR_UNAVAILABLE_MSG = "HttpOperator not available in this Airflow version"

# Default config for testing
DEFAULT_CONFIG = {
    "default_args": {
        "owner": "default_owner",
        "start_date": datetime.date(2018, 3, 1),
        "end_date": datetime.date(2018, 3, 5),
        "retries": 1,
        "retry_delay_sec": 300,
    },
    "concurrency": 1,
    "max_active_runs": 1,
    "dagrun_timeout_sec": 600,
    "schedule_interval": "0 1 * * *",
}

# Basic DAG config for tests
DAG_CONFIG = {
    "default_args": {"owner": "custom_owner"},
    "description": "this is an example dag",
    "schedule_interval": "0 3 * * *",
}


@pytest.mark.skipif(HttpOperator is None, reason=HTTP_OPERATOR_UNAVAILABLE_MSG)
@pytest.mark.parametrize(
    "headers, data, expected_headers, expected_callable",
    [
        ({"Content-Type": "application/json"}, {"key": "value"}, {"Content-Type": "application/json"}, True),
        ({"Content-Type": "APPLICATION/JSON"}, {"key": "value"}, {"Content-Type": "APPLICATION/JSON"}, True),
        (
            {"Content-Type": "application/json; charset=utf-8"},
            {"key": "value"},
            {"Content-Type": "application/json; charset=utf-8"},
            True,
        ),
        ({"Content-Type": "text/plain"}, {"key": "value"}, {"Content-Type": "text/plain"}, False),
    ],
)
def test_http_operator_json_serialization(headers, data, expected_headers, expected_callable):
    """Test that HttpOperator properly handles JSON data serialization"""
    td = DagBuilder("test_dag", DAG_CONFIG, DEFAULT_CONFIG)

    # Try to get the right operator path for the current Airflow version
    operator = None
    for op_path in [
        "airflow.providers.http.operators.http.HttpOperator",
        "airflow.operators.http_operator.SimpleHttpOperator",
    ]:
        try:
            import_string(op_path)
            operator = op_path
            break
        except ImportError:
            continue

    if operator is None:
        pytest.skip(HTTP_OPERATOR_UNAVAILABLE_MSG)

    task_params = {
        "task_id": "test_http_task",
        "http_conn_id": "test_conn",
        "method": "POST",
        "endpoint": "/api/test",
        "headers": headers.copy(),
        "data": data,
    }

    task = td.make_task(operator, task_params)

    # For empty headers with application/json content type test:
    # We need to explicitly check if Content-Type was added to headers
    if not headers and "Content-Type" in expected_headers:
        assert task.headers.get("Content-Type") == expected_headers["Content-Type"]
    else:
        assert task.headers == expected_headers

    # For JSON content type, data should be a callable
    if expected_callable:
        assert callable(task.data)
        # Call the callable to ensure it returns valid JSON
        result = task.data()
        assert isinstance(result, str)
        # Verify we can parse it back to the original dict
        parsed = json.loads(result)
        assert parsed == data
    else:
        # For non-JSON content types, data should remain unchanged
        assert task.data == data


@pytest.mark.skipif(HttpOperator is None, reason=HTTP_OPERATOR_UNAVAILABLE_MSG)
@pytest.mark.parametrize(
    "json_string",
    ['{"key": "value", "nested": {"inner": "data"}}', '{"array": [1, 2, 3], "boolean": true, "null": null}'],
)
def test_http_operator_with_json_string(json_string):
    """Test that HttpOperator handles valid JSON strings correctly"""
    td = DagBuilder("test_dag", DAG_CONFIG, DEFAULT_CONFIG)

    # Try to get the right operator path for the current Airflow version
    operator = None
    for op_path in [
        "airflow.providers.http.operators.http.HttpOperator",
        "airflow.operators.http_operator.SimpleHttpOperator",
    ]:
        try:
            import_string(op_path)
            operator = op_path
            break
        except ImportError:
            continue

    if operator is None:
        pytest.skip(HTTP_OPERATOR_UNAVAILABLE_MSG)

    task_params = {
        "task_id": "test_http_task",
        "http_conn_id": "test_conn",
        "method": "POST",
        "endpoint": "/api/test",
        "headers": {"Content-Type": "application/json"},
        "data": json_string,
    }

    task = td.make_task(operator, task_params)

    # Data should be a callable for JSON content type
    assert callable(task.data)

    # The callable should return the original JSON string
    result = task.data()
    assert result == json_string


@pytest.mark.skipif(HttpOperator is None, reason=HTTP_OPERATOR_UNAVAILABLE_MSG)
@pytest.mark.parametrize(
    "invalid_json",
    ["{key: 'value'}", "{'key': 'value'}"],  # Missing quotes around key  # Single quotes instead of double quotes
)
def test_http_operator_with_invalid_json_string(invalid_json):
    """Test that HttpOperator raises error with invalid JSON strings"""
    from dagfactory import utils

    with pytest.raises(ValueError, match="Invalid JSON provided"):
        utils.get_json_serialized_callable(invalid_json)

    td = DagBuilder("test_dag", DAG_CONFIG, DEFAULT_CONFIG)

    # Try to get the right operator path for the current Airflow version
    operator = None
    for op_path in [
        "airflow.providers.http.operators.http.HttpOperator",
        "airflow.operators.http_operator.SimpleHttpOperator",
    ]:
        try:
            import_string(op_path)
            operator = op_path
            break
        except ImportError:
            continue

    if operator is None:
        pytest.skip(HTTP_OPERATOR_UNAVAILABLE_MSG)

    task_params = {
        "task_id": "test_http_task",
        "http_conn_id": "test_conn",
        "method": "POST",
        "endpoint": "/api/test",
        "headers": {"Content-Type": "application/json"},
        "data": invalid_json,
    }

    with pytest.raises(DagFactoryException):
        td.make_task(operator, task_params)


@pytest.mark.skip
@pytest.mark.skipif(HttpOperator is None, reason=HTTP_OPERATOR_UNAVAILABLE_MSG)
def test_dag_with_http_operator():
    """Test building a complete DAG with HttpOperator tasks"""
    # Create a config with HTTP operator tasks
    http_dag_config = {
        "default_args": {"owner": "test_owner", "start_date": datetime.date(2023, 1, 1)},
        "schedule_interval": "0 0 * * *",
        "tasks": {
            "http_task_json": {
                "operator": "airflow.providers.http.operators.http.HttpOperator",
                "http_conn_id": "test_conn",
                "method": "POST",
                "endpoint": "/api/test",
                "headers": {"Content-Type": "application/json"},
                "data": {"message": "test data", "value": 123},
            },
            "http_task_plain": {
                "operator": "airflow.providers.http.operators.http.HttpOperator",
                "http_conn_id": "test_conn",
                "method": "POST",
                "endpoint": "/api/test",
                "headers": {"Content-Type": "text/plain"},
                "data": "plain text data",
                "dependencies": ["http_task_json"],
            },
        },
    }

    # Build the DAG
    td = DagBuilder("test_http_dag", http_dag_config, DEFAULT_CONFIG)
    dag_obj = td.build()

    # Verify DAG was created successfully
    assert dag_obj["dag_id"] == "test_http_dag"
    assert isinstance(dag_obj["dag"], DAG)

    # Verify tasks were created correctly
    dag = dag_obj["dag"]

    # Get both tasks and verify they exist
    json_task = dag.get_task("http_task_json")
    plain_task = dag.get_task("http_task_plain")

    # Verify JSON task has callable data
    assert callable(json_task.data)

    # Verify JSON serialization works correctly
    json_result = json_task.data()
    assert isinstance(json_result, str)

    # Verify the serialized data contains the expected values
    assert '"message": "test data"' in json_result
    assert '"value": 123' in json_result

    # Convert back to Python object and verify structure
    parsed_data = json.loads(json_result)
    assert parsed_data == {"message": "test data", "value": 123}

    # Verify plain text task has string data
    assert plain_task.data == "plain text data"

    # Verify dependency
    assert plain_task.upstream_task_ids == {"http_task_json"}


@pytest.mark.skip
@pytest.mark.skipif(HttpOperator is None, reason=HTTP_OPERATOR_UNAVAILABLE_MSG)
def test_http_operator_from_yaml():
    """Test loading HttpOperator from a fixture YAML file"""
    from dagfactory import DagFactory

    # Load test fixture YAML content
    fixture_path = os.path.join(PROJECT_ROOT_PATH, "tests", "fixtures", "dag_factory_http_operator_task.yml")

    # Skip if fixture doesn't exist
    if not os.path.exists(fixture_path):
        pytest.skip(f"Test fixture not found: {fixture_path}")

    # Create DagFactory with fixture and build DAGs
    dag_factory = DagFactory(fixture_path)
    dags = {}

    # Call generate_dags to build all DAGs from the YAML file
    dag_factory.generate_dags(dags)

    # Now check if our DAG is in the result
    dag = dags.get("http_operator_example_dag")

    # Skip if DAG not found
    if not dag:
        pytest.skip("DAG not found in fixture")

    # Test JSON task
    json_task = dag.get_task("send_request_json")
    assert json_task.headers.get("Content-Type") == "application/json"
    assert callable(json_task.data)

    # Call the data callable to get the serialized JSON
    serialized_json = json_task.data()
    assert isinstance(serialized_json, str)

    # Parse the JSON to verify it's valid and contains expected data
    parsed_data = json.loads(serialized_json)
    assert parsed_data.get("data") == "fake_data"
    assert parsed_data.get("format") == "json"

    # Verify the original test fixture data was correctly serialized
    expected_dict = {"data": "fake_data", "format": "json"}
    assert parsed_data == expected_dict

    # Test plaintext task
    plain_task = dag.get_task("send_request_plain_text")
    assert plain_task.headers.get("Content-Type") == "text/plain"
    assert isinstance(plain_task.data, dict)

    # For non-JSON content type, data should remain a dict
    assert plain_task.data == {"data": "fake_data", "test": "plain_text"}
