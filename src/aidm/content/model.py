from collections.abc import Mapping
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
    starting_location_id: CheckedEntityId
    # Shared by every game of this scenario: read-only — `begin_game` deep-copies before mutating.
    world: WorldState

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        if "srd" not in self.packs:
            raise ValueError("scenario packs must include 'srd'")
        if self.world.find(PLAYER_ID) is not None:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        starting_location = self.world.find(self.starting_location_id)
        if starting_location is None or starting_location.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        for companion in self.world.party:
            if self.world.require(companion).parent_id != self.starting_location_id:
                raise ValueError(
                    f"the player stands beside who they set out with, unlike {companion!r}"
                )
        return self

    @model_validator(mode="after")
    def _every_location_reachable(self) -> Self:
        """Count locked and unknown exits because play can still open or discover them."""
        reached = _walk(self.world.entities, self.starting_location_id)
        unreachable = sorted(
            entity.id
            for entity in self.world.entities.values()
            if entity.kind == "location" and entity.id not in reached
        )
        if unreachable:
            raise ValueError(
                f"locations no walk of exits reaches from "
                f"{self.starting_location_id!r}: {unreachable}"
            )
        return self


def _walk(entities: Mapping[EntityId, Entity], start: EntityId) -> set[EntityId]:
    reached = {start}
    frontier = [start]
    while frontier:
        here = entities.get(frontier.pop())
        for way in () if here is None else here.exits:
            if way.to not in reached:
                reached.add(way.to)
                frontier.append(way.to)
    return reached


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
        ids = sorted(item.id for item in self.items if item.rules != {})
        if ids:
            raise ValueError(f"gear rules live in the engine overlay, not base.json: {ids}")
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
