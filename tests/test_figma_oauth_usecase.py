import uuid
from unittest.mock import AsyncMock

from app.db.models import UserModel
from app.usecases.auth import FigmaOAuthUseCase


class _NoOpSession:
    pass


async def test_is_connected_true_when_a_figma_connection_exists():
    use_case = FigmaOAuthUseCase(_NoOpSession())
    use_case._figma = AsyncMock()
    use_case._figma.get_connection.return_value = object()  # any non-None row

    user = UserModel(id=uuid.uuid4(), email="researcher@example.com")
    assert await use_case.is_connected(user) is True


async def test_is_connected_false_when_no_figma_connection_exists():
    use_case = FigmaOAuthUseCase(_NoOpSession())
    use_case._figma = AsyncMock()
    use_case._figma.get_connection.return_value = None

    user = UserModel(id=uuid.uuid4(), email="researcher@example.com")
    assert await use_case.is_connected(user) is False
