from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.content.sources import ExpansionPolicy
from aidm.state.base import (
    PLAYER_ID,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Slug,
    Trait,
    require_unique,
)
from aidm.state.world import CONNECTED, Hook, Memory, Relation, ScenarioMeta, Thread, WorldState

# The id-shaped keys committed facts actually carry; any other match key is not policed here.
_FACT_ENTITY_KEYS = ("entity_id", "to_id", "target")
# Effect keys that must name an existing entity; created ids (`trait_id`, `stage`) are free.
_EFFECT_ENTITY_KEYS = ("entity_id", "to_id", "source", "target", "actor_id")

type EffectParse = Callable[[JsonValue], Frozen]


@dataclass(frozen=True, slots=True)
class Binding:
    """What loading content needs from an engine, so `content` never imports one."""

    engine: EngineId
    parse_effect: EffectParse
    check_overlay: Callable[[Iterable[dict[str, JsonValue]]], None]


class ScenarioWorld(Frozen):
    """`world.json`: the narrative canon, authored once for every ruleset."""

    meta: ScenarioMeta
    expansion: ExpansionPolicy = "closed"
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
        require_unique("entity ids", [entity.id for entity in self.entities])
        require_unique("relations", [relation.id for relation in self.relations])
        require_unique("threads", [thread.id for thread in self.threads])
        require_unique("memories", [memory.id for memory in self.memories])
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
        require_unique("starting party", self.starting_party)
        for companion in self.starting_party:
            actor = self.world.require_kind(companion, "actor")
            if not (actor.known and actor.parent_id == self.starting_location_id):
                raise ValueError(
                    f"the player has met and stands beside who they set out with, "
                    f"unlike {companion!r}"
                )
        return self

    @model_validator(mode="after")
    def _every_location_reachable(self) -> Self:
        """An unknown or locked way still counts — the player can discover or open it — but a
        location no walk of `connected` relations reaches is content nobody can ever visit."""
        ways = [relation for relation in self.relations if relation.kind == CONNECTED]
        reached = _walk(ways, self.starting_location_id)
        unreachable = sorted(
            entity.id
            for entity in self.entities
            if entity.kind == "location" and entity.id not in reached
        )
        if unreachable:
            raise ValueError(
                f"locations no walk of `connected` relations reaches from "
                f"{self.starting_location_id!r}: {unreachable}"
            )
        return self

    @model_validator(mode="after")
    def _every_known_location_reachable_by_known_ways(self) -> Self:
        """A player who knows a place exists but has no known way to walk there hits a refusal
        for a place the premise told them about; movement is gated by `connected` relations, so
        this is a real dead end, not a cosmetic one."""
        known_ways = [
            relation for relation in self.relations if relation.kind == CONNECTED and relation.known
        ]
        reached = _walk(known_ways, self.starting_location_id)
        stranded = sorted(
            entity.id
            for entity in self.entities
            if entity.kind == "location" and entity.known and entity.id not in reached
        )
        if stranded:
            raise ValueError(
                f"locations the player knows of but no known way reaches from "
                f"{self.starting_location_id!r}: {stranded}"
            )
        return self

    @model_validator(mode="after")
    def _hooks_wait_on_authored_ids(self) -> Self:
        pools = _id_pools(self, _FACT_ENTITY_KEYS)
        dangling = [
            f"hook {hook.id!r} waits on {key}={value!r}"
            for hook in self.hooks
            for key, value in _dangling_ids(pools, hook.match.data)
        ]
        if dangling:
            raise ValueError(
                f"hooks waiting on ids nothing authored carries can never fire: "
                f"{'; '.join(dangling)}"
            )
        return self


def _walk(ways: Sequence[Relation], start: EntityId) -> set[EntityId]:
    """Every `connected` way is undirected, so a walk follows one from either end."""
    reached = {start}
    frontier = [start]
    while frontier:
        here = frontier.pop()
        for way in ways:
            if not way.touches(here):
                continue
            far = way.far_end(here)
            if far not in reached:
                reached.add(far)
                frontier.append(far)
    return reached


class ScenarioOverlay(Frozen):
    """`<engine>.json`: what one ruleset adds to the entities that need it."""

    entities: dict[EntityId, dict[str, JsonValue]] = Field(default_factory=dict)


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


def _require_authored(
    engine: EngineId,
    overlay: Mapping[EntityId, dict[str, JsonValue]],
    authored: Collection[EntityId],
) -> None:
    """An overlay keys off the authored ids, so a typo must fail at load, not go unread."""
    unknown = sorted(entity_id for entity_id in overlay if entity_id not in authored)
    if unknown:
        raise ValueError(f"the {engine!r} overlay names unauthored ids: {unknown}")


def check_hooks(world: ScenarioWorld, binding: Binding) -> None:
    """Hook effects are the engine's own vocabulary; core only checks the ids they reference."""
    pools = _id_pools(world, _EFFECT_ENTITY_KEYS)
    dangling: list[str] = []
    for hook in world.hooks:
        for effect in hook.effects:
            data = binding.parse_effect(effect).model_dump()
            dangling.extend(
                f"hook {hook.id!r} effect {data.get('op')!r} names {key}={value!r}"
                for key, value in _dangling_ids(pools, data)
            )
    if dangling:
        raise ValueError(
            f"hook effects naming ids nothing authored carries would fail mid-game: "
            f"{'; '.join(dangling)}"
        )


def _id_pools(world: ScenarioWorld, entity_keys: Iterable[str]) -> dict[str, set[str]]:
    entity_ids: set[str] = {PLAYER_ID, *world.world.entities}
    return {**dict.fromkeys(entity_keys, entity_ids), "thread_id": set(world.world.threads)}


def _dangling_ids(
    pools: Mapping[str, set[str]], data: Mapping[str, object]
) -> list[tuple[str, object]]:
    """Absent or null keys pass: null already means the player or 'leave as is', never a typo."""
    return [
        (key, value)
        for key, pool in pools.items()
        if (value := data.get(key)) is not None
        and (not isinstance(value, str) or value not in pool)
    ]
