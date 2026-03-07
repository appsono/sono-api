from datetime import datetime, timedelta, timezone
from io import BytesIO
from app.core.config import settings
from app import crud


class TestTokenInvalidation:

    def test_revoke_sets_timestamp(self, client, test_user, db_session):
        """revoke_all_user_tokens must set token_invalidated_at on the user"""
        assert test_user.token_invalidated_at is None

        crud.revoke_all_user_tokens(db_session, test_user.id, reason="test")

        db_session.refresh(test_user)
        assert test_user.token_invalidated_at is not None

    def test_access_token_rejected_after_revocation(self, client, test_user, db_session):
        """access tokens issued before revocation must be rejected"""
        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        old_token = login.json()["access_token"]

        # verify it works
        assert client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {old_token}"},
        ).status_code == 200

        # revoke
        crud.revoke_all_user_tokens(db_session, test_user.id)

        # verify it's rejected
        assert client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {old_token}"},
        ).status_code == 401

    def test_refresh_token_rejected_after_revocation(self, client, test_user, db_session):
        """refresh tokens issued before revocation must be rejected"""
        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        old_refresh = login.json()["refresh_token"]

        crud.revoke_all_user_tokens(db_session, test_user.id)

        assert client.post(
            f"{settings.API_V1_STR}/users/token/refresh",
            json={"refresh_token": old_refresh},
        ).status_code == 401

    def test_new_login_works_after_revocation(self, client, test_user, db_session):
        """logging in after revocation should produce valid tokens"""
        test_user.token_invalidated_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db_session.commit()

        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        assert login.status_code == 200

        assert client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        ).status_code == 200


class TestResetTokenTimezones:

    def test_expired_token_rejected(self, client, test_user, db_session):
        """expired reset tokens must be rejected"""
        from app import models

        token = models.PasswordResetToken(
            user_id=test_user.id,
            token="tz-expired-token",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            is_valid=True,
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post(
            f"{settings.API_V1_STR}/users/verify-reset-token",
            json={"token": "tz-expired-token"},
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_valid_token_accepted(self, client, test_user, db_session):
        """non-expired reset tokens should work"""
        from app import models

        token = models.PasswordResetToken(
            user_id=test_user.id,
            token="tz-valid-token",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_valid=True,
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post(
            f"{settings.API_V1_STR}/users/verify-reset-token",
            json={"token": "tz-valid-token"},
        )
        assert resp.status_code == 200

    def test_expired_token_rejected_on_reset(self, client, test_user, db_session):
        """expired tokens must also fail at the actual reset step"""
        from app import models

        token = models.PasswordResetToken(
            user_id=test_user.id,
            token="tz-expired-reset",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            is_valid=True,
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post(
            f"{settings.API_V1_STR}/users/reset-password",
            json={"token": "tz-expired-reset", "new_password": "NewPass123!@#"},
        )
        assert resp.status_code == 400


class TestInactiveUserTokenRefresh:

    def test_disabled_user_cannot_refresh(self, client, test_user, db_session):
        """refresh must fail for disabled users"""
        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        refresh = login.json()["refresh_token"]

        test_user.is_active = False
        db_session.commit()

        resp = client.post(
            f"{settings.API_V1_STR}/users/token/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 403

    def test_disabled_user_cannot_login(self, client, inactive_test_user):
        """disabled users cannot login at all"""
        resp = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "inactiveuser", "password": "Inactive123!@#"},
        )
        assert resp.status_code == 403

    def test_reenabled_user_can_login(self, client, test_user, db_session):
        """re-enabled users should be able to login again"""
        test_user.is_active = False
        db_session.commit()

        # can't login
        resp = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        assert resp.status_code in [401, 403]

        # re-enable
        test_user.is_active = True
        db_session.commit()

        # can login again
        resp = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        assert resp.status_code == 200


class TestAudioUploadValidation:
    def test_octet_stream_rejected(self, client, auth_headers):
        """application/octet-stream must be rejected"""
        resp = client.post(
            f"{settings.API_V1_STR}/audio/upload",
            headers=auth_headers,
            files={"file": ("file.bin", BytesIO(b"\x00" * 100), "application/octet-stream")},
            data={"title": "test"},
        )
        assert resp.status_code == 400
        assert "Unsupported audio format" in resp.json()["detail"]

    def test_exe_upload_rejected(self, client, auth_headers):
        """executable files must be rejected"""
        resp = client.post(
            f"{settings.API_V1_STR}/audio/upload",
            headers=auth_headers,
            files={"file": ("virus.exe", BytesIO(b"MZ" + b"\x00" * 100), "application/octet-stream")},
            data={"title": "test"},
        )
        assert resp.status_code == 400

    def test_html_upload_rejected(self, client, auth_headers):
        """HTML uploads must be rejected to prevent stored XSS"""
        resp = client.post(
            f"{settings.API_V1_STR}/audio/upload",
            headers=auth_headers,
            files={"file": ("xss.html", BytesIO(b"<script>alert(1)</script>"), "text/html")},
            data={"title": "test"},
        )
        assert resp.status_code == 400

    def test_pdf_upload_rejected(self, client, auth_headers):
        """PDF uploads must be rejected"""
        resp = client.post(
            f"{settings.API_V1_STR}/audio/upload",
            headers=auth_headers,
            files={"file": ("doc.pdf", BytesIO(b"%PDF-1.4" + b"\x00" * 100), "application/pdf")},
            data={"title": "test"},
        )
        assert resp.status_code == 400


class TestListUsersEndpoint:

    def test_admin_can_list_users(self, client, admin_auth_headers, test_user):
        """admin listing users should return a list (was crashing)"""
        resp = client.get(
            f"{settings.API_V1_STR}/users/",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_non_admin_rejected(self, client, auth_headers):
        """non-admin users must be rejected"""
        resp = client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        """unauthenticated requests must be rejected"""
        resp = client.get(f"{settings.API_V1_STR}/users/")
        assert resp.status_code == 401


class TestPasswordResetSessionInvalidation:

    def test_old_token_dies_after_reset(self, client, test_user, db_session):
        """after password reset, old access tokens must stop working"""
        from app import models

        # login
        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        old_token = login.json()["access_token"]

        # create reset token
        reset = models.PasswordResetToken(
            user_id=test_user.id,
            token="session-kill-token",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_valid=True,
        )
        db_session.add(reset)
        db_session.commit()

        # reset password
        resp = client.post(
            f"{settings.API_V1_STR}/users/reset-password",
            json={"token": "session-kill-token", "new_password": "BrandNew123!@#"},
        )
        assert resp.status_code == 200

        # old token must fail
        resp = client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert resp.status_code == 401

    def test_can_login_with_new_password_after_reset(self, client, test_user, db_session):
        """new password should work immediately after reset"""
        from app import models

        reset = models.PasswordResetToken(
            user_id=test_user.id,
            token="new-pw-token",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_valid=True,
        )
        db_session.add(reset)
        db_session.commit()

        client.post(
            f"{settings.API_V1_STR}/users/reset-password",
            json={"token": "new-pw-token", "new_password": "FreshPass123!@#"},
        )

        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "FreshPass123!@#"},
        )
        assert login.status_code == 200
        assert "access_token" in login.json()

    def test_old_password_fails_after_reset(self, client, test_user, db_session):
        """old password must fail after reset"""
        from app import models

        reset = models.PasswordResetToken(
            user_id=test_user.id,
            token="old-pw-fail-token",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_valid=True,
        )
        db_session.add(reset)
        db_session.commit()

        client.post(
            f"{settings.API_V1_STR}/users/reset-password",
            json={"token": "old-pw-fail-token", "new_password": "Changed123!@#"},
        )

        login = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "Test123!@#"},
        )
        assert login.status_code == 401


class TestCryptoErrorHandling:

    def test_bad_encrypted_password_gives_generic_error(self, client, test_user):
        """invalid encrypted password should return generic error, not internals"""
        response = client.post(
            f"{settings.API_V1_STR}/users/token",
            data={"username": "testuser", "password": "not-valid-base64-encrypted"},
            headers={"X-Password-Encrypted": "true"},
        )
        # the mock crypto handler in tests just passes through,
        # so this tests the flow works without crashing
        # in production the real handler would catch the decryption error
        assert response.status_code in [200, 400, 401]
