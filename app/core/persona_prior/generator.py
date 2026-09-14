"""Samples a single grounded persona from the prior graph: real demographics/behavior
draws (with provenance — which dataset and fallback level backed each field) plus a
transparent, non-learned heuristic `behavior_profile` derived from them.

Ported from the standalone Syndata persona-generator prototype
(`prior_crreation/graph_layer/17_persona_generator.py`). `AudienceEngine
.sample_grounded_participants` (app/services/audience_engine.py) is the only caller —
it extracts the 5 core traits from `behavior_profile` for the simulation loop and keeps
`identity`/`demographics`/`observed_behavior`/`provenance` as new persona fields;
`mental_model`/`goal` here are intentionally unused stubs, superseded by
`PersonaSampler`'s task-grounded versions."""

import copy
from typing import Any

import numpy as np

from app.core.persona_prior.prior_retrieval import PriorRetriever

_NAMES: dict[str, dict[str, list[str]]] = {
    "IND": {
        "male": ["Rohan Mehta", "Arjun Patel", "Vikram Singh", "Aditya Sharma", "Karan Gupta"],
        "female": ["Ananya Sharma", "Diya Patel", "Priya Singh", "Kavya Gupta", "Neha Desai"],
    },
    "global": {
        "male": ["John Doe", "Alex Smith", "Michael Johnson", "David Brown", "James Taylor"],
        "female": ["Jane Doe", "Sarah Smith", "Emily Johnson", "Jessica Brown", "Emma Taylor"],
    },
}

_OCCUPATIONS: dict[str, list[str]] = {
    "IND": [
        "Software Engineer",
        "Teacher",
        "Small Business Owner",
        "Student",
        "Healthcare Worker",
        "Retail Manager",
        "Freelancer",
        "Clerk",
    ],
    "global": [
        "Engineer",
        "Teacher",
        "Business Owner",
        "Student",
        "Nurse",
        "Manager",
        "Freelancer",
        "Clerk",
    ],
}

# Same 5-band vocabulary as `audience_engine.py`'s `_BAND_TO_MEAN_STD`, so a researcher's
# existing `digital.confidence`/`digital.familiarity` band string means the same thing
# whether or not grounding is enabled.
_TARGET_MAP: dict[str, float] = {
    "low": 0.25,
    "low_medium": 0.40,
    "medium": 0.55,
    "medium_high": 0.70,
    "high": 0.80,
}

_OBSERVED_BEHAVIOR_FEATURES = [
    "internet_usage",
    "mobile_phone_ownership",
    "account_ownership",
    "digital_payment_usage",
    "saving_behavior",
    "borrowing_behavior",
    "digital_experience_proxy",
]


class AudienceResolver:
    """Translates a researcher-facing audience definition into the prior graph's
    conditioning keys (hard filters), age bounds, and soft profile targets."""

    @staticmethod
    def resolve(audience_def: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {"conditions": {}, "bounds": {}, "profile_targets": {}}

        for key in ("country_code", "region", "urbanicity", "gender"):
            if audience_def.get(key):
                resolved["conditions"][key] = audience_def[key]

        if audience_def.get("age_min") is not None and audience_def.get("age_max") is not None:
            resolved["bounds"]["age"] = (audience_def["age_min"], audience_def["age_max"])

        for key in ("digital_confidence", "product_familiarity"):
            value = audience_def.get(key)
            if value:
                resolved["profile_targets"][key] = str(value).strip().lower()

        return resolved


class PersonaGenerator:
    def __init__(self, retriever: PriorRetriever) -> None:
        self.retriever = retriever

    def _sample_categorical(self, probs: dict[str, float], rng: np.random.Generator) -> str | None:
        categories = list(probs.keys())
        weights = list(probs.values())
        total = sum(weights)
        if total == 0:
            return None
        weights = [w / total for w in weights]
        return rng.choice(categories, p=weights)

    def _sample_continuous(
        self,
        prior: dict[str, Any],
        rng: np.random.Generator,
        bounds: tuple[float, float] | None = None,
    ) -> float:
        if prior.get("mean") is not None and prior.get("std") is not None:
            value = rng.normal(prior["mean"], prior["std"])
        else:
            value = prior.get("p50", 0.5)
        low, high = bounds if bounds else (0.0, 1.0)
        return float(np.clip(value, low, high))

    def _sample_age(
        self,
        age_bounds: tuple[int, int],
        conditions: dict[str, Any],
        rng: np.random.Generator,
        provenance: dict[str, Any],
    ) -> int:
        prior_node, fallback = self.retriever.resolve_fallback("age_bucket", conditions)
        age: int | None = None

        if prior_node and prior_node["type"] == "categorical":
            valid_probs: dict[str, float] = {}
            for bucket, prob in prior_node["probabilities"].items():
                if bucket in ("unknown", "refused"):
                    continue
                if "-" in bucket:
                    b_min, b_max = (int(x) for x in bucket.split("-"))
                else:
                    b_min, b_max = int(bucket.replace("+", "")), 110
                if age_bounds[0] <= b_max and age_bounds[1] >= b_min:
                    valid_probs[bucket] = prob

            if valid_probs:
                selected_bucket = self._sample_categorical(valid_probs, rng)
                if "-" in selected_bucket:
                    b_min, b_max = (int(x) for x in selected_bucket.split("-"))
                else:
                    b_min, b_max = int(selected_bucket.replace("+", "")), 110
                c_min = max(age_bounds[0], b_min)
                c_max = min(age_bounds[1], b_max)
                age = int(rng.integers(c_min, c_max + 1))
                provenance["age"] = {
                    "source": prior_node["source_dataset"],
                    "fallback": fallback,
                    "bucket": selected_bucket,
                }

        if age is None:
            age = int(rng.integers(age_bounds[0], age_bounds[1] + 1))
            provenance["age"] = {"source": "audience_bounds", "fallback": "uniform_random"}

        if age < 25:
            conditions["age_bucket"] = "15-24"
        elif age < 35:
            conditions["age_bucket"] = "25-34"
        elif age < 50:
            conditions["age_bucket"] = "35-49"
        elif age < 65:
            conditions["age_bucket"] = "50-64"
        else:
            conditions["age_bucket"] = "65+"

        return age

    def generate_persona(
        self, audience_def: dict[str, Any], persona_id: str, seed: int
    ) -> dict[str, Any]:
        rng = np.random.default_rng(seed)
        resolved = AudienceResolver.resolve(audience_def)
        conditions = copy.deepcopy(resolved["conditions"])

        provenance: dict[str, Any] = {}
        observed: dict[str, Any] = {}
        identity: dict[str, Any] = {}

        age_bounds = resolved["bounds"].get("age", (18, 99))
        identity["age"] = self._sample_age(age_bounds, conditions, rng, provenance)

        if "gender" not in conditions:
            prior_node, fallback = self.retriever.resolve_fallback("gender", conditions)
            if prior_node:
                gender = self._sample_categorical(prior_node["probabilities"], rng)
                conditions["gender"] = gender
                provenance["gender"] = {
                    "source": prior_node["source_dataset"],
                    "fallback": fallback,
                }
            else:
                gender = rng.choice(["male", "female"])
                conditions["gender"] = gender
                provenance["gender"] = {"source": "random", "fallback": "none"}

        for demo in ("education_level", "income_level", "employment_status", "urbanicity_clean"):
            prior_node, fallback = self.retriever.resolve_fallback(demo, conditions)
            if prior_node:
                value = self._sample_categorical(prior_node["probabilities"], rng)
                if value:
                    observed[demo] = value
                    provenance[demo] = {
                        "source": prior_node["source_dataset"],
                        "fallback": fallback,
                    }
                    conditions[demo] = value

        for feat in _OBSERVED_BEHAVIOR_FEATURES:
            prior_node, fallback = self.retriever.resolve_fallback(feat, conditions)
            if not prior_node:
                continue
            if prior_node["type"] == "categorical":
                value = self._sample_categorical(prior_node["probabilities"], rng)
                observed[feat] = 1 if value == "yes" else (0 if value == "no" else value)
            else:
                observed[feat] = self._sample_continuous(prior_node, rng)
            provenance[feat] = {"source": prior_node["source_dataset"], "fallback": fallback}

        profile = self._derive_behavior_profile(observed, resolved["profile_targets"], rng)

        country = conditions.get("country_code", "global")
        gender_key = str(conditions.get("gender", "male")).lower()
        names_pool = _NAMES.get(country, _NAMES["global"])
        if gender_key not in names_pool:
            gender_key = "male"
        identity["name"] = rng.choice(names_pool[gender_key])

        occ_pool = _OCCUPATIONS.get(country, _OCCUPATIONS["global"])
        identity["occupation"] = rng.choice(occ_pool)

        loc_parts = []
        if conditions.get("region"):
            loc_parts.append(conditions["region"])
        if country != "global":
            loc_parts.append(country)
        identity["location"] = ", ".join(loc_parts) if loc_parts else "Global"

        return {
            "persona_id": persona_id,
            "identity": identity,
            "context": conditions,
            "observed_behavior": observed,
            "behavior_profile": profile,
            "mental_model": {"expected_actions": [], "navigation_expectations": []},
            "goal": {"primary": None},
            "provenance": provenance,
        }

    def _derive_behavior_profile(
        self, observed: dict[str, Any], targets: dict[str, str], rng: np.random.Generator
    ) -> dict[str, float]:
        """Transparent, non-learned heuristic rules — do NOT replace with a trained
        model; the whole point is that every number here traces back to either a real
        survey draw (`observed`) or the researcher's own stated target."""
        profile: dict[str, float] = {}

        internet = float(observed.get("internet_usage", 0.5))
        digital_experience = float(observed.get("digital_experience_proxy", 0.5))
        base_confidence = (internet + digital_experience) / 2

        target_confidence = _TARGET_MAP.get(targets.get("digital_confidence", ""), base_confidence)
        profile["digital_confidence"] = np.clip(
            base_confidence * 0.6 + target_confidence * 0.4 + rng.normal(0, 0.1), 0, 1
        )

        target_familiarity = _TARGET_MAP.get(targets.get("product_familiarity", ""), 0.5)
        profile["product_familiarity"] = np.clip(target_familiarity + rng.normal(0, 0.1), 0, 1)

        exploration = profile["digital_confidence"] * (1 - profile["product_familiarity"])
        profile["exploration"] = np.clip(exploration + rng.normal(0, 0.1), 0, 1)

        profile["goal_directedness"] = np.clip(
            (1 - exploration) * 0.8 + 0.2 + rng.normal(0, 0.1), 0, 1
        )

        profile["patience"] = np.clip(rng.normal(0.5, 0.15), 0, 1)

        profile["cta_recognition"] = np.clip(
            profile["digital_confidence"] * 0.8 + 0.2 + rng.normal(0, 0.05), 0, 1
        )
        profile["instruction_following"] = np.clip(
            (profile["patience"] + profile["goal_directedness"]) / 2, 0, 1
        )

        return {k: round(float(v), 2) for k, v in profile.items()}

    def generate_personas(
        self, audience_def: dict[str, Any], n: int, start_seed: int
    ) -> list[dict[str, Any]]:
        return [
            self.generate_persona(audience_def, f"P-{i + 1:03d}", seed=start_seed + i)
            for i in range(n)
        ]
