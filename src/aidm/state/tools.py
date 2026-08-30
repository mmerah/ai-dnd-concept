from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel, JsonValue

from aidm.state.entities import Frozen
from aidm.state.facts import Fact
from aidm.state.model import AdvanceThread, Game


class NoArgs(Frozen):
    pass


@dataclass(frozen=True, slots=True)
class DirectorTool:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[Game, Mapping[str, JsonValue], Random], tuple[Fact, ...]]
    # World tools may still run in a turn that opened suspended; engine mechanics may not.
    during_suspension: bool = False


def director_tool[A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    resolve: Callable[[Game, A, Random], Sequence[Fact]],
    *,
    during_suspension: bool = False,
) -> DirectorTool:
    """Validation lives here, so both harnesses reject the same arguments the same way."""
    if bare := [key for key, one in args.model_fields.items() if not one.description]:
        raise ValueError(f"{name} parameters the model reads carry no description: {bare}")

    def call(draft: Game, raw: Mapping[str, JsonValue], rng: Random) -> tuple[Fact, ...]:
        return tuple(resolve(draft, args.model_validate(raw), rng))

    return DirectorTool(name, description, args, call, during_suspension)


# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play = Callable[[Game, Random], tuple[Fact, ...]]
type Validate = Callable[[Game], None]


def apply_to_draft(validate: Validate, draft: Game, play: Play, rng: Random) -> tuple[Fact, ...]:
    """Every mutation runs this sequence, so no caller can skip the engine's own gate."""
    before = draft.pending
    landed = play(draft, rng)
    if before is not None and draft.pending is not before:
        raise ValueError("the rules already wait on a decision; they take one at a time")
    for fact in landed:
        if not fact.told or fact.entity_id is None:
            continue
        subject = draft.world.find(fact.entity_id)
        if subject is None:
            raise ValueError(f"a told fact names {fact.entity_id!r}, which the world does not hold")
        if not subject.known:
            raise ValueError(f"a told fact names {fact.entity_id!r}, whom the player has not met")
    validate(draft)
    return landed


def transact(
    validate: Validate, draft: Game, play: Play, rng: Random
) -> tuple[Game, tuple[Fact, ...]]:
    """A draft mutated and committed whole, for a change that stands on its own outside a turn."""
    before = draft.pending
    landed = apply_to_draft(validate, draft, play, rng)
    if draft.pending is not before:
        raise ValueError("a change outside a turn cannot open a decision for the player")
    return draft.committed(), landed


def advance_thread(draft: Game, effect: AdvanceThread) -> list[Fact]:
    """Threads are the Director's bookkeeping, so nothing here reaches the Narrator."""
    thread = draft.world.thread(effect.thread_id)
    if thread is None:
        known = ", ".join(sorted(draft.world.threads)) or "(none)"
        raise ValueError(f"unknown thread {effect.thread_id!r}. The threads are: {known}")
    thread.status = effect.status or thread.status
    if effect.note is not None:
        thread.note = effect.note
    moved = f"thread {thread.title}[{thread.id}] — status {thread.status}"
    if thread.note:
        moved += f" — note: {thread.note}"
    return [Fact(kind="thread_advanced", trace=moved)]
