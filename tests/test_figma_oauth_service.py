import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core import crypto
from app.db.models import FigmaConnectionModel
from app.services.figma_oauth_service import TOKEN_REFRESH_BUFFER, FigmaOAuthService


class _FakeSession:
    def __init__(self, connection: FigmaConnectionModel | None) -> None:
        self._connection = connection

    async def scalar(self, _stmt):
        return self._connection

    async def flush(self) -> None:
        pass

    async def refresh(self, _obj) -> None:
        pass


def _connection(expires_at: datetime, access_token: str = "old-token") -> FigmaConnectionModel:
    return FigmaConnectionModel(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        access_token_encrypted=crypto.encrypt(access_token),
        refresh_token_encrypted=crypto.encrypt("refresh-token"),
        expires_at=expires_at,
    )


async def test_get_valid_access_token_returns_the_stored_token_when_not_near_expiry(monkeypatch):
    connection = _connection(datetime.now(UTC) + timedelta(hours=1))
    service = FigmaOAuthService(_FakeSession(connection))
    refresh_mock = AsyncMock()
    monkeypatch.setattr(service, "refresh_access_token", refresh_mock)

    token = await service.get_valid_access_token(connection.user_id)

    assert token == "old-token"
    refresh_mock.assert_not_awaited()


async def test_get_valid_access_token_refreshes_when_close_to_expiry(monkeypatch):
    """A long-running import job shouldn't have its token expire mid-request
    — refresh happens `TOKEN_REFRESH_BUFFER` ahead of actual expiry, not at it."""
    connection = _connection(datetime.now(UTC) + TOKEN_REFRESH_BUFFER - timedelta(seconds=1))
    service = FigmaOAuthService(_FakeSession(connection))
    refreshed = _connection(datetime.now(UTC) + timedelta(hours=1), access_token="new-token")
    refresh_mock = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(service, "refresh_access_token", refresh_mock)

    token = await service.get_valid_access_token(connection.user_id)

    assert token == "new-token"
    refresh_mock.assert_awaited_once_with(connection)


async def test_get_valid_access_token_rejects_a_user_with_no_figma_connection():
    service = FigmaOAuthService(_FakeSession(None))

    with pytest.raises(HTTPException) as exc_info:
        await service.get_valid_access_token(uuid.uuid4())

    assert exc_info.value.status_code == 403
