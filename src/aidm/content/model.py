from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, Field, JsonValue, SerializeAsAny, field_validator, model_validator

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
from aidm.state.model import ScenarioMeta, WorldState, require_parsed_payload


class ScenarioPayload(Frozen):
    """The legacy engines' scenario payload; it dies with the Phase-3 port."""

    # Where the played character starts; a non-rooms engine leaves it null.
    player_parent_id: CheckedEntityId | None = None
    # Shared by every game of this scenario: read-only — `begin_game` deep-copies before mutating.
    world: WorldState

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        if self.world.find(PLAYER_ID) is not None:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        if self.player_parent_id is not None:
            _ = self.world.require(self.player_parent_id)
        return self


class Scenario(Frozen):
    """`scenarios/<id>/world.json`: its dump is the scenario envelope around one payload."""

    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    grows: bool = False
    art_style: str = ""
    payload: SerializeAsAny[BaseModel]

    _payload_is_parsed = field_validator("payload", mode="before")(require_parsed_payload)

    @model_validator(mode="after")
    def _unique_packs(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        return self

    @property
    def _legacy(self) -> ScenarioPayload:
        if not isinstance(self.payload, ScenarioPayload):
            raise ValueError(f"the {self.engine!r} scenario holds no rooms world")
        return self.payload

    @property
    def world(self) -> WorldState:
        return self._legacy.world

    @property
    def player_parent_id(self) -> CheckedEntityId | None:
        return self._legacy.player_parent_id


class CharacterPayload(Frozen):
    """The legacy engines' character payload; it dies with the Phase-3 port."""

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


class Character(Frozen):
    """`characters/<id>/<engine>.json`: who they are and the payload this engine plays them by."""

    id: Slug
    engine: EngineId
    name: str
    brief: str
    payload: SerializeAsAny[BaseModel]

    _payload_is_parsed = field_validator("payload", mode="before")(require_parsed_payload)

    @property
    def _legacy(self) -> CharacterPayload:
        if not isinstance(self.payload, CharacterPayload):
            raise ValueError(f"the {self.engine!r} character holds no legacy payload")
        return self.payload

    @property
    def traits(self) -> tuple[Trait, ...]:
        return self._legacy.traits

    @property
    def items(self) -> tuple[Entity, ...]:
        return self._legacy.items

    @property
    def mechanics(self) -> dict[str, JsonValue]:
        return self._legacy.mechanics


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
