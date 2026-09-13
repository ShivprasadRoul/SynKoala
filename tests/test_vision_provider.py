import pydantic_ai

from app.agents.providers.vision_provider import (
    InferredTransition,
    PydanticAIVisionProvider,
    ScreenAnalysis,
    ScreenElement,
    ScreenGraphInference,
    ScreenSummary,
)


class _FakeResult:
    """Stands in for `pydantic_ai`'s `AgentRunResult` — only `.output` is used
    by `PydanticAIVisionProvider`. Per `.claude/skills/backend-feature/
    SKILL.md` §6, agent tests mock `Agent.run` rather than hitting a real
    model — there's no model-provider API key configured in this repo yet
    anyway (`CLAUDE.md` "Repository state")."""

    def __init__(self, output):
        self.output = output


async def test_analyze_screen_returns_the_agents_structured_output(monkeypatch):
    expected = ScreenAnalysis(
        elements=[
            ScreenElement(
                id="cta",
                type="button",
                text="Buy",
                bbox=(1, 2, 3, 4),
                semantic_role="primary_action",
                interactable=True,
            )
        ]
    )

    async def fake_run(self, user_prompt=None, **kwargs):
        return _FakeResult(expected)

    monkeypatch.setattr(pydantic_ai.Agent, "run", fake_run)

    provider = PydanticAIVisionProvider(model="test")
    result = await provider.analyze_screen(b"fake-bytes", "image/png")

    assert result == expected


async def test_infer_transitions_skips_the_model_call_for_fewer_than_two_screens():
    """No model call needed (and none made) when there's nothing to connect —
    this assertion holds without any mocking, since a real call would error
    with no model-provider API key configured."""
    provider = PydanticAIVisionProvider(model="test")
    result = await provider.infer_transitions([ScreenSummary(screen_key="home", elements=[])])

    assert result == ScreenGraphInference(transitions=[])


async def test_infer_transitions_returns_the_agents_structured_output(monkeypatch):
    expected = ScreenGraphInference(
        transitions=[
            InferredTransition(
                from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="confirm"
            )
        ]
    )

    async def fake_run(self, user_prompt=None, **kwargs):
        return _FakeResult(expected)

    monkeypatch.setattr(pydantic_ai.Agent, "run", fake_run)

    provider = PydanticAIVisionProvider(model="test")
    result = await provider.infer_transitions(
        [
            ScreenSummary(screen_key="home", elements=[]),
            ScreenSummary(screen_key="confirm", elements=[]),
        ]
    )

    assert result == expected


async def test_analyze_screen_tells_the_model_the_real_pixel_dimensions_when_known(monkeypatch):
    """Vision models commonly resize a large image internally before
    analyzing it, so a bbox reported with no frame of reference can land in
    whatever resolution the model happened to downscale to rather than the
    original upload's real pixel grid — every downstream consumer
    (_sample_point_in_bbox, the results UI's heatmap/scanpath overlays)
    treats bbox as absolute pixels in that original space, so the model must
    be told it explicitly."""
    captured_prompts = []

    async def fake_run(self, user_prompt=None, **kwargs):
        captured_prompts.append(user_prompt)
        return _FakeResult(ScreenAnalysis(elements=[]))

    monkeypatch.setattr(pydantic_ai.Agent, "run", fake_run)

    provider = PydanticAIVisionProvider(model="test")
    await provider.analyze_screen(b"fake-bytes", "image/png", image_size=(750, 1334))

    prompt_text = " ".join(p for p in captured_prompts[0] if isinstance(p, str))
    assert "750x1334" in prompt_text


async def test_analyze_screen_omits_the_size_hint_when_dimensions_are_unknown(monkeypatch):
    captured_prompts = []

    async def fake_run(self, user_prompt=None, **kwargs):
        captured_prompts.append(user_prompt)
        return _FakeResult(ScreenAnalysis(elements=[]))

    monkeypatch.setattr(pydantic_ai.Agent, "run", fake_run)

    provider = PydanticAIVisionProvider(model="test")
    await provider.analyze_screen(b"fake-bytes", "image/png")

    prompt_text = " ".join(p for p in captured_prompts[0] if isinstance(p, str))
    assert "pixels" not in prompt_text
