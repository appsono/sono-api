"""tests for admin endpoints"""

from app.core.config import settings


def test_admin_stats(client, admin_auth_headers):
    """admin stats endpoint should return system statistics"""
    response = client.get(
        f"{settings.API_V1_STR}/admin/stats",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "active_users" in data
    assert "total_audio_files" in data
    assert isinstance(data["total_users"], int)


def test_admin_stats_rejected_for_non_admin(client, auth_headers):
    """non-admin users should not access admin stats"""
    response = client.get(
        f"{settings.API_V1_STR}/admin/stats",
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_admin_stats_rejected_without_auth(client):
    """unauthenticated requests should not access admin stats"""
    response = client.get(f"{settings.API_V1_STR}/admin/stats")
    assert response.status_code == 401


def test_admin_get_user_details(client, admin_auth_headers, test_user):
    """admin should be able to view user details"""
    response = client.get(
        f"{settings.API_V1_STR}/admin/users/{test_user.id}",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == "testuser"


def test_admin_get_nonexistent_user(client, admin_auth_headers):
    """admin requesting nonexistent user gets 404"""
    response = client.get(
        f"{settings.API_V1_STR}/admin/users/99999",
        headers=admin_auth_headers,
    )
    assert response.status_code == 404


def test_admin_disable_user(client, admin_auth_headers, test_user, db_session):
    """admin should be able to disable a user"""
    response = client.post(
        f"{settings.API_V1_STR}/admin/users/{test_user.id}/disable",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    db_session.refresh(test_user)
    assert test_user.is_active is False


def test_admin_enable_user(client, admin_auth_headers, test_user, db_session):
    """admin should be able to re-enable a disabled user"""
    test_user.is_active = False
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/admin/users/{test_user.id}/enable",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_admin_cannot_disable_self(client, admin_auth_headers, test_superuser):
    """admin should not be able to disable their own account"""
    response = client.post(
        f"{settings.API_V1_STR}/admin/users/{test_superuser.id}/disable",
        headers=admin_auth_headers,
    )
    assert response.status_code == 400


def test_admin_disable_already_disabled(client, admin_auth_headers, test_user, db_session):
    """disabling an already-disabled user should fail"""
    test_user.is_active = False
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/admin/users/{test_user.id}/disable",
        headers=admin_auth_headers,
    )
    assert response.status_code == 400


def test_admin_collection_stats(client, admin_auth_headers):
    """admin collection stats endpoint should work"""
    response = client.get(
        f"{settings.API_V1_STR}/admin/collections/stats",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_collections" in data


def test_admin_update_upload_limit(client, admin_auth_headers, test_user):
    """admin should be able to update a user's upload limit"""
    response = client.put(
        f"{settings.API_V1_STR}/admin/users/{test_user.id}/upload-limit",
        headers=admin_auth_headers,
        json={"max_audio_uploads": 50},
    )
    assert response.status_code == 200
    assert response.json()["max_audio_uploads"] == 50


def test_admin_get_upload_stats(client, admin_auth_headers, test_user):
    """admin should be able to view user upload stats"""
    response = client.get(
        f"{settings.API_V1_STR}/admin/users/{test_user.id}/upload-stats",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "used_uploads" in data
    assert "max_uploads" in data
    assert "remaining_uploads" in data
