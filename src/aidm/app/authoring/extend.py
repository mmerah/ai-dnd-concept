from pydantic import JsonValue
from pydantic_ai import UsageLimits

from aidm.config import Settings
from aidm.content.authored import Character
from aidm.content.sources import whole_text
from aidm.content.store import source_file
from aidm.engines.engine import Engine
from aidm.state.model import Entity, EntityId, Exit, Fact, Frozen, Game, Thread, WorldState

from .agents import REQUEST_LIMIT, world_agent
from .draft import WorldDraft
from .playability import Playtest, extend_brief


class ExitLink(Frozen):
    location_id: EntityId
    to: EntityId
    locked: bool = False


class ExtensionPatch(Frozen):
    entities: tuple[Entity, ...] = ()
    exits: tuple[ExitLink, ...] = ()
    threads: tuple[Thread, ...] = ()


async def author_extension(
    config: Settings,
    engine: Engine,
    character: Character,
    state: Game,
) -> ExtensionPatch:
    """One authoring run against the live world, answered as the canon it added. The `finish`
    validator refuses an unplayable draft inside the run, so there is no outer retry loop."""
    document = source_file(config.scenarios_dir, state.scenario_id)
    draft = WorldDraft.of_game(state)
    playing = (Playtest(engine=engine, character=character),)
    agent = world_agent(playing, config, extend_brief(state.world))
    given = state.scenario.premise if document is None else whole_text(document)
    heading = "PREMISE:" if document is None else "SOURCE DOCUMENT:"
    _ = await agent.run(
        f"{heading}\n{given}\n\nExtend the world `scenario_so_far` holds.",
        deps=draft,
        usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
    )
    return delta(state.world, draft)


def delta(before: WorldState, after: WorldDraft) -> ExtensionPatch:
    """What an extension pass added. Add-only: a change to canon that already existed is ignored,
    except a new way out of it, which is how new canon is reached at all."""
    held = {entity.id: entity for entity in before.entities}
    opened = {thread.id for thread in before.threads}
    return ExtensionPatch(
        entities=tuple(entity for entity in after.entities if entity.id not in held),
        exits=tuple(
            ExitLink(location_id=entity.id, to=way.to, locked=way.locked)
            for entity in after.entities
            if (was := held.get(entity.id)) is not None
            for way in entity.exits
            if was.exit_to(way.to) is None
        ),
        threads=tuple(thread for thread in after.threads if thread.id not in opened),
    )


def apply_patch(draft: Game, patch: ExtensionPatch) -> tuple[Fact, ...]:
    """The one place a patch reaches the world: add-only, unknown, and refused whole on any id the
    draft already holds."""
    facts = [_added_entity(draft, entity) for entity in patch.entities]
    facts.extend(_added_exit(draft, link) for link in patch.exits)
    facts.extend(_opened(draft, thread) for thread in patch.threads)
    return tuple(facts)


def _added_entity(draft: Game, entity: Entity) -> Fact:
    # Copied, so the patch recorded in the trace is not the object the world goes on mutating.
    materialized = entity.model_copy(deep=True)
    materialized.known = False
    for way in materialized.exits:
        way.known = False
    return draft.add(materialized)


def _added_exit(draft: Game, link: ExitLink) -> Fact:
    here = draft.world.require_kind(link.location_id, "location")
    if here.exit_to(link.to) is not None:
        raise ValueError(f"a way already leads from {here.id!r} to {link.to!r}")
    here.exits.append(Exit(to=link.to, locked=link.locked))
    return _materialized(
        f"way from {here.id} to {link.to}", {"location_id": here.id, "to_id": link.to}
    )


def _opened(draft: Game, thread: Thread) -> Fact:
    if draft.world.thread(thread.id) is not None:
        raise ValueError(f"a thread {thread.id!r} already exists")
    draft.world.threads.append(thread.model_copy(deep=True))
    return _materialized(f"thread {thread.id}", {"thread_id": thread.id})


def _materialized(what: str, data: dict[str, JsonValue]) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}", data=data)
