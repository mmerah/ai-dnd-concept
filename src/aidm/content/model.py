from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, Field, JsonValue, model_validator

from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    Entity,
    Frozen,
    Slug,
    Trait,
    require_unique,
)
from aidm.state.model import ScenarioMeta, WorldState


class Scenario(Frozen):
    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    grows: bool = False
    art_style: str = ""
    # Where the played character starts; a non-rooms engine leaves it null.
    player_parent_id: CheckedEntityId | None = None
    # Shared by every game of this scenario: read-only — `begin_game` deep-copies before mutating.
    world: WorldState

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        if self.world.find(PLAYER_ID) is not None:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        if self.player_parent_id is not None:
            _ = self.world.require(self.player_parent_id)
        return self


class Character(Frozen):
    """`characters/<id>/<engine>.json`: who they are and the sheet this engine plays them by."""

    id: Slug
    engine: EngineId
    name: str
    brief: str
    traits: tuple[Trait, ...] = ()
    items: tuple[Entity, ...] = ()
    mechanics: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _held_and_known(self) -> Self:
        """Reject unknown carried gear because the Narrator sees the inventory."""
        wrong_kind = sorted(item.id for item in self.items if item.kind != "item")
        if wrong_kind:
            raise ValueError(f"a character holds items only: {wrong_kind}")
        misplaced = sorted(item.id for item in self.items if item.parent_id != PLAYER_ID)
        if misplaced:
            raise ValueError(f"a character's items start in their own hands: {misplaced}")
        unknown = sorted(item.id for item in self.items if not item.known)
        if unknown:
            raise ValueError(f"a character knows the gear they start with: {unknown}")
        return self


@dataclass(frozen=True, slots=True)
class AuthoringTool:
    name: str
    description: str
    args: type[BaseModel]
    apply: Callable[[WorldState, Mapping[str, JsonValue]], str]


@dataclass(frozen=True, slots=True)
class AuthoringBrief:
    bar_prompt: str
    guidance: str
    unmet: Callable[[Scenario], list[str]]
    settled: frozenset[str] = frozenset()
    tools: tuple[AuthoringTool, ...] = ()
