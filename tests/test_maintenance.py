"""tests for maintenance mode"""

from app.core.config import settings
from app.core.maintenance_state import maintenance_state


def test_maintenance_status_public(client):
    """maintenance status endpoint should be publicly accessible"""
    response = client.get(f"{settings.API_V1_STR}/admin/maintenance/status")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "message" in data
    assert data["enabled"] is False


def test_enable_maintenance_admin(client, admin_auth_headers):
    """admin should be able to enable maintenance mode"""
    response = client.post(
        f"{settings.API_V1_STR}/admin/maintenance/enable",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True

    # clean up
    maintenance_state.disable()


def test_enable_maintenance_with_custom_message(client, admin_auth_headers):
    """admin should be able to set a custom maintenance message"""
    response = client.post(
        f"{settings.API_V1_STR}/admin/maintenance/enable?message=Upgrading%20database",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert "Upgrading database" in response.json()["message"]

    maintenance_state.disable()


def test_disable_maintenance_admin(client, admin_auth_headers):
    """admin should be able to disable maintenance mode"""
    maintenance_state.enable("test")

    response = client.post(
        f"{settings.API_V1_STR}/admin/maintenance/disable",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_toggle_maintenance(client, admin_auth_headers):
    """toggle endpoint should enable/disable maintenance"""
    response = client.post(
        f"{settings.API_V1_STR}/admin/maintenance/toggle",
        headers=admin_auth_headers,
        json={"enabled": True, "message": "Toggle test"},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True

    response = client.post(
        f"{settings.API_V1_STR}/admin/maintenance/toggle",
        headers=admin_auth_headers,
        json={"enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_maintenance_rejects_non_admin(client, auth_headers):
    """non-admin users should not be able to control maintenance mode"""
    response = client.post(
        f"{settings.API_V1_STR}/admin/maintenance/enable",
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_health_check_during_maintenance(client, admin_auth_headers):
    """health check should work even during maintenance"""
    maintenance_state.enable("test")

    response = client.get("/health")
    assert response.status_code == 200

    maintenance_state.disable()
