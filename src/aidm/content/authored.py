from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Literal, Self

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
from aidm.state.effects import Reveal, references
from aidm.state.world import (
    CONNECTED,
    DiscoveryMatch,
    Hook,
    Memory,
    Relation,
    ScenarioMeta,
    Thread,
    ThreadMatch,
    WorldState,
)


@dataclass(frozen=True, slots=True)
class EngineBinding:
    """What loading content needs from an engine, so `content` never imports one."""

    engine: EngineId
    check_overlay: Callable[[Iterable[dict[str, JsonValue]]], None]


class ScenarioWorld(Frozen):
    """`world.json`: the narrative canon, authored once for every ruleset."""

    meta: ScenarioMeta
    expansion: ExpansionPolicy = "closed"
    art_style: str = ""
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
        require_unique("hooks", [hook.id for hook in self.hooks])
        return WorldState(
            entities={entity.id: entity for entity in self.entities},
            relations={relation.id: relation for relation in self.relations},
            threads={thread.id: thread for thread in self.threads},
            memories={memory.id: memory for memory in self.memories},
            hooks={hook.id: hook for hook in self.hooks},
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
        entity_ids = {PLAYER_ID, *self.world.entities}
        thread_ids = set(self.world.threads)
        dangling: list[str] = []
        for hook in self.hooks:
            match hook.match:
                case DiscoveryMatch(entity_id=entity_id) if entity_id is not None:
                    if entity_id not in entity_ids:
                        dangling.append(f"hook {hook.id!r} waits on entity_id={entity_id!r}")
                case ThreadMatch(thread_id=thread_id) if thread_id is not None:
                    if thread_id not in thread_ids:
                        dangling.append(f"hook {hook.id!r} waits on thread_id={thread_id!r}")
                case _:
                    pass
        if dangling:
            raise ValueError(
                f"hooks waiting on ids nothing authored carries can never fire: "
                f"{'; '.join(dangling)}"
            )
        return self

    @model_validator(mode="after")
    def _hook_effects_are_sound(self) -> Self:
        pools: dict[Literal["entity", "thread"], set[str]] = {
            "entity": {PLAYER_ID, *self.world.entities},
            "thread": set(self.world.threads),
        }
        dangling: list[str] = []
        revealed: dict[Slug, set[EntityId]] = {}
        for hook in self.hooks:
            dangling.extend(
                f"hook {hook.id!r} effect {effect.op!r} names {kind}={value!r}"
                for effect in hook.effects
                for kind, value in references(effect)
                if value not in pools[kind]
            )
            revealed[hook.id] = {
                effect.entity_id for effect in hook.effects if isinstance(effect, Reveal)
            }
        if dangling:
            raise ValueError(
                f"hook effects naming ids nothing authored carries would fail mid-game: "
                f"{'; '.join(dangling)}"
            )
        _no_hook_domino(self, revealed)
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


def _no_hook_domino(world: ScenarioWorld, revealed: Mapping[Slug, set[EntityId]]) -> None:
    """`fire_hooks` feeds each round's facts back into matching, so a hook's own `reveal` fires the
    hook waiting on that discovery. One such step is a consequence; a hook that is both fired by
    another and fires a third is a domino that opens the whole adventure on one turn."""
    waiting = {
        hook.match.entity_id: hook.id
        for hook in world.hooks
        if isinstance(hook.match, DiscoveryMatch) and hook.match.entity_id is not None
    }
    edges = [
        (hook_id, waiting[entity_id])
        for hook_id, entity_ids in revealed.items()
        for entity_id in entity_ids
        if entity_id in waiting
    ]
    middle = sorted({fired for _, fired in edges} & {fires for fires, _ in edges})
    if middle:
        raise ValueError(
            f"hooks chaining discoveries into a domino, so one reveal fires the lot: {middle}. "
            "A hook another hook fires may not reveal what a third hook waits for; put the "
            "consequences in one hook, or wait on something the player must do next."
        )
