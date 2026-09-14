import json

import pytest

from app.services import audience_engine as audience_engine_module
from app.services.audience_engine import _CORE_TRAIT_KEYS, AudienceEngine

_FAKE_GRAPH = {
    "priors": {
        "age_bucket_global": {
            "type": "categorical",
            "source_dataset": "wvs",
            "probabilities": {"15-24": 0.2, "25-34": 0.3, "35-49": 0.3, "50-64": 0.15, "65+": 0.05},
        },
        "gender_global": {
            "type": "categorical",
            "source_dataset": "wvs",
            "probabilities": {"male": 0.5, "female": 0.5},
        },
        "internet_usage_global": {
            "type": "categorical",
            "source_dataset": "findex",
            "probabilities": {"yes": 0.7, "no": 0.3},
        },
        "digital_experience_proxy_global": {
            "type": "continuous",
            "source_dataset": "findex",
            "mean": 0.6,
            "std": 0.1,
        },
    },
    "index": {
        "age_bucket": {"global": {"global": "age_bucket_global"}},
        "gender": {"global": {"global": "gender_global"}},
        "internet_usage": {"global": {"global": "internet_usage_global"}},
        "digital_experience_proxy": {"global": {"global": "digital_experience_proxy_global"}},
    },
    "relationships": [],
}


def _mock_download(monkeypatch, storage_path: str = "persona-priors/fake_graph.json") -> list:
    """Stands in for `app.core.storage.download_object` so tests never hit a real
    Supabase Storage bucket — records each call so tests can assert caching."""
    calls: list[str] = []

    async def fake_download_object(bucket_and_path: str):
        calls.append(bucket_and_path)
        return json.dumps(_FAKE_GRAPH).encode(), "application/json"

    monkeypatch.setattr(audience_engine_module.storage, "download_object", fake_download_object)
    audience_engine_module._retriever_cache.clear()
    return calls


async def test_sample_participants_raises_a_clear_error_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        "app.services.audience_engine.settings.persona_prior_graph_storage_path", None
    )
    with pytest.raises(RuntimeError, match="PERSONA_PRIOR_GRAPH_STORAGE_PATH"):
        await AudienceEngine().sample_participants({"country_code": "IND"}, n=1, seed=1)


async def test_sample_participants_is_deterministic_and_shaped_correctly(monkeypatch):
    storage_path = "persona-priors/fake_graph.json"
    _mock_download(monkeypatch, storage_path)
    monkeypatch.setattr(
        "app.services.audience_engine.settings.persona_prior_graph_storage_path", storage_path
    )

    engine = AudienceEngine()
    definition = {"country_code": "IND", "region": "Mumbai"}

    first = await engine.sample_participants(definition, n=3, seed=7)
    second = await engine.sample_participants(definition, n=3, seed=7)

    assert first == second
    assert len(first) == 3
    for persona in first:
        assert set(persona["traits"].keys()) == set(_CORE_TRAIT_KEYS)
        for value in persona["traits"].values():
            assert 0.0 <= value <= 1.0
        assert "identity" in persona
        assert "demographics" in persona
        assert "observed_behavior" in persona
        assert persona["provenance"], "every persona should cite at least one real source"


async def test_sample_participants_fetches_the_graph_only_once(monkeypatch):
    """The ~30MB graph should be downloaded from Storage once per process, not once
    per call — this is what actually makes repeated generation fast."""
    storage_path = "persona-priors/fake_graph.json"
    calls = _mock_download(monkeypatch, storage_path)
    monkeypatch.setattr(
        "app.services.audience_engine.settings.persona_prior_graph_storage_path", storage_path
    )

    engine = AudienceEngine()
    await engine.sample_participants({"country_code": "IND"}, n=1, seed=1)
    await engine.sample_participants({"country_code": "IND"}, n=1, seed=2)

    assert calls == [storage_path]
