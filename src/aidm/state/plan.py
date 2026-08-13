import json
from collections.abc import Callable, Sequence
from random import Random
from typing import cast

from pydantic import Field, ValidationError, model_validator

from .base import EntityId, Frozen, Slug, duplicates
from .facts import Fact
from .world import GameState


class TurnPlanBase(Frozen):
    """One turn, answered in one plan."""

    focus: str = Field(
        description="1-2 sentences: what the player is reaching for and what this turn is about."
    )
    pressure: str = Field(
        default="",
        description=(
            "1-2 sentences: what pushes back this turn — a complication, a cost, a threat. Empty "
            "when the turn is genuinely quiet and nothing should push back."
        ),
    )
    stakes: str = Field(
        default="",
        description=(
            "One sentence: what the player stands to win or lose. Empty when nothing is at stake."
        ),
    )
    speaker_id: EntityId | None = Field(
        default=None,
        description=(
            "Exact id of the NPC the player addresses — one they have met and who is here with "
            "them — or null if nobody is addressed."
        ),
    )

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


class OutcomeBranch[E](Frozen):
    """What follows in the fiction if the action lands on this outcome, and only then."""

    outcome: Slug = Field(description="One outcome label the chosen action allows.")
    effects: tuple[E, ...] = Field(default=(), description="What that outcome causes in the world.")


class Branched[E](TurnPlanBase):
    """The common plan shape: unconditional effects plus effects per outcome, over the
    engine's own effect vocabulary."""

    effects: tuple[E, ...] = Field(
        default=(), description="Consequences that happen whatever the action settles."
    )
    branches: tuple[OutcomeBranch[E], ...] = Field(
        default=(),
        description="Consequences keyed by outcome: at most one branch per label, and only labels "
        "this action allows. Outcomes that do not occur simply never apply. An action rolled to "
        "cause a lasting change — a condition taking hold or lifted, something revealed — must "
        "carry that change in the matching outcome's branch: with no branch, even success "
        "changes nothing.",
    )


type Apply[E] = Callable[[GameState, E], list[Fact]]


def apply_all[E](draft: GameState, effects: Sequence[E], apply: Apply[E]) -> list[Fact]:
    return [fact for effect in effects for fact in apply(draft, effect)]


def apply_branch[E](
    draft: GameState, plan: Branched[E], outcome: Slug, apply: Apply[E]
) -> list[Fact]:
    """An outcome the model wrote no branch for is fine: not every outcome needs consequences."""
    branch = next((held for held in plan.branches if held.outcome == outcome), None)
    return [] if branch is None else apply_all(draft, branch.effects, apply)


def check_effects[E](
    state: GameState, plan: Branched[E], labels: frozenset[Slug], apply: Apply[E]
) -> str | None:
    named = [branch.outcome for branch in plan.branches]
    if repeated := duplicates(named):
        return f"one branch per outcome, and {repeated} is branched twice"
    if outside := sorted(set(named) - labels):
        allowed = ", ".join(sorted(labels))
        if not allowed:
            return (
                f"this action settles no outcome, so it takes no branches: move what {outside} "
                "would cause into `effects`, or choose an action that can fail"
            )
        return f"{outside} is no outcome of this action. Its outcomes are: {allowed}"
    # Branches are alternatives: each is trialled with the unconditional effects, never a sibling.
    alternatives = [(*branch.effects, *plan.effects) for branch in plan.branches] or [plan.effects]
    for group in alternatives:
        if fault := check_draft(state, _applied(group, apply)):
            return fault
    return None


def check_action[E](
    state: GameState,
    plan: Branched[E],
    labels: frozenset[Slug],
    apply: Apply[E],
    resolve: Callable[[GameState, Random], object],
) -> str | None:
    """An action that cannot resolve is refused before the plan's effects are judged."""
    if refused := check_draft(state, lambda draft: resolve(draft, Random(0))):
        return refused
    return check_effects(state, plan, labels, apply)


def _applied[E](effects: Sequence[E], apply: Apply[E]) -> Callable[[GameState], object]:
    return lambda draft: apply_all(draft, effects, apply)


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
