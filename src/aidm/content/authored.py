from collections.abc import Collection, Mapping, Sequence
from functools import cached_property
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.base import PLAYER_ID, EngineId, Entity, EntityId, Frozen, Slug, Trait
from aidm.state.effects import AdvanceThread
from aidm.state.world import Hook, Memory, Relation, ScenarioMeta, Thread, WorldState

type Rules = dict[str, JsonValue]


class ScenarioWorld(Frozen):
    """`world.json`: the narrative canon, authored once for every ruleset."""

    meta: ScenarioMeta
    starting_location_id: EntityId
    starting_party: tuple[EntityId, ...] = ()
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    threads: tuple[Thread, ...] = ()
    memories: tuple[Memory, ...] = ()
    hooks: tuple[Hook, ...] = ()

    @cached_property
    def world(self) -> WorldState:
        """The authored canon as the one shape that validates it. The file keys nothing by id
        because an id-keyed JSON object collapses a duplicate silently."""
        _unique("entity ids", [entity.id for entity in self.entities])
        _unique("relations", [relation.id for relation in self.relations])
        _unique("threads", [thread.id for thread in self.threads])
        _unique("memories", [memory.id for memory in self.memories])
        return WorldState(
            entities={entity.id: entity for entity in self.entities},
            relations={relation.id: relation for relation in self.relations},
            threads={thread.id: thread for thread in self.threads},
            memories={memory.id: memory for memory in self.memories},
            hooks=self.hooks,
        )

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        if PLAYER_ID in self.world.entities:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        starting_location = self.world.entities.get(self.starting_location_id)
        if starting_location is None or starting_location.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        _unique("starting party", self.starting_party)
        for companion in self.starting_party:
            actor = self.world.require_kind(companion, "actor")
            if not (actor.known and actor.parent_id == self.starting_location_id):
                raise ValueError(
                    f"the player has met and stands beside who they set out with, "
                    f"unlike {companion!r}"
                )
        wanted = sorted(
            {
                effect.thread_id
                for hook in self.world.hooks
                for effect in hook.effects
                if isinstance(effect, AdvanceThread)
            }
            - set(self.world.threads)
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
        _require_authored(self.engine, self.overlay.entities, self.world.world.entities)
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
        _require_authored(
            self.engine, self.overlay.entities, {item.id for item in self.profile.items}
        )
        return self


def _unique(what: str, ids: Sequence[str]) -> None:
    if repeated := sorted({name for name in ids if ids.count(name) > 1}):
        raise ValueError(f"scenario has duplicate {what}: {repeated}")


def _require_authored(
    engine: EngineId,
    overlay: Mapping[EntityId, Rules],
    authored: Collection[EntityId],
) -> None:
    """An overlay keys off the authored ids, so a typo must fail at load, not go unread."""
    unknown = sorted(entity_id for entity_id in overlay if entity_id not in authored)
    if unknown:
        raise ValueError(f"the {engine!r} overlay names unauthored ids: {unknown}")
