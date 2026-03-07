"""tests for audio file endpoints"""

from io import BytesIO
from unittest import mock
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


def test_upload_rejects_octet_stream(client, auth_headers):
    fake_exe = BytesIO(b"MZ\x90\x00" + b"\x00" * 100)
    response = client.post(
        f"{settings.API_V1_STR}/audio/upload",
        headers=auth_headers,
        files={"file": ("malware.exe", fake_exe, "application/octet-stream")},
        data={"title": "definitely not malware"},
    )
    assert response.status_code == 400
    assert "Unsupported audio format" in response.json()["detail"]


def test_upload_rejects_html(client, auth_headers):
    """HTML files must be rejected to prevent stored XSS via audio endpoint"""
    html_content = BytesIO(b"<html><script>alert('xss')</script></html>")
    response = client.post(
        f"{settings.API_V1_STR}/audio/upload",
        headers=auth_headers,
        files={"file": ("page.html", html_content, "text/html")},
        data={"title": "xss payload"},
    )
    assert response.status_code == 400


def test_upload_rejects_javascript(client, auth_headers):
    """JavaScript files must be rejected"""
    js_content = BytesIO(b"alert('xss')")
    response = client.post(
        f"{settings.API_V1_STR}/audio/upload",
        headers=auth_headers,
        files={"file": ("script.js", js_content, "application/javascript")},
        data={"title": "js payload"},
    )
    assert response.status_code == 400


def test_upload_accepts_valid_mp3(client, auth_headers):
    """valid audio/mpeg content type should be accepted (if MinIO works)"""
    # MinIO will fail in test env, but we should get past the content-type check
    fake_mp3 = BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    with mock.patch("app.routers.audio.minio_client") as mock_minio:
        mock_minio.put_object.return_value = None
        response = client.post(
            f"{settings.API_V1_STR}/audio/upload",
            headers=auth_headers,
            files={"file": ("song.mp3", fake_mp3, "audio/mpeg")},
            data={"title": "valid song"},
        )
        # should get past validation (200 if minio mock works, not 400)
        assert response.status_code != 400 or "Unsupported audio format" not in response.json().get("detail", "")


def test_upload_accepts_valid_wav(client, auth_headers):
    """valid audio/wav content type should pass format validation"""
    fake_wav = BytesIO(b"RIFF" + b"\x00" * 100)
    with mock.patch("app.routers.audio.minio_client") as mock_minio:
        mock_minio.put_object.return_value = None
        response = client.post(
            f"{settings.API_V1_STR}/audio/upload",
            headers=auth_headers,
            files={"file": ("sound.wav", fake_wav, "audio/wav")},
            data={"title": "valid wav"},
        )
        assert response.status_code != 400 or "Unsupported audio format" not in response.json().get("detail", "")


def test_upload_rejects_empty_file(client, auth_headers):
    """empty files should be rejected"""
    empty = BytesIO(b"")
    response = client.post(
        f"{settings.API_V1_STR}/audio/upload",
        headers=auth_headers,
        files={"file": ("empty.mp3", empty, "audio/mpeg")},
        data={"title": "empty"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


# ============= UPLOAD LIMIT TESTS =============


def test_upload_limit_enforced(client, auth_headers, test_user, db_session):
    """users with 0 remaining uploads should be rejected"""
    test_user.max_audio_uploads = 0
    db_session.commit()

    fake_mp3 = BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    response = client.post(
        f"{settings.API_V1_STR}/audio/upload",
        headers=auth_headers,
        files={"file": ("song.mp3", fake_mp3, "audio/mpeg")},
        data={"title": "over limit"},
    )
    assert response.status_code == 403
    assert "Upload limit reached" in response.json()["detail"]
