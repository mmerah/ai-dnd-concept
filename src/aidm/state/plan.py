import json
from collections.abc import Callable
from typing import Literal, cast

from pydantic import Field, JsonValue, ValidationError, model_validator

from .base import Frozen, Slug
from .facts import Fact
from .world import GameState


class Authored(Frozen):
    """Anything the Director writes: one turn's framing, one of its beats, or a call inside one."""

    @model_validator(mode="before")
    @classmethod
    def _decode_stringified_fields(cls, data: object) -> object:
        """Some backends serialize a tool call's nested arguments as JSON; the payload is valid."""
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


class RuleCall(Authored):
    """One call into the engine's vocabulary: what is called, and what it is called with."""

    name: Slug = Field(description="Exact name of the call, as the vocabulary below spells it.")
    args: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Its arguments: exactly the keys the vocabulary lists under that name, and no "
        "others. Empty when every argument sits at its default.",
    )


class DirectorBeat(Authored):
    """One thing put to the dice and what it causes. A turn is one beat, or several when what the
    dice settled asks for another."""

    roll: RuleCall | None = Field(
        default=None,
        description="The one thing this beat puts to the dice, or null when nothing that happens "
        "is uncertain enough to roll.",
    )
    effects: tuple[RuleCall, ...] = Field(
        default=(),
        description="What this beat causes in the world, applied once the roll has settled. Empty "
        "when nothing changes.",
    )


type Followup = Literal["none", "settle", "continue"]


class Resolution(Frozen):
    facts: tuple[Fact, ...] = ()
    outcome: Slug | None = None
    followup: Followup = "continue"


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
