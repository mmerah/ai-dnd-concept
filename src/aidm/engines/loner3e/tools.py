from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.engines.base import Attempt
from aidm.engines.loner3e.world import TagKind

CHANGE_TAGS = "A character here gains tags, loses tags, or both."
DRIVE = "A living character's goal, motive or nemesis changes."
RESTORE_LUCK = "A character's luck refills."
ROLL = (
    "Call this for one closed dramatic question. The engine rolls Chance against "
    "Risk, reads the answer, and moves luck in a conflict."
)

type Position = Literal["advantage", "neutral", "disadvantage"]


class ChangeTags(Frozen):
    entity_id: Slug = Field(description="Exact id of the player or someone here.")
    kind: TagKind = Field(
        description="`gear` for a thing taken or lost. `condition` for a lasting mark such as "
        "`Poisoned`."
    )
    gained: tuple[str, ...] = Field(
        default=(), description="Title-case tags gained, such as `Rusty Key`."
    )
    lost: tuple[str, ...] = Field(default=(), description="Exact tags lost, lifted or used up.")

    @model_validator(mode="after")
    def _at_least_one(self) -> Self:
        if not self.gained and not self.lost:
            raise ValueError("at least one gained or lost tag")
        return self


class Drive(Frozen):
    entity_id: Slug = Field(description="Exact id of the player or a living character here.")
    goal: str = Field(
        default="",
        description="What they now pursue, in one line. Empty keeps the current goal.",
    )
    motive: str = Field(default="", description="Why, in one line. Empty keeps the current motive.")
    nemesis: str = Field(
        default="", description="Who or what stands in their way. Empty keeps the current nemesis."
    )

    @model_validator(mode="after")
    def _at_least_one(self) -> Self:
        if not self.goal and not self.motive and not self.nemesis:
            raise ValueError("a goal, a motive or a nemesis")
        return self


class RestoreLuck(Frozen):
    entity_id: Slug = Field(description="Exact id of the player or a character here.")


class Roll(Attempt):
    actor_id: Slug = Field(description="Exact id of the character here who acts.")
    question: str = Field(
        min_length=1,
        description="Closed question where yes means the actor gets what they want. Only you "
        "read it.",
    )
    position: Position = Field(
        default="neutral",
        description="Which side the relevant tags and situation favour.",
    )
    edge: str = Field(
        default="",
        description="Tag or circumstance that sets the position, read by the player. Empty "
        "for neutral.",
    )
    opponent_id: Slug | None = Field(
        default=None,
        description="Exact id of the character here that resists. Null when nothing fights back.",
    )
