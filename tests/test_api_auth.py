"""Integration tests for STMS authentication API endpoints."""

from fastapi import status


def test_login_success(test_client, admin_user):
    """Login should return access token for valid credentials."""
    response = test_client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "testpassword"}
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["username"] == "admin"


def test_login_invalid_credentials(test_client):
    """Login should fail with 401 when credentials are invalid."""
    response = test_client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "wrongpassword"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_endpoint_without_token_is_unauthorized(test_client):
    """Accessing a protected endpoint without token should return 401."""
    response = test_client.get("/api/v1/density/realtime")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
