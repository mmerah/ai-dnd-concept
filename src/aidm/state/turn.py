from typing import Annotated, Literal

from pydantic import Field, JsonValue

from .base import SAVE_VERSION, EntityDetail, EntityId, Frozen, Kind
from .facts import Fact


class Creation(Frozen):
    kind: Kind
    name: str = Field(description="The exact name used in the narration.")
    brief: str = Field(description="One sentence describing it, consistent with the narration.")
    detail: EntityDetail
    location: str | None = Field(
        default=None,
        description=(
            "The place this belongs to: for a person or item where they are, and for a new "
            "location the place it connects to, so the player can walk there. Either a location "
            "already in the catalogue or one created this same turn; null means where the player "
            "is."
        ),
    )


class MemoryProposal(Frozen):
    owner_id: EntityId | None = Field(
        description="Exact id of who this belongs to, or null for the world."
    )
    text: str = Field(
        min_length=1, max_length=300, description="One concrete sentence, past tense."
    )


class WorldkeeperReport(Frozen):
    creations: tuple[Creation, ...] = ()
    memories: tuple[MemoryProposal, ...] = ()


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


class Applied(TraceEntryBase):
    """One advancement change: the same transaction as a turn, without a prompt or a narration."""

    entry: Literal["advancement"] = "advancement"
    subject_id: EntityId


type TraceEntry = Annotated[Turn | Applied, Field(discriminator="entry")]
