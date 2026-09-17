from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.engines.loner3e.world import DIE_FACE, TagKind
from aidm.engines.tools import Attempt

CHANGE_TAGS = "A character here gains tags, loses tags, or both."
DRIVE = "A living character's goal, motive or nemesis changes."
RESTORE_LUCK = "A character's luck refills and any defeat is behind them."
ROLL = (
    "Call this for one closed dramatic question. The engine rolls Chance against "
    "Risk, reads the answer, and moves luck in a conflict."
)
SPEND_LUCK = (
    "A character here spends luck on a cost the selected pack's SPECIAL RULES name, such as a "
    "spell."
)
TWIST_NOTE = (
    "A twist has just interrupted the scene: {subject} / {action}. The narration showed it "
    "arriving. Develop it this turn. Say what it set in motion, what it costs, and what it "
    "changes."
)
DEFEAT_NOTE = (
    "{name} has run out of luck and lost this conflict. Roll nothing more for it. Say how it "
    "ends for them: taken, severely injured, broken off, cornered, or conceding. Write any "
    "lasting mark with `change_tags`, as a `condition`. Then let the story move on. They are "
    "marked defeated and take no new luck exchange until `restore_luck` puts it behind them."
)

type Position = Literal["advantage", "neutral", "disadvantage"]


class ChangeTags(Frozen):
    actor_id: Slug = Field(description="Exact id of the player or someone here.")
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
    actor_id: Slug = Field(description="Exact id of the player or a living character here.")
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
    actor_id: Slug = Field(description="Exact id of the player or a character here.")


class SpendLuck(Frozen):
    actor_id: Slug = Field(description="Exact id of the player or a living character here.")
    amount: int = Field(ge=1, description="The luck spent: the cost the SPECIAL RULES print.")
    why: str = Field(min_length=1, description="What it buys, in one line, read by the player.")


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
    target_id: Slug | None = Field(
        default=None,
        description="Exact id of the character here whose endurance is worn down, for a contest "
        "run as luck exchanges. Null for one decisive question or a single key action, even "
        "against someone who resists.",
    )

    def faces(self) -> tuple[tuple[int, ...], tuple[int, ...]]:
        chance = (DIE_FACE, DIE_FACE) if self.position == "advantage" else (DIE_FACE,)
        risk = (DIE_FACE, DIE_FACE) if self.position == "disadvantage" else (DIE_FACE,)
        return chance, risk
