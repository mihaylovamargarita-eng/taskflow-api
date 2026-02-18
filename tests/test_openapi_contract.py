"""OpenAPI contract and backward-compatibility tests."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

BASELINE_PATH = Path("tests/contracts/openapi_backward_compat.json")


def _openapi() -> dict:
    """Return generated OpenAPI schema."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def _baseline() -> dict:
    """Load backward-compatibility baseline file."""
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_openapi_document_structure() -> None:
    """Generated OpenAPI should include expected top-level metadata."""
    schema = _openapi()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "TaskFlow API"
    assert schema["info"]["version"] == "1.0.0"
    assert "paths" in schema
    assert "components" in schema


def test_openapi_backward_compatibility_paths_and_methods() -> None:
    """Current API must preserve all baseline endpoint path/method contracts."""
    schema = _openapi()
    baseline = _baseline()

    for path, methods in baseline["required_paths"].items():
        assert path in schema["paths"], f"Missing path: {path}"
        for method in methods:
            assert method in schema["paths"][path], f"Missing method {method.upper()} for path {path}"


def test_openapi_backward_compatibility_required_schema_fields() -> None:
    """Current schema components must preserve baseline required fields."""
    schema = _openapi()
    baseline = _baseline()
    components = schema["components"]["schemas"]

    for schema_name, required_fields in baseline["required_schemas"].items():
        assert schema_name in components, f"Missing schema component: {schema_name}"
        component = components[schema_name]
        fields = set(component.get("properties", {}).keys())
        for field in required_fields:
            assert field in fields, f"Missing field '{field}' in schema {schema_name}"


def test_endpoint_error_contracts_reference_standard_error_response() -> None:
    """Protected endpoints should document standardized error response model."""
    schema = _openapi()
    paths = schema["paths"]

    checks = [
        ("/api/auth/login", "post", "401"),
        ("/api/auth/me", "get", "401"),
        ("/api/tasks", "post", "422"),
        ("/api/tasks/{task_id}", "put", "409"),
        ("/api/admin/users", "get", "403"),
    ]
    for path, method, status_code in checks:
        response_schema = (
            paths[path][method]["responses"][status_code]["content"]["application/json"]["schema"]["$ref"]
        )
        assert response_schema == "#/components/schemas/ErrorResponse"

