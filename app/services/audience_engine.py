import asyncio
import random

from app.core import storage
from app.core.persona_prior.generator import PersonaGenerator
from app.core.persona_prior.prior_retrieval import PriorRetriever
from app.core.settings import settings

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


# The 5 core traits `HeuristicParticipantModel` reads (LLD §5) — also the only
# `behavior_profile` keys pulled out of a grounded persona; the graph's own
# `cta_recognition`/`instruction_following` are dropped rather than merged, since
# `PersonaSampler` already derives its own versions of those from these 5 (see
# app/services/persona_sampler.py's module docstring).
_CORE_TRAIT_KEYS = (
    "digital_confidence",
    "product_familiarity",
    "exploration",
    "patience",
    "goal_directedness",
)


# Module-level cache: the compiled prior graph is ~30MB — fetched from Supabase
# Storage once per process, not once per `AudienceEngine()` instantiation (a fresh
# instance is built per request in `AudienceUseCase.__init__`). A lock (not
# `functools.lru_cache`, which can't await) guards the first concurrent fetch so two
# simultaneous requests don't both download it.
_retriever_cache: dict[str, PriorRetriever] = {}
_retriever_cache_lock = asyncio.Lock()


async def _load_retriever(storage_path: str) -> PriorRetriever:
    if storage_path in _retriever_cache:
        return _retriever_cache[storage_path]
    async with _retriever_cache_lock:
        if storage_path not in _retriever_cache:
            content, _content_type = await storage.download_object(storage_path)
            _retriever_cache[storage_path] = PriorRetriever.from_bytes(content)
    return _retriever_cache[storage_path]


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

    def grounding_available(self) -> bool:
        """True once a real, dataset-backed prior graph is configured
        (`PERSONA_PRIOR_GRAPH_STORAGE_PATH`) — mirrors Figma OAuth's own "unset
        disables the feature" pattern (`FigmaOAuthService`, app/core/settings.py)
        rather than failing hard: unlike a screenshot no model has looked at, there's
        an honest existing substitute here (`sample_participants`, above), so an
        unconfigured graph just means falling back to it, not refusing to generate a
        population at all. This only checks *configuration*, not that the object
        actually exists in Storage — same as Figma's own check — so a wrong path is a
        real `StorageError` raised by `sample_grounded_participants` once grounding
        is actually attempted, not a silent fallback."""
        return bool(settings.persona_prior_graph_storage_path)

    def _to_audience_def(self, definition: dict) -> dict:
        """Adapts a researcher's `AudienceCreate.definition` dict into the prior
        graph's expected shape. Every key here is optional and additive — a
        definition using only today's `demographics`/`digital` keys still resolves,
        just at a less specific fallback tier (still real-data-grounded, still
        provenance-tracked)."""
        demographics = definition.get("demographics", {}) if isinstance(definition, dict) else {}
        digital = definition.get("digital", {}) if isinstance(definition, dict) else {}

        audience_def: dict = {}
        for key in ("country_code", "region", "urbanicity", "gender"):
            if definition.get(key):
                audience_def[key] = definition[key]

        age_range = demographics.get("age_range")
        if definition.get("age_min") is not None and definition.get("age_max") is not None:
            audience_def["age_min"] = definition["age_min"]
            audience_def["age_max"] = definition["age_max"]
        elif age_range:
            audience_def["age_min"], audience_def["age_max"] = age_range[0], age_range[1]

        for target_key, source in (
            ("digital_confidence", digital.get("confidence")),
            ("product_familiarity", digital.get("familiarity")),
        ):
            if isinstance(source, str):
                audience_def[target_key] = source

        return audience_def

    async def sample_grounded_participants(self, definition: dict, n: int, seed: int) -> list[dict]:
        """Real-data-grounded counterpart to `sample_participants`: same 5 core
        traits (so `HeuristicParticipantModel` and everything downstream needs no
        change), plus `identity`/`demographics`/`observed_behavior`/`provenance` —
        genuinely new pieces with no equivalent in the qualitative-band sampler.
        Deterministic given `seed`, no model/agent call — same guarantee as
        `sample_participants` (planning/04-audience-engine.md). Raises
        `app.core.storage.StorageError` if `grounding_available()` is True but the
        configured object can't actually be fetched — a misconfigured path is a real
        error, not silently masked by falling back."""
        retriever = await _load_retriever(settings.persona_prior_graph_storage_path)
        generator = PersonaGenerator(retriever)
        audience_def = self._to_audience_def(definition)

        raw_personas = generator.generate_personas(audience_def, n, start_seed=seed or 0)
        return [
            {
                "traits": {key: raw["behavior_profile"][key] for key in _CORE_TRAIT_KEYS},
                "identity": raw["identity"],
                "demographics": raw["context"],
                "observed_behavior": raw["observed_behavior"],
                "provenance": raw["provenance"],
            }
            for raw in raw_personas
        ]
