import json

from app.services.audience_engine import _CORE_TRAIT_KEYS, AudienceEngine, _load_retriever

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


def _write_fake_graph(tmp_path) -> str:
    path = tmp_path / "fake_prior_graph.json"
    path.write_text(json.dumps(_FAKE_GRAPH))
    return str(path)


def test_grounding_unavailable_without_a_configured_path(monkeypatch):
    monkeypatch.setattr("app.services.audience_engine.settings.persona_prior_graph_path", None)
    assert AudienceEngine().grounding_available() is False


def test_grounding_unavailable_when_configured_file_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.audience_engine.settings.persona_prior_graph_path",
        str(tmp_path / "does_not_exist.json"),
    )
    assert AudienceEngine().grounding_available() is False


def test_grounding_available_once_a_real_graph_file_is_configured(monkeypatch, tmp_path):
    graph_path = _write_fake_graph(tmp_path)
    monkeypatch.setattr(
        "app.services.audience_engine.settings.persona_prior_graph_path", graph_path
    )
    _load_retriever.cache_clear()
    assert AudienceEngine().grounding_available() is True


def test_sample_grounded_participants_is_deterministic_and_shaped_correctly(monkeypatch, tmp_path):
    graph_path = _write_fake_graph(tmp_path)
    monkeypatch.setattr(
        "app.services.audience_engine.settings.persona_prior_graph_path", graph_path
    )
    _load_retriever.cache_clear()

    engine = AudienceEngine()
    definition = {"country_code": "IND", "region": "Mumbai"}

    first = engine.sample_grounded_participants(definition, n=3, seed=7)
    second = engine.sample_grounded_participants(definition, n=3, seed=7)

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
