from pydantic import Field, JsonValue

from aidm.engines.engine import TurnLog
from aidm.state.base import Entity, EntityId, Exit, Frozen
from aidm.state.facts import Fact
from aidm.state.trace import StepTrace
from aidm.state.world import Game, Hook, Thread

MAX_EXPANSIONS = 2


class ExitLink(Frozen):
    location_id: EntityId = Field(description="Exact id of the location the way leads from.")
    to: EntityId = Field(description="Exact id of the location it leads to.")
    locked: bool = Field(default=False, description="Whether the way starts shut.")


class ExpansionPatch(Frozen):
    """New canon, added to a world that only ever gains, apart from the ways it hangs on locations
    that already exist; nothing here is known to the player until the Director's own effects
    establish it."""

    entities: tuple[Entity, ...] = Field(
        default=(), description="New locations, actors, and items, each with an unused id."
    )
    exits: tuple[ExitLink, ...] = Field(
        default=(),
        description="Ways added to locations that already exist, so new places can be walked to.",
    )
    threads: tuple[Thread, ...] = Field(
        default=(), description="New storylines this canon opens, each with an unused id."
    )
    hooks: tuple[Hook, ...] = Field(
        default=(), description="New authored consequences, each with an unused id."
    )


def capped(log: TurnLog) -> bool:
    return len(log.steps) >= MAX_EXPANSIONS


def record(log: TurnLog, prompt: str, answer: ExpansionPatch | str) -> None:
    """A refusal is recorded as its reason, so a turn that wrote no canon still says why."""
    log.steps.append(
        StepTrace(
            name=f"expander-{len(log.steps) + 1}",
            prompt=prompt,
            output=answer if isinstance(answer, str) else answer.model_dump(mode="json"),
        )
    )


def apply_patch(draft: Game, patch: ExpansionPatch) -> tuple[Fact, ...]:
    """The one place a patch reaches the world: add-only, unknown, and refused whole on any id the
    draft already holds."""
    facts = [_added_entity(draft, entity) for entity in patch.entities]
    facts.extend(_added_exit(draft, link) for link in patch.exits)
    facts.extend(_opened(draft, thread) for thread in patch.threads)
    facts.extend(_authored(draft, patch.hooks))
    return tuple(facts)


def written(patch: ExpansionPatch) -> str:
    """What the tool hands back: the ids the Director plans with, none of them known yet."""
    lines = [f"- {entity.id} ({entity.kind}) — {entity.name}" for entity in patch.entities]
    lines.extend(f"- way: {link.location_id} → {link.to}" for link in patch.exits)
    lines.extend(f"- thread {thread.id} — {thread.title}" for thread in patch.threads)
    lines.extend(f"- hook {hook.id}" for hook in patch.hooks)
    return "\n".join(lines) or "nothing was added"


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


def _authored(draft: Game, hooks: tuple[Hook, ...]) -> list[Fact]:
    facts: list[Fact] = []
    for hook in hooks:
        if draft.world.hook(hook.id) is not None:
            raise ValueError(f"a hook {hook.id!r} already exists")
        for entity_id in (hook.on_discover, *hook.reveals):
            _ = draft.world.require(entity_id)
        advance = hook.advance_thread
        if advance is not None and draft.world.thread(advance.thread_id) is None:
            raise ValueError(f"a hook names unknown thread {advance.thread_id!r}")
        draft.world.hooks.append(hook)
        facts.append(_materialized(f"hook {hook.id}", {"hook_id": hook.id}))
    return facts


def _materialized(what: str, data: dict[str, JsonValue]) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}", data=data)
