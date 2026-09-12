import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.errors import LifecycleError
from app.usecases.stimulus import StimulusUseCase


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _use_case() -> StimulusUseCase:
    use_case = StimulusUseCase(_NoOpSession())
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = None
    use_case._stimuli = AsyncMock()
    use_case._figma_oauth = AsyncMock()
    return use_case


async def test_create_rejects_a_figma_stimulus_with_no_figma_connection():
    """The gap this closes: without this check, a create with type=figma and
    no connected Figma account would succeed (201, a real stimulus row) and
    only fail later, invisibly, inside the background import_figma_prototype
    job — the researcher would never see why nothing happened."""
    use_case = _use_case()
    use_case._figma_oauth.get_connection.return_value = None

    with pytest.raises(LifecycleError, match="Connect your Figma account"):
        await use_case.create(
            user=Mock(id=uuid.uuid4()),
            study_id=uuid.uuid4(),
            stimulus_type="figma",
            source_url="https://www.figma.com/design/abc123/My-Prototype",
            file_bytes=None,
            file_content_type=None,
            metadata=None,
        )

    use_case._stimuli.create_with_asset.assert_not_awaited()


async def test_create_proceeds_for_a_figma_stimulus_once_connected():
    use_case = _use_case()
    use_case._figma_oauth.get_connection.return_value = Mock()
    fake_stimulus = Mock()
    use_case._stimuli.create_with_asset.return_value = fake_stimulus

    result = await use_case.create(
        user=Mock(id=uuid.uuid4()),
        study_id=uuid.uuid4(),
        stimulus_type="figma",
        source_url="https://www.figma.com/design/abc123/My-Prototype",
        file_bytes=None,
        file_content_type=None,
        metadata=None,
    )

    assert result is fake_stimulus


async def test_create_never_checks_figma_for_a_non_figma_stimulus():
    use_case = _use_case()
    fake_stimulus = Mock()
    use_case._stimuli.create_with_asset.return_value = fake_stimulus

    result = await use_case.create(
        user=Mock(id=uuid.uuid4()),
        study_id=uuid.uuid4(),
        stimulus_type="mobile_ui",
        source_url=None,
        file_bytes=b"fake-bytes",
        file_content_type="image/png",
        metadata=None,
    )

    assert result is fake_stimulus
    use_case._figma_oauth.get_connection.assert_not_awaited()
