from collections.abc import Mapping
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.base import PLAYER_ID, EngineId, Entity, EntityId, Frozen, Slug, Trait
from aidm.state.effects import AdvanceThread
from aidm.state.world import (
    Hook,
    Relation,
    ScenarioMeta,
    Thread,
    check_placement,
)

type Rules = dict[str, JsonValue]


class ScenarioWorld(Frozen):
    """`world.json`: the narrative canon, authored once for every ruleset."""

    meta: ScenarioMeta
    starting_location_id: EntityId
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    threads: tuple[Thread, ...] = ()
    hooks: tuple[Hook, ...] = ()

    @model_validator(mode="after")
    def _valid_topology(self) -> Self:
        by_id = {entity.id: entity for entity in self.entities}
        if len(by_id) != len(self.entities):
            ids = [entity.id for entity in self.entities]
            duplicates = sorted({entity_id for entity_id in ids if ids.count(entity_id) > 1})
            raise ValueError(f"scenario has duplicate entity ids: {duplicates}")
        if PLAYER_ID in by_id:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        starting_location = by_id.get(self.starting_location_id)
        if starting_location is None or starting_location.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        for entity in self.entities:
            holder = None if entity.parent_id is None else by_id.get(entity.parent_id)
            check_placement(entity, holder)
        # A duplicate would silently collapse when the relations are keyed by their derived ids.
        relation_ids = [relation.id for relation in self.relations]
        if len(set(relation_ids)) != len(relation_ids):
            raise ValueError(f"scenario has duplicate relations: {sorted(relation_ids)}")
        _unique("threads", [thread.id for thread in self.threads])
        _unique("hooks", [hook.id for hook in self.hooks])
        authored = {thread.id for thread in self.threads}
        wanted = sorted(
            {
                effect.thread_id
                for hook in self.hooks
                for effect in hook.effects
                if isinstance(effect, AdvanceThread)
            }
            - authored
        )
        if wanted:
            raise ValueError(f"hooks advance threads the scenario never authors: {wanted}")
        return self


class ScenarioOverlay(Frozen):
    """`<engine>.json`: what one ruleset adds to the entities that need it."""

    entities: dict[EntityId, Rules] = Field(default_factory=dict)


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
    character: Rules
    entities: dict[EntityId, Rules] = Field(default_factory=dict)


class Scenario(Frozen):
    id: Slug
    engine: EngineId
    world: ScenarioWorld
    overlay: ScenarioOverlay

    @property
    def meta(self) -> ScenarioMeta:
        return self.world.meta

    @model_validator(mode="after")
    def _overlay_fits_the_world(self) -> Self:
        _require_authored(self.engine, self.overlay.entities, self.world.entities)
        return self


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
        _require_authored(self.engine, self.overlay.entities, self.profile.items)
        return self


def _unique(what: str, ids: list[Slug]) -> None:
    repeated = sorted({name for name in ids if ids.count(name) > 1})
    if repeated:
        raise ValueError(f"scenario has duplicate {what}: {repeated}")


def _require_authored(
    engine: EngineId,
    overlay: Mapping[EntityId, Rules],
    authored: tuple[Entity, ...],
) -> None:
    """An overlay keys off the authored ids, so a typo must fail at load, not go unread."""
    ids = {entity.id for entity in authored}
    unknown = sorted(entity_id for entity_id in overlay if entity_id not in ids)
    if unknown:
        raise ValueError(f"the {engine!r} overlay names unauthored ids: {unknown}")
