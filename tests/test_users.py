"""tests for user endpoints"""
from app.core.config import settings


def test_create_user(client):
    """test user registration"""
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewUser123!@#",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert "id" in data
    assert "hashed_password" not in data


def test_create_user_duplicate_email(client, test_user):
    """test user registration with duplicate email fails"""
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": "test@example.com",
            "username": "anotheruser",
            "password": "Test123!@#",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_create_user_duplicate_username(client, test_user):
    """test user registration with duplicate username fails"""
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": "another@example.com",
            "username": "testuser",
            "password": "Test123!@#",
        },
    )
    assert response.status_code == 400
    assert "already taken" in response.json()["detail"]


def test_login_success(client, test_user):
    """test successful login"""
    response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "testuser",
            "password": "Test123!@#",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    """test login with wrong password fails"""
    response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "testuser",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    """test login with nonexistent user fails"""
    response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "nonexistent",
            "password": "Test123!@#",
        },
    )
    assert response.status_code == 401


def test_get_current_user(client, auth_headers):
    """test getting current user info"""
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_get_current_user_unauthorized(client):
    """test getting current user without auth fails"""
    response = client.get(f"{settings.API_V1_STR}/users/me")
    assert response.status_code == 401


def test_update_user(client, auth_headers):
    """test updating user profile"""
    response = client.put(
        f"{settings.API_V1_STR}/users/me",
        headers=auth_headers,
        json={
            "display_name": "Test User",
            "bio": "This is my bio",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Test User"
    assert data["bio"] == "This is my bio"


def test_refresh_token(client, test_user):
    """test token refresh"""
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "testuser",
            "password": "Test123!@#",
        },
    )
    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        f"{settings.API_V1_STR}/users/token/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_logout(client, test_user):
    """test logout"""
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "testuser",
            "password": "Test123!@#",
        },
    )
    refresh_token = login_response.json()["refresh_token"]
    auth_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        f"{settings.API_V1_STR}/users/logout",
        headers=auth_headers,
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert "successfully logged out" in response.json()["message"].lower()