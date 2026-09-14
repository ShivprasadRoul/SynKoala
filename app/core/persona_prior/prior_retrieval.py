"""Loads the compiled audience-prior graph (real survey datasets — WVS, Findex, etc. —
compiled offline into empirical probabilities/means per demographic condition) and
resolves the most specific prior available for a given feature, per
planning/04-audience-engine.md's grounding of `AudienceEngine.sample_participants`.

Ported from the standalone Syndata persona-generator prototype
(`prior_crreation/graph_layer/16_prior_retrieval.py`) with no behavioral changes."""

import copy
import json
from pathlib import Path
from typing import Any

# Each hierarchy entry is (condition-type name in the graph's per-feature index, the
# audience-condition keys required to use it) — tried most specific first, falling all
# the way back to "global" (no conditions) so a lookup never simply fails.
_FALLBACK_HIERARCHY: list[tuple[str, list[str]]] = [
    ("country_age_gender", ["country_code", "age_bucket", "gender"]),
    ("country_age", ["country_code", "age_bucket"]),
    ("country_gender", ["country_code", "gender"]),
    ("country", ["country_code"]),
    ("region_age_gender", ["region", "age_bucket", "gender"]),
    ("region_age", ["region", "age_bucket"]),
    ("region_gender", ["region", "gender"]),
    ("region", ["region"]),
    ("global", []),
]


class PriorRetriever:
    """Holds the full prior graph in memory (loaded once — see the
    `@lru_cache`-wrapped loader in `app/services/audience_engine.py`) and resolves
    feature priors against it."""

    def __init__(self, graph_path: str | Path) -> None:
        with open(graph_path) as f:
            graph = json.load(f)
        self.priors: dict[str, Any] = graph.get("priors", {})
        self.index: dict[str, Any] = graph.get("index", {})
        self.relationships: list[dict[str, Any]] = graph.get("relationships", [])

    def _build_cond_key(self, conditions: dict[str, Any], keys: list[str]) -> str:
        cond_dict = {k: conditions[k] for k in keys if k in conditions and conditions[k]}
        if not cond_dict:
            return "global"
        return "&".join(f"{k}={v}" for k, v in sorted(cond_dict.items()))

    def resolve_fallback(
        self, feature_id: str, audience_conditions: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Hierarchically falls back to the most specific prior available for
        `feature_id` given what's known about the audience. Returns
        `(prior_node, fallback_level_used)`, or `(None, None)` if the feature isn't in
        the graph at all."""
        if feature_id not in self.index:
            return None, None

        feature_index = self.index[feature_id]
        for cond_type, keys in _FALLBACK_HIERARCHY:
            if not all(k in audience_conditions and audience_conditions[k] for k in keys):
                continue
            cond_key = self._build_cond_key(audience_conditions, keys)
            if cond_type in feature_index and cond_key in feature_index[cond_type]:
                prior_id = feature_index[cond_type][cond_key]
                return copy.deepcopy(self.priors[prior_id]), cond_type

        return None, None

    def get_prior(self, feature_id: str, conditions: dict[str, Any]) -> dict[str, Any] | None:
        prior, _ = self.resolve_fallback(feature_id, conditions)
        return prior

    def get_related_features(
        self, feature_id: str, min_strength: str = "moderate"
    ) -> list[dict[str, Any]]:
        """Features correlated with `feature_id` above `min_strength` — not used by the
        persona generator today, kept for parity with the source graph's own tooling."""
        strength_levels = {"strong": 3, "moderate": 2, "weak": 1, "negligible": 0}
        min_level = strength_levels.get(min_strength, 1)

        related = []
        for rel in self.relationships:
            if rel["source"] == feature_id or rel["target"] == feature_id:
                if strength_levels.get(rel.get("strength"), 0) >= min_level:
                    related.append(rel)
        return related
