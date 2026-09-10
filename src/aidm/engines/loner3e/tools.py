from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Discriminator, Field

from aidm.core.entities import CheckedEntityId, Frozen, Slug
from aidm.core.play import DecisionOption
from aidm.core.tools import Attempt
from aidm.engines import base
from aidm.engines.base import JoinParty, LeaveParty
from aidm.engines.loner3e.world import TagKind
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal

AND_AT = 4  # both dice 4+ sharpens the answer to -and
BUT_AT = 3  # both dice 3 or under softens it to -but

type Position = Literal["advantage", "neutral", "disadvantage"]


class ChangeTags(Frozen):
    """A character here gains tags, loses tags, or both."""

    verb: Literal["change_tags"]
    entity_id: CheckedEntityId = Field(description="Exact id of the player or someone here.")
    kind: TagKind = Field(
        description="`gear` for a thing taken or lost. `condition` for a lasting mark such as "
        "`Poisoned`."
    )
    gained: tuple[str, ...] = Field(
        default=(), description="Title-case tags gained, such as `Rusty Key`."
    )
    lost: tuple[str, ...] = Field(default=(), description="Exact tags lost, lifted or used up.")


class Drive(Frozen):
    """A living character's goal, motive or nemesis changes."""

    verb: Literal["drive"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of the player or a living character here."
    )
    goal: str = Field(
        default="",
        description="What they now pursue, in one line. Empty keeps the current goal.",
    )
    motive: str = Field(default="", description="Why, in one line. Empty keeps the current motive.")
    nemesis: str = Field(
        default="", description="Who or what stands in their way. Empty keeps the current nemesis."
    )


class RestoreLuck(Frozen):
    """A character's luck refills."""

    verb: Literal["restore_luck"]
    entity_id: CheckedEntityId = Field(description="Exact id of the player or a character here.")


type WorldChange = (
    Reveal | Enter | Leave | ChangeTags | Drive | Kill | JoinParty | LeaveParty | RestoreLuck
)


ChangeWorld = base.ChangeWorld[Annotated[WorldChange, Discriminator("verb")]]


class Question(Attempt):
    actor_id: CheckedEntityId = Field(description="Exact id of the character here who acts.")
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
    opponent_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of the character here that resists. Null when nothing fights back.",
    )


class Outcome(Frozen):
    name: Slug
    harm: int

    @property
    def told(self) -> str:
        """The answer in story words: the narrator never reads the rules."""
        return TOLD[self.name]


TOLD: dict[str, str] = {
    "yes-and": "yes, and better than hoped",
    "yes": "yes",
    "yes-but": "yes, but at a cost",
    "no-but": "no, but not badly",
    "no": "no",
    "no-and": "no, and worse",
}


def outcome_for(chance: int, risk: int) -> Outcome:
    if chance == risk:
        return Outcome(name="yes-but", harm=1)
    side, sign = ("yes", 1) if chance > risk else ("no", -1)
    if min(chance, risk) >= AND_AT:
        return Outcome(name=f"{side}-and", harm=3 * sign)
    if max(chance, risk) <= BUT_AT:
        return Outcome(name=f"{side}-but", harm=sign)
    return Outcome(name=side, harm=2 * sign)


def twist_pairing(
    subject: int, action: int, twists: tuple[tuple[str, str], ...]
) -> tuple[str, str]:
    return twists[subject - 1][0], twists[action - 1][1]


def twist_note(subject: str, action: str) -> str:
    return (
        f"A twist has just interrupted the scene: {subject.upper()} / {action.upper()}. The "
        "narration showed it arriving. Develop it this turn. Say what it set in motion, what "
        "it costs, and what it changes."
    )


def defeat_note(name: str) -> str:
    return (
        f"{name} has run out of luck and lost this conflict. Roll nothing more for it. Say how "
        "it ends for them: taken, severely injured, broken off, cornered, or conceding. Write "
        "any lasting mark with the `change_tags` arm, as a `condition`. Then let the story "
        "move on."
    )


def pack_meanings(
    entries: Sequence[DecisionOption], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)
