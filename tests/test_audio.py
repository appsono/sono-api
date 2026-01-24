"""tests for audio file endpoints"""
from app.core.config import settings


def test_get_upload_stats(client, auth_headers):
    """test getting upload statistics"""
    response = client.get(
        f"{settings.API_V1_STR}/audio/stats",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "used_uploads" in data
    assert "max_uploads" in data
    assert "remaining_uploads" in data
    assert isinstance(data["used_uploads"], int)
    assert isinstance(data["max_uploads"], int)
    assert isinstance(data["remaining_uploads"], int)


def test_get_upload_stats_unauthorized(client):
    """test getting upload stats without auth fails"""
    response = client.get(f"{settings.API_V1_STR}/audio/stats")
    assert response.status_code == 401


def test_get_audio_files_list(client, auth_headers):
    """test getting list of audio files"""
    response = client.get(
        f"{settings.API_V1_STR}/audio/my-files",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert "total" in data
    assert "has_more" in data
    assert isinstance(data["files"], list)


def test_get_audio_files_list_unauthorized(client):
    """test getting audio files without auth fails"""
    response = client.get(f"{settings.API_V1_STR}/audio/my-files")
    assert response.status_code == 401


def test_get_public_audio_files(client):
    """test getting public audio files without auth"""
    response = client.get(f"{settings.API_V1_STR}/audio/public")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_nonexistent_audio_file(client, auth_headers):
    """test getting nonexistent audio file returns 404"""
    response = client.get(
        f"{settings.API_V1_STR}/audio/99999",
        headers=auth_headers,
    )
    assert response.status_code == 404