"""Audience -> PersonaSampler -> Persona[] (planning/04-audience-engine.md's
Audience != Persona principle). AudienceEngine already samples the five core
behavioral traits from the audience's statistical prior (pure stats, seeded,
no model call) — PersonaSampler takes those five real, already-sampled values
for one participant and builds the rest of the rich persona object around
them:

- Every *behavioral* number here (friction, ui_preferences, the extra
  behavior-profile fields) is a deterministic formula of the five core
  traits plus a small seeded jitter — never sampled independently of the
  audience, and never from an LLM, so a given seed always reproduces the
  same personas (PRD §7 reproducibility).
- Identity fields (name/occupation/device/usage frequency) are cosmetic
  flavor drawn from a small curated pool via the same seeded RNG — they
  never feed back into any behavioral formula, per spec ("should NOT be the
  primary determinant of simulation behavior").
- Mental-model/goal fields are derived from the study's real Task text where
  one exists (never invented) — falling back to generic, clearly-generic
  copy when no task has been defined yet.

This is intentionally its own module, not a method on AudienceEngine: the
LLD's `Audience -> PersonaSampler -> Persona[] -> BehaviorPolicy -> Simulation`
pipeline keeps "what a persona is" separate from "how traits are sampled" and
(later) "how a persona decides what to do".
"""

import random
import re

_FIRST_NAMES = [
    "Rohan",
    "Priya",
    "Arjun",
    "Ananya",
    "Vikram",
    "Kavya",
    "Aditya",
    "Neha",
    "Karan",
    "Ishita",
    "Rahul",
    "Meera",
    "Sanjay",
    "Divya",
    "Amit",
    "Pooja",
    "Nikhil",
    "Sneha",
    "Varun",
    "Riya",
]
_LAST_NAMES = [
    "Mehta",
    "Sharma",
    "Iyer",
    "Reddy",
    "Kapoor",
    "Nair",
    "Gupta",
    "Rao",
    "Joshi",
    "Bose",
    "Verma",
    "Menon",
    "Chatterjee",
    "Desai",
    "Pillai",
]
_OCCUPATIONS = [
    "Software Engineer",
    "Teacher",
    "Student",
    "Small Business Owner",
    "Consultant",
    "Nurse",
    "Graphic Designer",
    "Accountant",
    "Delivery Executive",
    "Homemaker",
    "Sales Manager",
    "Electrician",
    "Content Writer",
    "Retail Associate",
    "Retired",
]
_USAGE_FREQUENCIES = ["Daily", "2-3 times/week", "Weekly", "Rarely"]
_DEVICES = ["Android", "iOS"]

_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "for",
    "with",
    "on",
    "in",
    "at",
    "and",
    "or",
    "your",
    "you",
    "this",
    "that",
    "into",
}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _jitter(rng: random.Random, spread: float = 0.05) -> float:
    return rng.uniform(-spread, spread)


def _derive_mental_model(task: dict | None, goal_directedness: float, exploration: float) -> dict:
    if not task or not task.get("instruction"):
        return {
            "expected_action": "Complete the intended task",
            "expected_location": "Home screen",
            "expected_terminology": [],
            "navigation_expectation": "No task defined yet for this study",
        }

    instruction: str = task["instruction"].strip()
    # A short, literal lead-in from the real instruction (up to the first
    # preposition/comma) rather than an invented summary — e.g. "Send ₹1,000
    # to a saved beneficiary" -> "Send ₹1,000".
    lead_in_match = re.split(r"\s+(?:to|for|via|using|so that)\s+|,\s+", instruction, maxsplit=1)
    expected_action = lead_in_match[0].strip() if lead_in_match else instruction

    tokens = [
        t for t in re.findall(r"[A-Za-z₹$€]+[A-Za-z]*", instruction) if t.lower() not in _STOPWORDS
    ]
    # Keep original casing where the source capitalized a word (a proper-noun-ish
    # signal), otherwise title-case short keywords — still literal words from
    # the instruction, not invented terms.
    seen: set[str] = set()
    expected_terminology: list[str] = []
    for token in tokens:
        label = token if token[0].isupper() else token.title()
        if label.lower() in seen or len(label) < 3:
            continue
        seen.add(label.lower())
        expected_terminology.append(label)
        if len(expected_terminology) >= 5:
            break

    navigation_expectation = (
        "Direct action from the starting screen"
        if goal_directedness >= 0.6
        else (
            "Exploratory browsing before committing to an action"
            if exploration >= 0.6
            else "A cautious, step-by-step path"
        )
    )

    return {
        "expected_action": expected_action,
        "expected_location": task.get("starting_point") or "Home screen",
        "expected_terminology": expected_terminology,
        "navigation_expectation": navigation_expectation,
    }


def _derive_goal(task: dict | None, goal_directedness: float, patience: float) -> dict:
    urgency = _clip(0.5 * goal_directedness + 0.5 * (1 - patience))
    if not task or not task.get("instruction"):
        return {
            "primary_goal": "No task defined yet for this study",
            "motivation": "N/A",
            "urgency": urgency,
            "success_definition": "N/A",
        }

    motivation = (
        "Complete this as quickly as possible"
        if urgency >= 0.6
        else "Get this right without rushing"
    )
    success_conditions = task.get("success_conditions")
    success_definition = (
        f"Meets the defined success conditions: {success_conditions}"
        if success_conditions
        else f"Successfully completes: {task['instruction']}"
    )
    return {
        "primary_goal": task["instruction"],
        "motivation": motivation,
        "urgency": urgency,
        "success_definition": success_definition,
    }


class PersonaSampler:
    """Builds one rich Persona dict per already-sampled set of core traits.
    Stateless — every call is a pure function of its arguments plus the
    caller-supplied `rng`, so reproducibility is entirely the caller's
    responsibility (seed the rng once per batch, call this once per
    participant in order)."""

    def sample(
        self,
        *,
        rng: random.Random,
        core_traits: dict[str, float],
        definition: dict,
        index: int,
        task: dict | None = None,
    ) -> dict:
        digital_confidence = core_traits.get("digital_confidence", 0.5)
        product_familiarity = core_traits.get("product_familiarity", 0.5)
        exploration = core_traits.get("exploration", 0.5)
        patience = core_traits.get("patience", 0.5)
        goal_directedness = core_traits.get("goal_directedness", 0.5)

        demographics = definition.get("demographics", {}) if isinstance(definition, dict) else {}
        age_range = demographics.get("age_range")
        age = rng.randint(age_range[0], age_range[1]) if age_range else rng.randint(18, 55)
        location = (
            ", ".join(filter(None, [demographics.get("city"), demographics.get("country")]))
            or "Unknown"
        )

        identity = {
            "name": f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
            "age": age,
            "occupation": rng.choice(_OCCUPATIONS),
            "location": location,
        }

        domain_experience = _clip(
            0.5 * product_familiarity + 0.3 * digital_confidence + _jitter(rng)
        )
        usage_index = min(
            len(_USAGE_FREQUENCIES) - 1, int((1 - product_familiarity) * len(_USAGE_FREQUENCIES))
        )
        context = {
            "digital_confidence": digital_confidence,
            "product_familiarity": product_familiarity,
            "domain_experience": domain_experience,
            "usage_frequency": _USAGE_FREQUENCIES[usage_index],
            "primary_device": rng.choices(_DEVICES, weights=[65, 35])[0],
        }

        behavior = {
            "digital_confidence": digital_confidence,
            "exploration": exploration,
            "patience": patience,
            "goal_directedness": goal_directedness,
            "decision_speed": _clip(
                0.5 * goal_directedness + 0.3 * digital_confidence + _jitter(rng)
            ),
            "cta_recognition": _clip(
                0.5 * digital_confidence + 0.3 * product_familiarity + _jitter(rng)
            ),
            "search_tendency": _clip(
                0.6 * exploration + 0.2 * (1 - goal_directedness) + _jitter(rng)
            ),
            "backtracking_tendency": _clip(0.5 * (1 - patience) + 0.3 * exploration + _jitter(rng)),
            "error_recovery": _clip(0.5 * digital_confidence + 0.3 * patience + _jitter(rng)),
            "instruction_following": _clip(
                0.5 * goal_directedness + 0.3 * (1 - exploration) + _jitter(rng)
            ),
        }

        mental_model = _derive_mental_model(task, goal_directedness, exploration)
        goal = _derive_goal(task, goal_directedness, patience)

        friction = {
            "confusion_threshold": _clip(
                0.3 + 0.4 * digital_confidence + 0.3 * product_familiarity + _jitter(rng)
            ),
            "abandonment_threshold": _clip(
                0.3 + 0.5 * patience + 0.2 * goal_directedness + _jitter(rng)
            ),
            "retry_probability": _clip(
                0.3 + 0.4 * patience + 0.3 * goal_directedness + _jitter(rng)
            ),
            "alternative_path_probability": _clip(0.2 + 0.5 * exploration + _jitter(rng)),
            "help_seeking_probability": _clip(0.6 - 0.4 * digital_confidence + _jitter(rng)),
        }

        ui_preferences = {
            "text_comprehension": _clip(
                0.4 + 0.4 * digital_confidence + 0.2 * product_familiarity + _jitter(rng)
            ),
            "icon_reliance": _clip(
                0.3 + 0.4 * exploration + 0.2 * digital_confidence + _jitter(rng)
            ),
            "form_tolerance": _clip(0.3 + 0.4 * patience + 0.2 * digital_confidence + _jitter(rng)),
            "modal_tolerance": _clip(0.3 + 0.4 * patience + _jitter(rng)),
            "scrolling_tolerance": _clip(0.3 + 0.5 * patience + 0.2 * exploration + _jitter(rng)),
            "icon_only_cta_recognition": _clip(
                0.2 + 0.5 * digital_confidence + 0.3 * product_familiarity + _jitter(rng)
            ),
        }

        return {
            "persona_id": f"P-{index + 1:03d}",
            "identity": identity,
            "context": context,
            "behavior": behavior,
            "mental_model": mental_model,
            "goal": goal,
            "friction": friction,
            "ui_preferences": ui_preferences,
        }
