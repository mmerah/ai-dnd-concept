from pydantic import Field

from aidm.state.base import EntityId, Frozen


class MemoryProposal(Frozen):
    owner_id: EntityId | None = Field(
        description="Exact id of who this belongs to, or null for the world."
    )
    text: str = Field(
        min_length=1, max_length=300, description="One concrete sentence, past tense."
    )


class WorldkeeperReport(Frozen):
    memories: tuple[MemoryProposal, ...] = ()


class MechanicStep(Frozen):
    tool: str = Field(min_length=1, description="Name of the tool that records this step.")
    instruction: str = Field(
        min_length=1,
        max_length=300,
        description="One sentence telling the Director what to make it do, with exact ids.",
    )
    when: str = Field(
        default="",
        max_length=120,
        description=(
            "Empty when the step always happens. Otherwise the outcome it waits on, in the "
            "words this engine's rules use for how the dice land."
        ),
    )


class TurnInterpretation(Frozen):
    mechanics: tuple[MechanicStep, ...] = Field(
        default=(), description="The mechanics this turn calls for, in the order they happen."
    )
    # No default: an empty answer would otherwise pass for a considered "no mechanics" decision.
    explanation: str = Field(
        min_length=1, max_length=300, description="One line saying why that is the right reading."
    )
