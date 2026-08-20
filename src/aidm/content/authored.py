from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.content.sources import ExpansionPolicy
from aidm.state.base import PLAYER_ID, EngineId, Entity, EntityId, Frozen, Slug, Trait
from aidm.state.world import ScenarioMeta, WorldState


@dataclass(frozen=True, slots=True)
class EngineBinding:
    """What loading content needs from an engine, so `content` never imports one."""

    engine: EngineId
    check_overlay: Callable[[Iterable[dict[str, JsonValue]]], None]


class Scenario(Frozen):
    """`world.json`: the starting state, authored once for every ruleset."""

    meta: ScenarioMeta
    expansion: ExpansionPolicy = "closed"
    art_style: str = ""
    starting_location_id: EntityId
    # Shared by every game of this scenario: read-only — `begin_game` deep-copies before mutating.
    world: WorldState

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
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
        """A locked or unfound way still counts — the player can open or walk it — but a location
        no walk of exits reaches is content nobody can ever visit."""
        reached = _walk(self.world.entities, self.starting_location_id)
        unreachable = sorted(
            entity.id
            for entity in self.world.entities
            if entity.kind == "location" and entity.id not in reached
        )
        if unreachable:
            raise ValueError(
                f"locations no walk of exits reaches from "
                f"{self.starting_location_id!r}: {unreachable}"
            )
        return self


def _walk(entities: Sequence[Entity], start: EntityId) -> set[EntityId]:
    by_id = {entity.id: entity for entity in entities}
    reached = {start}
    frontier = [start]
    while frontier:
        here = by_id.get(frontier.pop())
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
        """Own gear is known gear: an unknown carried item would be hidden canon inside the
        inventory the Narrator is shown, so the two prompts would contradict each other."""
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
    character: dict[str, JsonValue]
    entities: dict[EntityId, dict[str, JsonValue]] = Field(default_factory=dict)


class CreatedCharacter(Frozen):
    """What in-app creation produces: exactly the two files hand-authoring writes."""

    profile: CharacterProfile
    overlay: CharacterOverlay


class Character(Frozen):
    id: Slug
    engine: EngineId
    profile: CharacterProfile
    overlay: CharacterOverlay

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def brief(self) -> str:
        return self.profile.brief

    @model_validator(mode="after")
    def _overlay_fits_the_character(self) -> Self:
        _require_authored(
            self.engine, self.overlay.entities, {item.id for item in self.profile.items}
        )
        return self


def _require_authored(
    engine: EngineId,
    overlay: Mapping[EntityId, dict[str, JsonValue]],
    authored: Collection[EntityId],
) -> None:
    """An overlay keys off the authored ids, so a typo must fail at load, not go unread."""
    unknown = sorted(entity_id for entity_id in overlay if entity_id not in authored)
    if unknown:
        raise ValueError(f"the {engine!r} overlay names unauthored ids: {unknown}")
