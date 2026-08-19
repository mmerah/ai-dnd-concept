from pydantic import Field, JsonValue

from aidm.engines.engine import TurnLog
from aidm.state.base import Entity, Frozen
from aidm.state.facts import Fact
from aidm.state.resolution import Resolution
from aidm.state.trace import StepTrace
from aidm.state.world import GameState, Hook, Relation, Thread

MAX_EXPANSIONS = 2


class ExpansionPatch(Frozen):
    """New canon, add-only: nothing already in the world is touched, and nothing here is known to
    the player until the Director's own effects establish it."""

    entities: tuple[Entity, ...] = Field(
        default=(), description="New locations, actors, and items, each with an unused id."
    )
    relations: tuple[Relation, ...] = Field(
        default=(), description="New ties: `connected` joins two locations the player can walk."
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


def apply_patch(draft: GameState, patch: ExpansionPatch) -> Resolution:
    """The one place a patch reaches the world: add-only, unknown, and refused whole on any id the
    draft already holds."""
    facts = [_added_entity(draft, entity) for entity in patch.entities]
    facts.extend(_added_relation(draft, relation) for relation in patch.relations)
    facts.extend(_opened(draft, thread) for thread in patch.threads)
    facts.extend(_authored(draft, patch.hooks))
    return Resolution(facts=tuple(facts))


def written(patch: ExpansionPatch) -> str:
    """What the tool hands back: the ids the Director plans with, none of them known yet."""
    lines = [f"- {entity.id} ({entity.kind}) — {entity.name}" for entity in patch.entities]
    lines.extend(
        f"- {relation.kind}: {relation.source} — {relation.target}" for relation in patch.relations
    )
    lines.extend(f"- thread {thread.id} — {thread.title}" for thread in patch.threads)
    lines.extend(f"- hook {hook.id}" for hook in patch.hooks)
    return "\n".join(lines) or "nothing was added"


def _added_entity(draft: GameState, entity: Entity) -> Fact:
    # Copied, so the patch recorded in the trace is not the object the world goes on mutating.
    materialized = entity.model_copy(deep=True)
    materialized.known = False
    return draft.add(materialized)


def _added_relation(draft: GameState, relation: Relation) -> Fact:
    materialized = relation.model_copy(deep=True)
    materialized.known = False
    if materialized.id in draft.world.relations:
        raise ValueError(f"a tie {materialized.id!r} already joins those two")
    _ = draft.world.require(materialized.source)
    _ = draft.world.require(materialized.target)
    draft.world.relations[materialized.id] = materialized
    return _materialized(f"tie {materialized.id}", {"relation_id": materialized.id})


def _opened(draft: GameState, thread: Thread) -> Fact:
    if thread.id in draft.world.threads:
        raise ValueError(f"a thread {thread.id!r} already exists")
    draft.world.threads[thread.id] = thread.model_copy(deep=True)
    return _materialized(f"thread {thread.id}", {"thread_id": thread.id})


def _authored(draft: GameState, hooks: tuple[Hook, ...]) -> list[Fact]:
    facts: list[Fact] = []
    for hook in hooks:
        if hook.id in draft.world.hooks:
            raise ValueError(f"a hook {hook.id!r} already exists")
        for entity_id in (hook.on_discover, *hook.reveals):
            _ = draft.world.require(entity_id)
        advance = hook.advance_thread
        if advance is not None and advance.thread_id not in draft.world.threads:
            raise ValueError(f"a hook names unknown thread {advance.thread_id!r}")
        draft.world.hooks[hook.id] = hook
        facts.append(_materialized(f"hook {hook.id}", {"hook_id": hook.id}))
    return facts


def _materialized(what: str, data: dict[str, JsonValue]) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}", data=data)
