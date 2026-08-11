import json
from collections.abc import Callable, Sequence
from random import Random
from typing import cast

from pydantic import Field, ValidationError, model_validator

from .base import PLAYER_ID, EntityId, Frozen, Slug
from .facts import Fact
from .world import GameState


def check_speaker(state: GameState, speaker_id: EntityId | None) -> str | None:
    """The player is addressed, never the speaker: losing this lets the Director voice them."""
    if speaker_id is None:
        return None
    if speaker_id == PLAYER_ID:
        return "speaker_id names another actor the player addresses, never the player."
    speaker = state.world.find(speaker_id)
    if speaker is None:
        return f"unknown speaker id {speaker_id!r}. Use only ids you were shown, or null."
    if speaker.kind != "actor" or not speaker.known or not state.is_here(speaker):
        return (
            f"speaker {speaker_id!r} must be an NPC the player has met and who is here with them. "
            "Use null if nobody is being addressed."
        )
    return None


class TurnPlanBase(Frozen):
    """One turn, answered in one plan. Core knows a plan only by this base: every field, every
    effect, and the whole resolution belong to the engine whose plan it is."""

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
    """The plan shape both shipped engines use: unconditional effects plus effects per outcome,
    over that engine's own effect vocabulary."""

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
    """What every engine's plan check shares: the outcome labels this action allows, and a trial
    application of the effects against the state as it stands."""
    named = [branch.outcome for branch in plan.branches]
    if repeated := sorted({name for name in named if named.count(name) > 1}):
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
        if fault := _trial(state, group, apply):
            return fault
    return None


def check_action[E](
    state: GameState,
    plan: Branched[E],
    labels: frozenset[Slug],
    apply: Apply[E],
    resolve: Callable[[GameState, Random], object],
) -> str | None:
    """The trial resolve owes the model every refusal the real resolve raises, so an action that
    cannot resolve is refused before the plan's effects are judged."""
    try:
        _ = resolve(state.draft(), Random(0))
    except ValueError as refused:
        return str(refused)
    return check_effects(state, plan, labels, apply)


def _trial[E](state: GameState, effects: Sequence[E], apply: Apply[E]) -> str | None:
    draft = state.draft()
    try:
        for effect in effects:
            _ = apply(draft, effect)
        _ = draft.committed()
    except ValidationError as invalid:
        return f"the state this leaves is invalid: {invalid.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None
