import json
from collections.abc import Callable, Sequence
from random import Random
from typing import Literal, cast

from pydantic import Field, ValidationError, model_validator

from .base import EntityId, Frozen, Slug
from .facts import Fact
from .world import GameState


class Authored(Frozen):
    """Anything the Director writes: one turn's framing, or one of its beats."""

    @model_validator(mode="before")
    @classmethod
    def _decode_stringified_fields(cls, data: object) -> object:
        """Some OpenAI-compatible backends serialize a tool call's nested arguments as JSON
        strings; the payload inside is valid, so decode it instead of dying on the transport."""
        if not isinstance(data, dict):
            return data
        decoded = cast("dict[object, object]", data).copy()
        for key, value in decoded.items():
            if not isinstance(value, str) or value[:1] not in "{[":
                continue
            try:
                loaded = json.loads(value)
            except ValueError:
                continue
            if isinstance(loaded, (dict, list)):
                decoded[key] = loaded
        return decoded


class TurnPlanBase(Authored):
    """How the turn is framed. What it does is its beats."""

    focus: str = Field(
        description="1-2 sentences: what the player is reaching for and what this turn is about."
    )
    speaker_id: EntityId | None = Field(
        default=None,
        description=(
            "Exact id of the NPC the player addresses — one they have met and who is here with "
            "them — or null if nobody is addressed."
        ),
    )


class Beat[E, A](Authored):
    """One action and what it causes, over the engine's own vocabulary. A turn is one beat, or
    several when what the dice settled asks for another."""

    effects: tuple[E, ...] = Field(
        description="What this beat causes in the world, applied once the action has settled. "
        "Empty when nothing changes."
    )
    action: A | None = None


type Flow = Literal["continue", "yield-to-player"]


class Resolution(Frozen):
    """What one resolution settled, and whether the turn may go on without asking the player."""

    facts: tuple[Fact, ...] = ()
    outcome: Slug | None = None
    flow: Flow = "continue"


type Apply[E] = Callable[[GameState, E], list[Fact]]
type Resolver = Callable[[GameState, Random], Resolution]


def apply_all[E](draft: GameState, effects: Sequence[E], apply: Apply[E]) -> list[Fact]:
    return [fact for effect in effects for fact in apply(draft, effect)]


def check_beat[E, A](
    state: GameState, beat: Beat[E, A], apply: Apply[E], resolve: Resolver | None
) -> str | None:
    """One trial in the order the beat runs: a trial roll first, then what it causes."""

    def played(draft: GameState) -> None:
        if resolve is not None:
            _ = resolve(draft, Random(0))
        _ = apply_all(draft, beat.effects, apply)

    return check_draft(state, played)


def resolve_beat[E, A](
    draft: GameState, beat: Beat[E, A], apply: Apply[E], resolve: Resolver | None, rng: Random
) -> Resolution:
    if resolve is None:
        return Resolution(facts=tuple(apply_all(draft, beat.effects, apply)))
    settled = resolve(draft, rng)
    facts = (*settled.facts, *apply_all(draft, beat.effects, apply))
    return Resolution(facts=facts, outcome=settled.outcome, flow=settled.flow)


def check_draft(
    state: GameState, act: Callable[[GameState], object], what: str = "the state this leaves"
) -> str | None:
    draft = state.draft()
    try:
        _ = act(draft)
        _ = draft.committed()
    except ValidationError as broken:
        return f"{what} is invalid: {broken.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None
