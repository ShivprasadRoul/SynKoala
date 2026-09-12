from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import UserModel
from app.db.session import get_session
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=True)


@lru_cache
def _default_jwk_client() -> PyJWKClient:
    # PyJWKClient caches fetched keys in-memory, so this is the "verify locally,
    # don't round-trip to Supabase per request" cache from planning/01-auth.md.
    return PyJWKClient(settings.supabase_jwks_url, cache_keys=True)


def get_jwk_client() -> PyJWKClient:
    return _default_jwk_client()


def decode_supabase_jwt(token: str, jwk_client: PyJWKClient) -> dict:
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
    jwk_client: PyJWKClient = Depends(get_jwk_client),
) -> UserModel:
    claims = decode_supabase_jwt(credentials.credentials, jwk_client)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return await AuthService(session).get_or_create_user(user_id=sub, email=claims.get("email"))
