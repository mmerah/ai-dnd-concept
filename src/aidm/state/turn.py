from typing import Annotated, Literal

from pydantic import Field, JsonValue

from .base import SAVE_VERSION, EntityDetail, EntityId, Frozen, Kind, Slug
from .facts import Fact


class Creation(Frozen):
    kind: Kind
    name: str = Field(description="The exact name used in the narration.")
    brief: str = Field(description="One sentence describing it, consistent with the narration.")
    detail: EntityDetail
    location: str | None = Field(
        default=None,
        description=(
            "For a person or item, the place they are: a location already in the catalogue, or one "
            "created this same turn. Null places them where the player is, and is also correct "
            "for a location entry itself."
        ),
    )


class WorldkeeperReport(Frozen):
    creations: tuple[Creation, ...] = ()


class SceneDirective(Frozen):
    """What the turn is about, decided before any rule is touched."""

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
    threads: tuple[Slug, ...] = Field(
        default=(), description="Ids of the active threads this turn serves; none when none apply."
    )
    reveal: tuple[EntityId, ...] = Field(
        default=(),
        description=(
            "Ids of the things the player has not found yet that this turn should bring into "
            "play; none unless the fiction genuinely puts one in front of them."
        ),
    )
    speaker_id: EntityId | None = Field(
        default=None,
        description=(
            "Exact id of the NPC the player addresses — one they have met and who is here with "
            "them — or null if nobody is addressed."
        ),
    )


class StepTrace(Frozen):
    name: str
    prompt: str | None = None
    output: dict[str, JsonValue] | str | None = None


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    save_version: int = SAVE_VERSION
    facts: tuple[Fact, ...] = ()


class Turn(TraceEntryBase):
    entry: Literal["turn"] = "turn"
    prompt: str
    narration: str
    steps: tuple[StepTrace, ...] = ()


class Advance(TraceEntryBase):
    """A level-up: the same transaction as a turn, without a prompt or a narration."""

    entry: Literal["advance"] = "advance"


type TraceEntry = Annotated[Turn | Advance, Field(discriminator="entry")]
