"""tests for health check and root endpoints"""

from app.core.config import settings


def test_root_endpoint(client):
    """test root endpoint => returns OK"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "OK"}


def test_health_check(client):
    """test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project_name"] == settings.PROJECT_NAME
    assert data["version"] == "1.0.0"
