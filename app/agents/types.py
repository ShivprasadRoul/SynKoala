"""Internal shapes for the Simulation Engine (planning/07-simulation-engine.md).

These mirror the LLD's JSON examples (§5 Participant, §6 Screen Representation, §7
Screen Graph) but as the typed objects the graph/providers actually pass around —
distinct from `app/domain/schemas/*` (API request/response) and from the ORM models
they're built from (`app/db/models.py`).
"""

import uuid

from pydantic import BaseModel


class ElementView(BaseModel):
    id: uuid.UUID
    element_key: str
    type: str
    text: str | None
    bbox: tuple[int, int, int, int]
    semantic_role: str | None
    interactable: bool


class ScreenView(BaseModel):
    id: uuid.UUID
    screen_key: str
    width: int | None
    height: int | None
    elements: list[ElementView]

    def element(self, element_id: uuid.UUID) -> ElementView | None:
        return next((e for e in self.elements if e.id == element_id), None)


class TransitionView(BaseModel):
    from_screen_id: uuid.UUID
    trigger_element_id: uuid.UUID
    action: str
    to_screen_id: uuid.UUID


class ScreenGraph(BaseModel):
    screens: dict[uuid.UUID, ScreenView]
    transitions: list[TransitionView]

    def transitions_from(self, screen_id: uuid.UUID) -> list[TransitionView]:
        return [t for t in self.transitions if t.from_screen_id == screen_id]

    def resolve_starting_screen(self, starting_point: str | None) -> uuid.UUID:
        if starting_point:
            for screen in self.screens.values():
                if screen.screen_key == starting_point:
                    return screen.id
        if not self.screens:
            raise ValueError("Screen graph has no screens")
        return next(iter(self.screens))


class ParticipantDraft(BaseModel):
    id: uuid.UUID
    traits: dict[str, float]
    persona: dict | None = None
    seed: int | None = None


class TaskContext(BaseModel):
    id: uuid.UUID
    instruction: str
    starting_point: str | None
    success_conditions: dict | None
    constraints: dict | None
    expected_critical_actions: list[str] | None
