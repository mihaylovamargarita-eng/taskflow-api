"""Task API integration tests."""

from fastapi.testclient import TestClient


def register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    """Create user and return access and refresh tokens."""
    register_response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "Password123"},
    )
    assert login_response.status_code == 200
    payload = login_response.json()
    return payload["access_token"], payload["refresh_token"]


def auth_header(token: str) -> dict[str, str]:
    """Build bearer authorization header."""
    return {"Authorization": f"Bearer {token}"}


def test_task_crud_and_ownership(client: TestClient) -> None:
    """Verify task CRUD flow and ownership enforcement."""
    user1_access, _ = register_and_login(client, "task-user1@example.com")
    user2_access, _ = register_and_login(client, "task-user2@example.com")

    create_response = client.post(
        "/api/tasks",
        json={
            "title": "Prepare release",
            "description": "Create release candidate and validate",
            "priority": "high",
            "status": "todo",
        },
        headers=auth_header(user1_access),
    )
    assert create_response.status_code == 201
    task = create_response.json()
    task_id = task["id"]

    list_response = client.get(
        "/api/tasks",
        params={"status": "todo", "priority": "high", "skip": 0, "limit": 10},
        headers=auth_header(user1_access),
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    forbidden_response = client.get(f"/api/tasks/{task_id}", headers=auth_header(user2_access))
    assert forbidden_response.status_code == 403

    update_response = client.put(
        f"/api/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=auth_header(user1_access),
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "in_progress"

    delete_response = client.delete(f"/api/tasks/{task_id}", headers=auth_header(user1_access))
    assert delete_response.status_code == 204

    not_found_response = client.get(f"/api/tasks/{task_id}", headers=auth_header(user1_access))
    assert not_found_response.status_code == 404


def test_task_title_normalization_on_create_and_update(client: TestClient) -> None:
    """Task titles should be normalized during create and update operations."""
    user_access, _ = register_and_login(client, "task-normalize@example.com")

    create_response = client.post(
        "/api/tasks",
        json={"title": "   Build    API   contract   "},
        headers=auth_header(user_access),
    )
    assert create_response.status_code == 201
    task = create_response.json()
    assert task["title"] == "Build API contract"

    update_response = client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "  Finalize     docs  "},
        headers=auth_header(user_access),
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Finalize docs"


def test_task_update_rejects_empty_payload(client: TestClient) -> None:
    """Task update should reject payloads with no fields."""
    user_access, _ = register_and_login(client, "task-empty-update@example.com")
    create_response = client.post(
        "/api/tasks",
        json={"title": "Initial task"},
        headers=auth_header(user_access),
    )
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    empty_update_response = client.put(
        f"/api/tasks/{task_id}",
        json={},
        headers=auth_header(user_access),
    )
    assert empty_update_response.status_code == 400


def test_task_status_regression_and_done_immutability(client: TestClient) -> None:
    """Task status cannot regress and done tasks cannot be modified."""
    user_access, _ = register_and_login(client, "task-policy@example.com")
    create_response = client.post(
        "/api/tasks",
        json={"title": "Policy task", "status": "in_progress"},
        headers=auth_header(user_access),
    )
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    regression_response = client.put(
        f"/api/tasks/{task_id}",
        json={"status": "todo"},
        headers=auth_header(user_access),
    )
    assert regression_response.status_code == 409

    done_response = client.put(
        f"/api/tasks/{task_id}",
        json={"status": "done"},
        headers=auth_header(user_access),
    )
    assert done_response.status_code == 200

    done_update_response = client.put(
        f"/api/tasks/{task_id}",
        json={"description": "should fail"},
        headers=auth_header(user_access),
    )
    assert done_update_response.status_code == 409


def test_task_create_respects_per_user_limit(client: TestClient, monkeypatch) -> None:
    """Task creation should enforce per-user configured maximum."""
    monkeypatch.setattr("app.routers.tasks.settings.TASK_MAX_PER_USER", 1)
    user_access, _ = register_and_login(client, "task-limit@example.com")

    first = client.post(
        "/api/tasks",
        json={"title": "First"},
        headers=auth_header(user_access),
    )
    assert first.status_code == 201

    second = client.post(
        "/api/tasks",
        json={"title": "Second"},
        headers=auth_header(user_access),
    )
    assert second.status_code == 400


def test_task_payload_forbids_immutable_fields(client: TestClient) -> None:
    """Task create/update should reject unknown or immutable payload fields."""
    user_access, _ = register_and_login(client, "task-forbid@example.com")

    create_response = client.post(
        "/api/tasks",
        json={"title": "Task", "user_id": 999},
        headers=auth_header(user_access),
    )
    assert create_response.status_code == 422

    task_create = client.post(
        "/api/tasks",
        json={"title": "Task valid"},
        headers=auth_header(user_access),
    )
    assert task_create.status_code == 201
    task_id = task_create.json()["id"]

    update_response = client.put(
        f"/api/tasks/{task_id}",
        json={"created_at": "2020-01-01T00:00:00Z"},
        headers=auth_header(user_access),
    )
    assert update_response.status_code == 422
