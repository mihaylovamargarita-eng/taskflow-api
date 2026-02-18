"""Health endpoint integration tests."""

from fastapi.testclient import TestClient


def test_liveness_endpoint(client: TestClient) -> None:
    """Liveness endpoint should return healthy response with request id."""
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("X-Request-ID")


def test_readiness_endpoint(client: TestClient) -> None:
    """Readiness endpoint should verify database readiness."""
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

