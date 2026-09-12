import json
import uuid
from datetime import UTC, datetime
from functools import lru_cache

import jwt
from cryptography.fernet import InvalidToken
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import crypto
from app.core.settings import settings
from app.db.models import ParticipantRunModel, UserModel
from app.db.session import get_session
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=True)

_TERMINAL_PARTICIPANT_STATUSES = ("COMPLETED", "FAILED", "ABANDONED")


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


async def get_capture_token(
    x_capture_token: str = Header(..., alias="X-Capture-Token"),
    session: AsyncSession = Depends(get_session),
) -> ParticipantRunModel:
    """planning/13-journey-capture.md's capture-token dependency, sibling to
    get_current_user, not a replacement for it — testers never get a Supabase
    account. Header-based (not Authorization/HTTPBearer) to stay visually and
    mechanically distinct from the Supabase JWT scheme."""
    try:
        payload = json.loads(crypto.decrypt(x_capture_token))
        participant_run_id = uuid.UUID(payload["participant_run_id"])
        expires_at = payload["exp"]
    except (InvalidToken, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid capture token"
        ) from exc
    if datetime.now(UTC).timestamp() > expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Capture token expired"
        )

    participant_run = await session.scalar(
        select(ParticipantRunModel)
        .where(ParticipantRunModel.id == participant_run_id)
        .options(selectinload(ParticipantRunModel.simulation_run))
    )
    if participant_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participant run not found"
        )
    if participant_run.simulation_run.source != "HUMAN":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not a human capture session"
        )
    if participant_run.status in _TERMINAL_PARTICIPANT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Capture session already finished"
        )
    return participant_run
