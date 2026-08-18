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
