import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.auth import decode_supabase_jwt, get_current_user
from app.core.settings import settings
from app.db.models import UserModel
from app.main import app


class _FakeSigningKey:
    def __init__(self, key) -> None:
        self.key = key


class _FakeJWKClient:
    """Stands in for PyJWKClient so the JWT-verification unit test never hits the
    network — planning/01-auth.md's contract is "verify locally", so this is what
    it looks like to verify without depending on Supabase actually being reachable."""

    def __init__(self, public_key) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(self._public_key)


@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(
    private_key,
    *,
    sub="11111111-1111-1111-1111-111111111111",
    exp_delta=timedelta(minutes=5),
):
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "email": "researcher@example.com",
        "aud": settings.supabase_jwt_audience,
        "iss": settings.supabase_jwt_issuer,
        "iat": now,
        "exp": now + exp_delta,
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_decode_supabase_jwt_accepts_valid_token(rsa_keypair):
    private_key, public_key = rsa_keypair
    token = _make_token(private_key)

    claims = decode_supabase_jwt(token, _FakeJWKClient(public_key))

    assert claims["sub"] == "11111111-1111-1111-1111-111111111111"
    assert claims["email"] == "researcher@example.com"


def test_decode_supabase_jwt_rejects_expired_token(rsa_keypair):
    private_key, public_key = rsa_keypair
    token = _make_token(private_key, exp_delta=timedelta(minutes=-5))

    with pytest.raises(Exception) as exc_info:
        decode_supabase_jwt(token, _FakeJWKClient(public_key))

    assert exc_info.value.status_code == 401


def test_decode_supabase_jwt_rejects_wrong_audience(rsa_keypair):
    private_key, public_key = rsa_keypair
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "x",
            "aud": "not-authenticated",
            "iss": settings.supabase_jwt_issuer,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )

    with pytest.raises(Exception) as exc_info:
        decode_supabase_jwt(token, _FakeJWKClient(public_key))

    assert exc_info.value.status_code == 401


async def test_users_me_requires_auth(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401  # HTTPBearer with no Authorization header


async def test_users_me_returns_authenticated_user(client):
    fake_user = UserModel(
        id=uuid.uuid4(),
        email="researcher@example.com",
        name="Researcher",
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user

    try:
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer irrelevant-because-overridden"}
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "researcher@example.com"
    assert body["id"] == str(fake_user.id)
