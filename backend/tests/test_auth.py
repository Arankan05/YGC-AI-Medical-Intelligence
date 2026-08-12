import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from supabase_auth.errors import AuthApiError

from app.core.config import Settings, get_settings
from app.core.security import (
    get_current_application_user,
    get_current_user,
    validate_supabase_token,
)
from app.db.database import get_db
from app.main import app
from app.models.user import User
from app.schemas.auth import AuthenticatedUser

# In-memory SQLite engine for test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

TEST_JWT_SECRET = "super-secret-test-jwt-key-for-medi-guardian-ai-tests-32bytes"


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite:///:memory:",
        SUPABASE_URL="https://mockproject.supabase.co",
        SUPABASE_KEY="mock-anon-key-12345",
        SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
        SUPABASE_JWT_ALGORITHM="HS256",
        SUPABASE_JWT_AUDIENCE="authenticated",
    )


class AuthTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create all tables on SQLite
        User.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        User.metadata.drop_all(bind=test_engine)

    def setUp(self):
        self.db = TestSessionLocal()
        self.settings = get_test_settings()

        # Create sample user in DB
        self.user_uuid = uuid.uuid4()
        self.user_email = f"user_{self.user_uuid.hex[:8]}@example.com"
        self.db_user = User(
            id=self.user_uuid,
            email=self.user_email,
        )
        self.db.add(self.db_user)
        self.db.commit()
        self.db.refresh(self.db_user)

        # Setup FastAPI TestClient with overrides
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_settings():
            return self.settings

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = override_get_settings
        self.client = TestClient(app)

    def tearDown(self):
        # Clean up database records
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()
        app.dependency_overrides.clear()

    def _create_token(
        self,
        sub: str,
        email: str,
        secret: str = TEST_JWT_SECRET,
        algorithm: str = "HS256",
        audience: str = "authenticated",
        expires_in: int = 3600,
    ) -> str:
        payload = {
            "sub": sub,
            "email": email,
            "aud": audience,
            "role": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in,
            "app_metadata": {"provider": "email"},
            "user_metadata": {"full_name": "Test User"},
        }
        return jwt.encode(payload, secret, algorithm=algorithm)

    def test_get_me_unauthorized_when_no_token(self):
        """Requests without Authorization header must receive HTTP 401."""
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("WWW-Authenticate", response.headers)
        self.assertIn("detail", response.json())

    def test_get_me_unauthorized_when_invalid_scheme(self):
        """Requests with non-Bearer authentication must receive HTTP 401."""
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_unauthorized_when_malformed_token(self):
        """Requests with invalid/malformed token must receive HTTP 401."""
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not-a-valid-jwt-token"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_unauthorized_when_expired_token(self):
        """Requests with expired tokens must receive HTTP 401."""
        token = self._create_token(
            sub=str(self.user_uuid),
            email=self.user_email,
            expires_in=-60,  # Expired 60s ago
        )
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("expired", response.json()["detail"].lower())

    def test_get_me_unauthorized_when_invalid_signature(self):
        """Requests signed with wrong secret must receive HTTP 401."""
        token = self._create_token(
            sub=str(self.user_uuid),
            email=self.user_email,
            secret="wrong-secret-key-that-does-not-match-settings-32b",
        )
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_unauthorized_when_invalid_audience(self):
        """Tokens with mismatched audience claim must receive HTTP 401."""
        token = self._create_token(
            sub=str(self.user_uuid),
            email=self.user_email,
            audience="unauthorized-aud",
        )
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_unauthorized_when_user_not_in_db(self):
        """Valid token for an unregistered user must receive HTTP 401."""
        unregistered_uuid = str(uuid.uuid4())
        token = self._create_token(
            sub=unregistered_uuid,
            email="unregistered@example.com",
        )
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_get_me_success_with_valid_token(self):
        """Authenticated application user can retrieve their safe profile."""
        token = self._create_token(
            sub=str(self.user_uuid),
            email=self.user_email,
        )
        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], str(self.user_uuid))
        self.assertEqual(data["email"], self.user_email)

        # Ensure no sensitive credentials or keys are exposed
        forbidden_keys = [
            "password",
            "token",
            "secret",
            "service_role",
            "jwt_secret",
            "access_token",
            "refresh_token",
        ]
        for key in forbidden_keys:
            self.assertNotIn(key, data)

    def test_tenant_isolation(self):
        """User A's token can only access User A's identity and never User B's."""
        # Create User B in DB
        user_b_uuid = uuid.uuid4()
        user_b_email = "user_b@example.com"
        user_b = User(id=user_b_uuid, email=user_b_email)
        self.db.add(user_b)
        self.db.commit()

        # Token for User A
        token_a = self._create_token(sub=str(self.user_uuid), email=self.user_email)
        res_a = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        self.assertEqual(res_a.json()["id"], str(self.user_uuid))
        self.assertEqual(res_a.json()["email"], self.user_email)
        self.assertNotEqual(res_a.json()["id"], str(user_b_uuid))

        # Token for User B
        token_b = self._create_token(sub=str(user_b_uuid), email=user_b_email)
        res_b = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        self.assertEqual(res_b.json()["id"], str(user_b_uuid))
        self.assertEqual(res_b.json()["email"], user_b_email)
        self.assertNotEqual(res_b.json()["id"], str(self.user_uuid))

    def test_empty_or_whitespace_token_raises_401(self):
        """Passing empty or whitespace token directly raises 401."""
        with self.assertRaises(HTTPException) as ctx:
            validate_supabase_token("", self.settings)
        self.assertEqual(ctx.exception.status_code, 401)

        with self.assertRaises(HTTPException) as ctx:
            validate_supabase_token("   ", self.settings)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwt_missing_sub_raises_401(self):
        """Token with missing 'sub' claim raises 401."""
        payload = {
            "email": self.user_email,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        with self.assertRaises(HTTPException) as ctx:
            validate_supabase_token(token, self.settings)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("missing user identifier", ctx.exception.detail.lower())

    def test_email_fallback_mapping_for_application_user(self):
        """When auth_user has non-matching UUID but matching email, it safely maps to the User."""
        different_uuid_str = str(uuid.uuid4())
        auth_identity = AuthenticatedUser(
            id=different_uuid_str,
            email=self.user_email,
        )
        import asyncio
        user = asyncio.run(get_current_application_user(auth_identity, self.db))
        self.assertEqual(user.id, self.user_uuid)
        self.assertEqual(user.email, self.user_email)

    @patch("app.core.security.get_supabase_client")
    def test_remote_supabase_validation_fallback(self, mock_get_client):
        """When SUPABASE_JWT_SECRET is None, remote Supabase Auth API validation is used."""
        settings_no_secret = Settings(
            DATABASE_URL="sqlite:///:memory:",
            SUPABASE_URL="https://mockproject.supabase.co",
            SUPABASE_KEY="mock-anon-key-12345",
            SUPABASE_JWT_SECRET=None,
        )

        mock_sb_user = MagicMock()
        mock_sb_user.id = str(self.user_uuid)
        mock_sb_user.email = self.user_email
        mock_sb_user.role = "authenticated"
        mock_sb_user.app_metadata = {}
        mock_sb_user.user_metadata = {}

        mock_response = MagicMock()
        mock_response.user = mock_sb_user

        mock_auth = MagicMock()
        mock_auth.get_user.return_value = mock_response

        mock_client = MagicMock()
        mock_client.auth = mock_auth
        mock_get_client.return_value = mock_client

        auth_user = validate_supabase_token("remote.supabase.token", settings_no_secret)
        self.assertEqual(auth_user.id, str(self.user_uuid))
        self.assertEqual(auth_user.email, self.user_email)
        mock_auth.get_user.assert_called_once_with("remote.supabase.token")

    @patch("app.core.security.get_supabase_client")
    def test_remote_supabase_validation_auth_api_error(self, mock_get_client):
        """When remote Supabase Auth API returns an error, it is mapped to HTTP 401."""
        settings_no_secret = Settings(
            DATABASE_URL="sqlite:///:memory:",
            SUPABASE_URL="https://mockproject.supabase.co",
            SUPABASE_KEY="mock-anon-key-12345",
            SUPABASE_JWT_SECRET=None,
        )

        mock_auth = MagicMock()
        mock_auth.get_user.side_effect = AuthApiError("Invalid token", 401, "invalid_jwt")

        mock_client = MagicMock()
        mock_client.auth = mock_auth
        mock_get_client.return_value = mock_client

        with self.assertRaises(HTTPException) as ctx:
            validate_supabase_token("invalid.token", settings_no_secret)
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
