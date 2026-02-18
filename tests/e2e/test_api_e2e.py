"""End-to-end tests against a running TaskFlow API instance."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass

import httpx
import pytest

BASE_URL = os.getenv("E2E_BASE_URL")
TIMEOUT_SECONDS = float(os.getenv("E2E_TIMEOUT_SECONDS", "20"))
READY_WAIT_SECONDS = float(os.getenv("E2E_READY_WAIT_SECONDS", "60"))
E2E_ENABLED = os.getenv("E2E_ENABLED", "0").lower() in {"1", "true", "yes"}

if not E2E_ENABLED:
    pytest.skip(
        "E2E tests disabled. Set E2E_ENABLED=1 to run them.",
        allow_module_level=True,
    )

if not BASE_URL:
    pytest.skip(
        "E2E tests require E2E_BASE_URL (example: http://localhost:8000).",
        allow_module_level=True,
    )


@dataclass
class AuthSession:
    """Authentication token bundle used in e2e test flows."""

    access_token: str
    refresh_token: str


def _client() -> httpx.Client:
    """Create an HTTP client for the running API."""
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS)


def _unique_email(prefix: str) -> str:
    """Generate unique email values to avoid collisions across runs."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _bearer(token: str) -> dict[str, str]:
    """Build bearer authorization header."""
    return {"Authorization": f"Bearer {token}"}


def _register(client: httpx.Client, email: str, password: str = "Password123") -> dict:
    """Register a new user."""
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: httpx.Client, email: str, password: str = "Password123") -> AuthSession:
    """Login and return access/refresh tokens."""
    response = client.post("/api/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return AuthSession(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
    )


@pytest.fixture(scope="module", autouse=True)
def wait_for_api_ready() -> None:
    """Wait until the target API is reachable and ready."""
    deadline = time.time() + READY_WAIT_SECONDS
    last_error = "API readiness check did not run."
    with _client() as client:
        while time.time() < deadline:
            try:
                response = client.get("/api/health/ready")
                if response.status_code == 200:
                    return
                last_error = f"Unexpected status: {response.status_code} body={response.text}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(1)
    pytest.fail(f"API not ready within {READY_WAIT_SECONDS}s. Last error: {last_error}")


@pytest.mark.e2e
def test_health_endpoints_e2e() -> None:
    """Health probes should respond successfully on running stack."""
    with _client() as client:
        live = client.get("/api/health/live")
        assert live.status_code == 200, live.text
        assert live.json()["status"] == "ok"

        ready = client.get("/api/health/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ok"


@pytest.mark.e2e
def test_auth_lifecycle_e2e() -> None:
    """Exercise full auth lifecycle: register/login/me/refresh/reuse/logout."""
    email = _unique_email("e2e-auth")
    with _client() as client:
        _register(client, email)
        session = _login(client, email)

        me = client.get("/api/auth/me", headers=_bearer(session.access_token))
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email

        refreshed = client.post(
            "/api/auth/refresh",
            json={"refresh_token": session.refresh_token},
        )
        assert refreshed.status_code == 200, refreshed.text
        refreshed_payload = refreshed.json()
        assert refreshed_payload["refresh_token"] != session.refresh_token
        assert refreshed_payload["access_token"] != session.access_token

        reused = client.post(
            "/api/auth/refresh",
            json={"refresh_token": session.refresh_token},
        )
        assert reused.status_code == 401, reused.text

        revoked = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refreshed_payload["refresh_token"]},
        )
        assert revoked.status_code == 401, revoked.text

        second_session = _login(client, email)
        logout = client.post("/api/auth/logout", headers=_bearer(second_session.access_token))
        assert logout.status_code == 204, logout.text

        refresh_after_logout = client.post(
            "/api/auth/refresh",
            json={"refresh_token": second_session.refresh_token},
        )
        assert refresh_after_logout.status_code == 401, refresh_after_logout.text


@pytest.mark.e2e
def test_tasks_lifecycle_and_boundaries_e2e() -> None:
    """Exercise task CRUD, filtering, pagination, and ownership checks."""
    owner_email = _unique_email("e2e-owner")
    other_email = _unique_email("e2e-other")

    with _client() as client:
        _register(client, owner_email)
        _register(client, other_email)
        owner = _login(client, owner_email)
        other = _login(client, other_email)

        create_1 = client.post(
            "/api/tasks",
            headers=_bearer(owner.access_token),
            json={
                "title": "Design API docs",
                "description": "Write contract-first docs",
                "status": "todo",
                "priority": "high",
            },
        )
        assert create_1.status_code == 201, create_1.text
        task_1 = create_1.json()

        create_2 = client.post(
            "/api/tasks",
            headers=_bearer(owner.access_token),
            json={
                "title": "Prepare release notes",
                "description": "Summarize major changes",
                "status": "in_progress",
                "priority": "medium",
            },
        )
        assert create_2.status_code == 201, create_2.text
        task_2 = create_2.json()

        filtered = client.get(
            "/api/tasks",
            headers=_bearer(owner.access_token),
            params={"status": "todo", "priority": "high", "skip": 0, "limit": 10},
        )
        assert filtered.status_code == 200, filtered.text
        filtered_items = filtered.json()
        assert len(filtered_items) == 1
        assert filtered_items[0]["id"] == task_1["id"]

        paged = client.get(
            "/api/tasks",
            headers=_bearer(owner.access_token),
            params={"skip": 0, "limit": 1},
        )
        assert paged.status_code == 200, paged.text
        assert len(paged.json()) == 1

        forbidden = client.get(f"/api/tasks/{task_1['id']}", headers=_bearer(other.access_token))
        assert forbidden.status_code == 403, forbidden.text

        update = client.put(
            f"/api/tasks/{task_2['id']}",
            headers=_bearer(owner.access_token),
            json={"status": "done", "priority": "low"},
        )
        assert update.status_code == 200, update.text
        updated_task = update.json()
        assert updated_task["status"] == "done"
        assert updated_task["priority"] == "low"

        delete = client.delete(f"/api/tasks/{task_1['id']}", headers=_bearer(owner.access_token))
        assert delete.status_code == 204, delete.text

        missing = client.get(f"/api/tasks/{task_1['id']}", headers=_bearer(owner.access_token))
        assert missing.status_code == 404, missing.text
