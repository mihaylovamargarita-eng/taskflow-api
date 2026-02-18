"""Authentication integration tests."""

from fastapi.testclient import TestClient


def register_user(client: TestClient, email: str, password: str = "Password123") -> None:
    """Register a user in test setup."""
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201


def login_user(client: TestClient, email: str, password: str = "Password123") -> dict:
    """Login a user and return token payload."""
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_login_returns_access_and_refresh_tokens(client: TestClient) -> None:
    """Login should return both token types and allow profile access."""
    email = "auth1@example.com"
    register_user(client, email)
    token_data = login_user(client, email)

    assert token_data["token_type"] == "bearer"
    assert token_data["access_token"]
    assert token_data["refresh_token"]

    profile_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == email


def test_refresh_token_rotation_and_reuse_detection(client: TestClient) -> None:
    """Refresh should rotate token; reuse of old token should revoke sessions."""
    email = "auth2@example.com"
    register_user(client, email)
    token_data = login_user(client, email)

    first_refresh = token_data["refresh_token"]
    refresh_response = client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()

    assert refreshed["refresh_token"] != first_refresh
    assert refreshed["access_token"] != token_data["access_token"]

    reused_response = client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
    assert reused_response.status_code == 401
    assert "reuse detected" in reused_response.json()["detail"].lower()

    revoked_response = client.post("/api/auth/refresh", json={"refresh_token": refreshed["refresh_token"]})
    assert revoked_response.status_code == 401


def test_logout_revokes_active_refresh_sessions(client: TestClient) -> None:
    """Logout should revoke refresh sessions for the current user."""
    email = "auth3@example.com"
    register_user(client, email)
    token_data = login_user(client, email)

    logout_response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert logout_response.status_code == 204

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": token_data["refresh_token"]},
    )
    assert refresh_response.status_code == 401

