"""tests for user endpoints"""

from datetime import datetime, timedelta, timezone
from app.core.config import settings


# ============= ORIGINAL TESTS =============


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


def test_old_access_token_rejected_after_invalidation(client, test_user, db_session):
    # login to get a token
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "testuser", "password": "Test123!@#"},
    )
    assert login_response.status_code == 200
    old_access_token = login_response.json()["access_token"]

    # verify the token works before invalidation
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert response.status_code == 200

    # simulate password reset => sets token_invalidated_at
    test_user.token_invalidated_at = datetime.now(timezone.utc)
    db_session.commit()

    # old token should now be rejected
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert response.status_code == 401


def test_old_refresh_token_rejected_after_invalidation(client, test_user, db_session):
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "testuser", "password": "Test123!@#"},
    )
    assert login_response.status_code == 200
    old_refresh_token = login_response.json()["refresh_token"]

    # invalidate all tokens (as password reset would)
    test_user.token_invalidated_at = datetime.now(timezone.utc)
    db_session.commit()

    # old refresh token should be rejected
    response = client.post(
        f"{settings.API_V1_STR}/users/token/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert response.status_code == 401


def test_new_token_works_after_invalidation(client, test_user, db_session):
    # invalidate existing tokens
    test_user.token_invalidated_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db_session.commit()

    # login again => new token issued after invalidation timestamp
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "testuser", "password": "Test123!@#"},
    )
    assert login_response.status_code == 200
    new_token = login_response.json()["access_token"]

    # new token should work fine
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert response.status_code == 200


def test_revoke_all_user_tokens_sets_timestamp(client, test_user, db_session):
    from app import crud

    assert test_user.token_invalidated_at is None

    crud.revoke_all_user_tokens(db_session, test_user.id, reason="test")

    db_session.refresh(test_user)
    assert test_user.token_invalidated_at is not None
    # SQLite strips tzinfo, so normalize before comparing
    invalidated_at = test_user.token_invalidated_at
    if invalidated_at.tzinfo is None:
        invalidated_at = invalidated_at.replace(tzinfo=timezone.utc)
    assert invalidated_at <= datetime.now(timezone.utc)


def test_verify_expired_reset_token_rejected(client, test_user, db_session):
    from app import models

    expired_token = models.PasswordResetToken(
        user_id=test_user.id,
        token="expired-test-token-12345",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        is_valid=True,
    )
    db_session.add(expired_token)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/users/verify-reset-token",
        json={"token": "expired-test-token-12345"},
    )
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_verify_valid_reset_token_accepted(client, test_user, db_session):
    from app import models

    valid_token = models.PasswordResetToken(
        user_id=test_user.id,
        token="valid-test-token-12345",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_valid=True,
    )
    db_session.add(valid_token)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/users/verify-reset-token",
        json={"token": "valid-test-token-12345"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_verify_used_reset_token_rejected(client, test_user, db_session):
    """used reset tokens should be rejected"""
    from app import models

    used_token = models.PasswordResetToken(
        user_id=test_user.id,
        token="used-test-token-12345",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_valid=False,
        used_at=datetime.now(timezone.utc),
    )
    db_session.add(used_token)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/users/verify-reset-token",
        json={"token": "used-test-token-12345"},
    )
    assert response.status_code == 400
    assert "already been used" in response.json()["detail"].lower()


def test_refresh_token_rejected_for_disabled_user(client, test_user, db_session):
    # login while user is still active
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "testuser", "password": "Test123!@#"},
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    # admin disables the user
    test_user.is_active = False
    db_session.commit()

    # attempt to refresh should fail
    response = client.post(
        f"{settings.API_V1_STR}/users/token/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


def test_login_rejected_for_disabled_user(client, inactive_test_user):
    """disabled users cannot login"""
    response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "inactiveuser", "password": "Inactive123!@#"},
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


def test_list_users_as_admin(client, admin_auth_headers, test_user):
    response = client.get(
        f"{settings.API_V1_STR}/users/",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # should contain at least the admin user and the test user
    assert len(data) >= 2


def test_list_users_rejected_for_non_admin(client, auth_headers):
    """GET /users/ should reject non-admin users"""
    response = client.get(
        f"{settings.API_V1_STR}/users/",
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_list_users_rejected_without_auth(client):
    """GET /users/ should reject unauthenticated requests"""
    response = client.get(f"{settings.API_V1_STR}/users/")
    assert response.status_code == 401


def test_password_reset_invalidates_sessions(client, test_user, db_session):
    from app import models

    # login to get tokens
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "testuser", "password": "Test123!@#"},
    )
    assert login_response.status_code == 200
    old_access_token = login_response.json()["access_token"]

    # create a valid reset token
    reset_token = models.PasswordResetToken(
        user_id=test_user.id,
        token="reset-session-test-token",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_valid=True,
    )
    db_session.add(reset_token)
    db_session.commit()

    # perform password reset
    response = client.post(
        f"{settings.API_V1_STR}/users/reset-password",
        json={
            "token": "reset-session-test-token",
            "new_password": "NewSecure123!@#",
        },
    )
    assert response.status_code == 200

    # old access token should now be rejected
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert response.status_code == 401

    # login with new password should work
    login_response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={"username": "testuser", "password": "NewSecure123!@#"},
    )
    assert login_response.status_code == 200


# ============= PASSWORD VALIDATION TESTS =============


def test_create_user_weak_password_no_uppercase(client):
    """password without uppercase should be rejected"""
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "weakpass123!",
        },
    )
    assert response.status_code == 422


def test_create_user_weak_password_no_special(client):
    """password without special character should be rejected"""
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "WeakPass123",
        },
    )
    assert response.status_code == 422


def test_create_user_weak_password_too_short(client):
    """password shorter than 8 chars should be rejected"""
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "Ab1!",
        },
    )
    assert response.status_code == 422


# ============= SEARCH USERS =============


def test_search_users(client, auth_headers, test_superuser):
    """search for users by username"""
    response = client.get(
        f"{settings.API_V1_STR}/users/search?query=admin",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(u["username"] == "adminuser" for u in data)


def test_search_users_query_too_short(client, auth_headers):
    """search with query < 2 chars should fail"""
    response = client.get(
        f"{settings.API_V1_STR}/users/search?query=a",
        headers=auth_headers,
    )
    assert response.status_code == 400
