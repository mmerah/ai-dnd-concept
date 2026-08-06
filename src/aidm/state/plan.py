import json
from collections.abc import Callable, Sequence
from typing import cast

from pydantic import Field, ValidationError, model_validator

from .base import PLAYER_ID, Entity, EntityId, Frozen, Slug
from .effects import Effect, apply_effect
from .facts import Fact
from .sheet import Sheet
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


class OutcomeBranch(Frozen):
    """What follows in the fiction if the action lands on this outcome, and only then."""

    outcome: Slug = Field(description="One outcome label the chosen action allows.")
    effects: tuple[Effect, ...] = Field(
        default=(), description="What that outcome causes in the world."
    )


class TurnPlanBase(Frozen):
    """One turn, answered in one plan: the engine rolls, picks the outcome, and applies it."""

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

    intent: str = Field(
        description="1-3 sentences for the Narrator: what the player attempted and what is at "
        "stake. Never an outcome, a number, or a die."
    )
    tone: str = Field(
        description="A few words of mood. Atmosphere only: 'tense and hushed', not 'they find it'."
    )
    speaker_id: EntityId | None = Field(
        default=None,
        description="Exact id of the NPC the player addresses — one they have met and who is here "
        "with them — or null if nobody is addressed.",
    )
    effects: tuple[Effect, ...] = Field(
        default=(), description="Consequences that happen whatever the action settles."
    )
    branches: tuple[OutcomeBranch, ...] = Field(
        default=(),
        description="Consequences keyed by outcome: at most one branch per label, and only labels "
        "this action allows. Outcomes that do not occur simply never apply. An action rolled to "
        "cause a lasting change — a condition taking hold or lifted, something revealed — must "
        "carry that change in the matching outcome's branch: with no branch, even success "
        "changes nothing.",
    )


def apply_branch(
    draft: GameState,
    plan: TurnPlanBase,
    outcome: Slug,
    default_rules: Callable[[Entity], Sheet],
) -> list[Fact]:
    """An outcome the model wrote no branch for is fine: not every outcome needs consequences."""
    branch = next((held for held in plan.branches if held.outcome == outcome), None)
    if branch is None:
        return []
    return [
        fact for effect in branch.effects for fact in apply_effect(draft, effect, default_rules)
    ]


def check_plan_base(
    state: GameState,
    plan: TurnPlanBase,
    labels: frozenset[Slug],
    default_rules: Callable[[Entity], Sheet],
) -> str | None:
    """What every engine's plan check shares: the speaker guard, the outcome labels this action
    allows, and a trial application of the effects against the state as it stands."""
    if fault := check_speaker(state, plan.speaker_id):
        return fault
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
        if fault := _trial(state, group, default_rules):
            return fault
    return None


def _trial(
    state: GameState, effects: Sequence[Effect], default_rules: Callable[[Entity], Sheet]
) -> str | None:
    draft = state.draft()
    try:
        for effect in effects:
            _ = apply_effect(draft, effect, default_rules)
        _ = draft.committed()
    except ValidationError as invalid:
        return f"the state this leaves is invalid: {invalid.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None
