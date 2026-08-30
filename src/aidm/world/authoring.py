from collections.abc import Callable, Mapping
from pathlib import Path
from random import Random

from pydantic import Field, JsonValue

from aidm.content.io import engine_text
from aidm.content.model import AuthoringBrief, AuthoringTool
from aidm.state.entities import Entity, EntityId, Exit, Frozen
from aidm.state.facts import Fact
from aidm.state.model import Game, Mechanics, MechanicsPatch, Scenario, Thread, WorldState
from aidm.state.tools import Play
from aidm.world.topology import frontier, walk

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_WORLD_PROMPT = engine_text(_PROMPTS_DIR / "scenario_world.md")

MIN_LOCATIONS = 4
MIN_ACTORS = 2
MIN_OPENING_ENTITIES = 2


class Connect(Frozen):
    from_id: EntityId = Field(description="Exact id of the first location.")
    to_id: EntityId = Field(description="Exact id of the second location.")
    known: bool = Field(
        default=False, description="Whether the player knows this route at the start."
    )
    locked: bool = Field(default=False, description="Whether the route starts locked.")
    one_way: bool = Field(
        default=False,
        description="Whether the route goes only from the first location to the second.",
    )


def connect(world: WorldState, args: Connect) -> str:
    from_id, to_id = args.from_id, args.to_id
    if from_id == to_id:
        raise ValueError(f"a way leads somewhere other than {from_id!r}")
    ends = {from_id: _require_location(world, from_id), to_id: _require_location(world, to_id)}
    ways = ((from_id, to_id),) if args.one_way else ((from_id, to_id), (to_id, from_id))
    # Appending to `exits` skips validation, so every refusal lands before the first append.
    for start, end in ways:
        if ends[start].exit_to(end) is not None:
            raise ValueError(f"a way already leads from {start!r} to {end!r}")
        if args.known and not (ends[start].known and ends[end].known):
            raise ValueError(
                f"a known way from {start!r} to {end!r} names a place the player has not "
                "met; leave it unknown until both ends are"
            )
    for start, end in ways:
        ends[start].exits.append(Exit(to=end, known=args.known, locked=args.locked))
    return f"joined {from_id} to {to_id} {'one way' if args.one_way else 'both ways'}"


def _require_location(world: WorldState, entity_id: EntityId) -> Entity:
    held = world.entities.get(entity_id)
    if held is None or held.kind != "location":
        raise ValueError(f"the draft holds no location {entity_id!r}")
    return held


def _connect_tool(settled: frozenset[str]) -> AuthoringTool:
    def apply(world: WorldState, raw: Mapping[str, JsonValue]) -> str:
        args = Connect.model_validate(raw)
        if {args.from_id, args.to_id} <= settled:
            raise ValueError(
                f"{args.from_id!r} and {args.to_id!r} are both the live game's, and nothing here "
                "can take a way between them back. Join one of them to a location this pass wrote."
            )
        return connect(world, args)

    return AuthoringTool("connect", "Connect two locations already in the draft.", Connect, apply)


def _party_unmet(scenario: Scenario) -> list[str]:
    """Companions stand beside the player at the start: a rooms rule, so not `Scenario`'s."""
    start = scenario.player_parent_id
    if start is None:
        return []
    apart = [one for one in scenario.world.party if scenario.world.require(one).parent_id != start]
    return [f"every starting party member in {start!r}, unlike {apart}"] if apart else []


def _bar_unmet(scenario: Scenario) -> list[str]:
    unmet = _party_unmet(scenario)
    entities, threads = scenario.world.entities.values(), scenario.world.threads
    locations = sorted(entity.id for entity in entities if entity.kind == "location")
    if len(locations) < MIN_LOCATIONS:
        unmet.append(f"four or more locations; the draft has {len(locations)}: {locations}")
    if (start := scenario.player_parent_id) is not None:
        # Count locked and unknown exits because play can still open or discover them.
        reached = walk(scenario.world.entities, start)
        unreached = [one for one in locations if one not in reached]
        if unreached:
            unmet.append(f"locations no walk of exits reaches from {start!r}: {unreached}")
    ways = [way for entity in entities for way in entity.exits]
    if all(way.known for way in ways):
        unmet.append("at least one exit starting `known: false` — a way to find")
    if not any(way.locked for way in ways):
        unmet.append("at least one exit starting `locked: true`")
    actors = [entity for entity in entities if entity.kind == "actor"]
    if len(actors) < MIN_ACTORS:
        actor_ids = sorted(actor.id for actor in actors)
        unmet.append(f"two or more actors; the draft has {len(actors)}: {actor_ids}")
    if all(actor.known for actor in actors):
        unmet.append("at least one actor starting `known: false`")
    if not any(entity.kind == "item" and not entity.known for entity in entities):
        unmet.append("at least one item starting `known: false` — a secret to find")
    if not threads:
        unmet.append("at least one thread")
    if not any(entity.when_reached and not entity.known for entity in entities):
        unmet.append("at least one unknown entity whose `when_reached` carries a consequence")
    return unmet


def _opening_unmet(scenario: Scenario) -> list[str]:
    unmet = _party_unmet(scenario)
    beyond = [
        entity_id for entity_id in scenario.world.entities if entity_id != scenario.player_parent_id
    ]
    if len(beyond) < MIN_OPENING_ENTITIES:
        unmet.append(
            f"two or three entities besides the starting location; the draft has {len(beyond)}"
        )
    if not scenario.world.threads:
        unmet.append("at least one thread")
    return unmet


def _extend_unmet(before: WorldState) -> Callable[[Scenario], list[str]]:
    held = set(before.entities)

    def unmet(scenario: Scenario) -> list[str]:
        added = {
            entity.id
            for entity in scenario.world.entities.values()
            if entity.kind == "location" and entity.id not in held
        }
        if not added:
            return ["at least one location the world did not already hold"]
        if not any(
            way.to in added
            for entity in scenario.world.entities.values()
            if entity.id in held and entity.known
            for way in entity.exits
        ):
            return [
                "at least one exit from a location the player already knows of into one of the "
                f"new ones: {sorted(added)}"
            ]
        return []

    return unmet


def rooms_brief(base: WorldState | None, opening: bool, guidance: str) -> AuthoringBrief:
    settled: frozenset[str] = (
        frozenset() if base is None else frozenset(base.entities) | set(base.threads)
    )
    if base is not None:
        bar, bar_unmet = "scenario_extend.md", _extend_unmet(base)
    elif opening:
        # An opening slice is deliberately thin: the rest of the world is written during play.
        bar, bar_unmet = "scenario_opening.md", _opening_unmet
    else:
        bar, bar_unmet = "scenario_bar.md", _bar_unmet
    return AuthoringBrief(
        bar_prompt=f"{_WORLD_PROMPT}\n\n{engine_text(_PROMPTS_DIR / bar)}",
        guidance=guidance,
        unmet=bar_unmet,
        settled=settled,
        tools=(_connect_tool(settled),),
    )


def rooms_growth_due(state: Game, limit: int) -> bool:
    return frontier(state.world) <= limit


def diff(
    base: WorldState,
    draft: WorldState,
    mechanics: Mechanics,
    patch: MechanicsPatch,
) -> Play:
    """What an authoring pass added, materialized into a game that may have moved on since."""
    added = tuple(entity for entity in draft.entities.values() if entity.id not in base.entities)
    ways = tuple(
        (entity.id, way)
        for entity in draft.entities.values()
        if (was := base.entities.get(entity.id)) is not None
        for way in entity.exits
        if was.exit_to(way.to) is None
    )
    threads = tuple(thread for thread in draft.threads.values() if thread.id not in base.threads)

    def play(game: Game, _rng: Random) -> tuple[Fact, ...]:
        facts = [_added_entity(game, entity) for entity in added]
        # A second pass, so a new way may lead into a place the first one added.
        facts.extend(_added_exit(game, location_id, way) for location_id, way in ways)
        facts.extend(_opened(game, thread) for thread in threads)
        if mechanics:
            game.world.mechanics = patch(game.world.mechanics, mechanics, ())
        return tuple(facts)

    return play


def _added_entity(game: Game, entity: Entity) -> Fact:
    # Copied, so the patch recorded in the trace is not the object the world goes on mutating.
    materialized = entity.model_copy(deep=True)
    materialized.known = False
    for way in materialized.exits:
        way.known = False
    return game.add(materialized)


def _added_exit(game: Game, location_id: EntityId, way: Exit) -> Fact:
    here = game.world.require_kind(location_id, "location")
    if here.exit_to(way.to) is not None:
        raise ValueError(f"a way already leads from {here.id!r} to {way.to!r}")
    here.exits.append(Exit(to=way.to, locked=way.locked, known=False))
    return _materialized(f"way from {here.id} to {way.to}")


def _opened(game: Game, thread: Thread) -> Fact:
    if game.world.thread(thread.id) is not None:
        raise ValueError(f"a thread {thread.id!r} already exists")
    game.world.threads[thread.id] = thread.model_copy(deep=True)
    return _materialized(f"thread {thread.id}")


def _materialized(what: str) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}")
