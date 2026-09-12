from unittest.mock import AsyncMock

from app.api.v1 import stimuli as stimuli_module
from app.core.storage import StorageError
from app.domain.schemas.stimulus import ScreenRead, StimulusRead


def _stimulus_read(screen_image_urls: list[str | None]) -> StimulusRead:
    return StimulusRead(
        id="11111111-1111-1111-1111-111111111111",
        study_id="22222222-2222-2222-2222-222222222222",
        type="mobile_ui",
        source_url=None,
        metadata=None,
        version=1,
        created_at="2026-01-01T00:00:00Z",
        screens=[
            ScreenRead(
                id=f"33333333-3333-3333-3333-33333333333{i}",
                stimulus_id="11111111-1111-1111-1111-111111111111",
                screen_key=f"screen_{i}",
                width=None,
                height=None,
                image_url=url,
                analysis=None,
                created_at="2026-01-01T00:00:00Z",
                elements=[],
            )
            for i, url in enumerate(screen_image_urls)
        ],
    )


async def test_sign_screen_urls_replaces_the_internal_key_with_a_signed_url(monkeypatch):
    stimulus = _stimulus_read(["stimuli/abc/original"])
    monkeypatch.setattr(
        stimuli_module, "signed_url_or_none", AsyncMock(return_value="https://signed.example/x")
    )

    await stimuli_module._sign_screen_urls([stimulus])

    assert stimulus.screens[0].image_url == "https://signed.example/x"


async def test_sign_screen_urls_leaves_a_screen_without_an_image_untouched(monkeypatch):
    stimulus = _stimulus_read([None])
    monkeypatch.setattr(stimuli_module, "signed_url_or_none", AsyncMock(return_value=None))

    await stimuli_module._sign_screen_urls([stimulus])

    assert stimulus.screens[0].image_url is None


async def test_sign_screen_urls_degrades_to_none_instead_of_raising_on_a_storage_error(
    monkeypatch,
):
    """A Storage hiccup while signing one screen must not 500 the whole
    response — the frontend already renders "no preview" for a null
    image_url, which is strictly better than the previous always-broken
    raw internal key, let alone a request failure."""
    stimulus = _stimulus_read(["stimuli/abc/original"])
    monkeypatch.setattr(
        stimuli_module,
        "signed_url_or_none",
        AsyncMock(side_effect=StorageError("Supabase Storage sign failed (500)")),
    )

    await stimuli_module._sign_screen_urls([stimulus])

    assert stimulus.screens[0].image_url is None
