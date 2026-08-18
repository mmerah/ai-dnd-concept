from dataclasses import dataclass, field

from pydantic import Field, JsonValue

from aidm.state.base import Entity, Frozen
from aidm.state.beat import Resolution
from aidm.state.facts import CORE, Fact
from aidm.state.trace import StepTrace
from aidm.state.world import CONNECTED, GameState, Hook, Relation, Thread

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


@dataclass(slots=True)
class Expansions:
    """What `expand_world` wrote into a turn's draft, for `run_turn` to fold into the turn."""

    facts: list[Fact] = field(default_factory=list)
    steps: list[StepTrace] = field(default_factory=list)

    def capped(self) -> bool:
        return len(self.steps) >= MAX_EXPANSIONS

    def record(self, prompt: str, answer: ExpansionPatch | str) -> None:
        """A refusal is recorded as its reason, so a turn that wrote no canon still says why."""
        self.steps.append(
            StepTrace(
                name=f"expander-{len(self.steps) + 1}",
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
    return Resolution(facts=tuple(facts), followup="none")


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
    # Resolved from the kind, as a Director-written tie already is: a `connected` left directed by
    # a defaulted field would fail the whole patch over something the engine knows on its own.
    materialized.directed = materialized.kind != CONNECTED
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
        draft.world.hooks[hook.id] = hook
        facts.append(_materialized(f"hook {hook.id}", {"hook_id": hook.id}))
    return facts


def _materialized(what: str, data: dict[str, JsonValue]) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(source=CORE, kind="canon_materialized", trace=f"materialized {what}", data=data)
