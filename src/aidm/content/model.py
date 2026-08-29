from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    Entity,
    EntityId,
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
        for companion in self.world.party:
            if self.world.require(companion).parent_id != self.player_parent_id:
                raise ValueError(
                    f"the player stands beside who they set out with, unlike {companion!r}"
                )
        return self


class CharacterProfile(Frozen):
    """`base.json`: who the character is, the traits they carry, and the gear they start holding."""

    name: str
    brief: str
    traits: tuple[Trait, ...] = ()
    items: tuple[Entity, ...] = ()

    @model_validator(mode="after")
    def _held_and_known(self) -> Self:
        """Reject unknown carried gear because the Narrator sees the inventory."""
        wrong_kind = sorted(item.id for item in self.items if item.kind != "item")
        if wrong_kind:
            raise ValueError(f"a character's profile holds items only: {wrong_kind}")
        misplaced = sorted(item.id for item in self.items if item.parent_id != PLAYER_ID)
        if misplaced:
            raise ValueError(f"a character's items start in their own hands: {misplaced}")
        unknown = sorted(item.id for item in self.items if not item.known)
        if unknown:
            raise ValueError(f"a character knows the gear they start with: {unknown}")
        return self


class CharacterOverlay(Frozen):
    """`<engine>.json`: the sheet the engine plays by and the rules of each `base.json` item."""

    sheet: dict[str, JsonValue]
    items: dict[EntityId, dict[str, JsonValue]] = Field(default_factory=dict)


class Character(Frozen):
    id: Slug
    profile: CharacterProfile
    rules: dict[str, JsonValue]
    item_rules: dict[EntityId, dict[str, JsonValue]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _overlay_names_carried_gear(self) -> Self:
        carried = {item.id for item in self.profile.items}
        ids = sorted(set(self.item_rules) - carried)
        if ids:
            raise ValueError(f"overlay names gear the character does not carry: {ids}")
        return self

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def brief(self) -> str:
        return self.profile.brief


@dataclass(frozen=True, slots=True)
class AuthoringBrief:
    bar_prompt: str
    unmet: Callable[[Scenario], list[str]]
    settled: frozenset[str] = frozenset()
