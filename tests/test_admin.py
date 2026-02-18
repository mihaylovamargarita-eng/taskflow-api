"""Admin RBAC integration tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserRole


def _auth_header(token: str) -> dict[str, str]:
    """Build bearer header."""
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str, password: str = "Password123") -> None:
    """Register a user for tests."""
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201


def _login(client: TestClient, email: str, password: str = "Password123") -> str:
    """Login and return access token."""
    response = client.post("/api/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _set_user_role(db: Session, email: str, role: UserRole) -> None:
    """Set user role directly in test database."""
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    user.role = role
    db.add(user)
    db.commit()


def test_non_admin_cannot_access_admin_routes(client: TestClient) -> None:
    """Regular users should receive 403 on admin routes."""
    email = "rbac-user@example.com"
    _register(client, email)
    access_token = _login(client, email)

    response = client.get("/api/admin/users", headers=_auth_header(access_token))
    assert response.status_code == 403


def test_admin_can_manage_users_and_stats(client: TestClient, db_session: Session) -> None:
    """Admin users should access admin APIs and manage user roles/status."""
    admin_email = "rbac-admin@example.com"
    target_email = "rbac-target@example.com"
    _register(client, admin_email)
    _register(client, target_email)
    _set_user_role(db_session, admin_email, UserRole.ADMIN)

    admin_token = _login(client, admin_email)

    list_response = client.get("/api/admin/users", headers=_auth_header(admin_token))
    assert list_response.status_code == 200
    users = list_response.json()
    assert any(user["email"] == admin_email and user["role"] == "admin" for user in users)
    target_user = next(user for user in users if user["email"] == target_email)

    role_response = client.patch(
        f"/api/admin/users/{target_user['id']}/role",
        json={"role": "admin"},
        headers=_auth_header(admin_token),
    )
    assert role_response.status_code == 200
    assert role_response.json()["role"] == "admin"

    status_response = client.patch(
        f"/api/admin/users/{target_user['id']}/status",
        json={"is_active": False},
        headers=_auth_header(admin_token),
    )
    assert status_response.status_code == 200
    assert status_response.json()["is_active"] is False

    deactivated_login = client.post(
        "/api/auth/login",
        data={"username": target_email, "password": "Password123"},
    )
    assert deactivated_login.status_code == 401

    stats_response = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert stats_response.status_code == 200
    stats_payload = stats_response.json()
    assert stats_payload["total_users"] >= 2
    assert "total_tasks" in stats_payload
    assert "active_refresh_sessions" in stats_payload
