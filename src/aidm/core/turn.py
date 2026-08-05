from typing import Annotated, Literal

from pydantic import Field, JsonValue

from .base import SAVE_VERSION, Entity, Frozen, Kind
from .facts import Fact


class GrowthRequest(Frozen):
    kind: Kind
    name: str = Field(description="The exact name used in the narration.")
    brief: str = Field(description="One sentence describing it, consistent with the narration.")
    location: str | None = Field(
        default=None,
        description=(
            "For a person or item, the place they are: a location already in the catalogue, or one "
            "requested this same turn. Null places them where the player is, and is also correct "
            "for a location entry itself."
        ),
    )


class Growth(Frozen):
    requests: tuple[GrowthRequest, ...] = ()


GrowthRejectionReason = Literal["duplicate_name", "over_cap"]


class RejectedGrowth(Frozen):
    request: GrowthRequest
    reason: GrowthRejectionReason


class ScreenedGrowth(Frozen):
    accepted: tuple[GrowthRequest, ...] = ()
    rejected: tuple[RejectedGrowth, ...] = ()


def screen_growth(
    requests: tuple[GrowthRequest, ...],
    existing_names: set[str],
    maximum: int,
) -> ScreenedGrowth:
    accepted: list[GrowthRequest] = []
    rejected: list[RejectedGrowth] = []
    seen = {name.casefold() for name in existing_names}
    for request in requests:
        normalized = request.name.casefold()
        if normalized in seen:
            rejected.append(RejectedGrowth(request=request, reason="duplicate_name"))
        elif len(accepted) >= maximum:
            rejected.append(RejectedGrowth(request=request, reason="over_cap"))
        else:
            accepted.append(request)
            seen.add(normalized)
    return ScreenedGrowth(accepted=tuple(accepted), rejected=tuple(rejected))


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    save_version: int = SAVE_VERSION
    facts: tuple[Fact, ...] = ()


class Turn(TraceEntryBase):
    entry: Literal["turn"] = "turn"
    prompt: str
    plan: dict[str, JsonValue]
    narrator_evidence: str
    narration: str
    growth: Growth
    created: tuple[Entity, ...] = ()
    rejected: tuple[RejectedGrowth, ...] = ()
    prompts: dict[str, str] = Field(default_factory=dict)


class Advance(TraceEntryBase):
    """A level-up: the same transaction as a turn, without a prompt or a narration."""

    entry: Literal["advance"] = "advance"


type TraceEntry = Annotated[Turn | Advance, Field(discriminator="entry")]
