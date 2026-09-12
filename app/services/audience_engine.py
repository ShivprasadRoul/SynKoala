import random

# PRD §4/FR-02: researchers describe traits qualitatively; these bands turn that into
# a numeric mean/std so continuous traits can be sampled (LLD §4), not fixed values.
_BAND_TO_MEAN_STD: dict[str, tuple[float, float]] = {
    "low": (0.25, 0.12),
    "low_medium": (0.40, 0.15),
    "medium": (0.55, 0.15),
    "medium_high": (0.70, 0.15),
    "high": (0.80, 0.12),
}

_DEFAULT_TRAIT = {"mean": 0.5, "std": 0.2}

# Maps a ParticipantRecordModel trait (LLD §5) back to where it lives in the researcher's raw
# audience `definition` (PRD §4's demographics/digital/behavioural characteristics).
_TRAIT_SOURCES: dict[str, tuple[str, str]] = {
    "digital_confidence": ("digital", "confidence"),
    "product_familiarity": ("digital", "familiarity"),
    "exploration": ("behaviour", "exploration"),
    "patience": ("behaviour", "patience"),
    "goal_directedness": ("behaviour", "goal_directedness"),
}


def _normalize_trait(value: object) -> dict[str, float]:
    if isinstance(value, dict) and "mean" in value:
        return {"mean": float(value["mean"]), "std": float(value.get("std", 0.15))}
    if isinstance(value, bool):
        raise ValueError(f"Unrecognized trait value: {value!r}")
    if isinstance(value, int | float):
        return {"mean": float(value), "std": 0.15}
    if isinstance(value, str):
        key = value.strip().lower().replace(" ", "_").replace("-", "_")
        if key in _BAND_TO_MEAN_STD:
            mean, std = _BAND_TO_MEAN_STD[key]
            return {"mean": mean, "std": std}
    raise ValueError(f"Unrecognized trait value: {value!r}")


class AudienceEngine:
    """planning/04-audience-engine.md. Pure statistics, no model/agent call — this is
    the highest-call-volume step in the pipeline and reproducibility (PRD §7) depends
    on it being deterministic given a seed."""

    def build_prior(self, definition: dict) -> dict:
        traits = {}
        for trait, (section, key) in _TRAIT_SOURCES.items():
            raw = (
                definition.get(section, {}).get(key)
                if isinstance(definition.get(section), dict)
                else None
            )
            traits[trait] = _normalize_trait(raw) if raw is not None else dict(_DEFAULT_TRAIT)
        return {"demographics": definition.get("demographics", {}), "traits": traits}

    def sample_participants(
        self, prior: dict, n: int, seed: int | None = None
    ) -> list[dict[str, float]]:
        rng = random.Random(seed)
        traits_prior = prior["traits"]
        participants = []
        for _ in range(n):
            traits = {
                name: min(1.0, max(0.0, rng.gauss(spec["mean"], spec["std"])))
                for name, spec in traits_prior.items()
            }
            participants.append(traits)
        return participants
