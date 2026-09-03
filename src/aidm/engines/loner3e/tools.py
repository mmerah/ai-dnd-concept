from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen, Slug
from aidm.core.play import DecisionOption
from aidm.engines.loner3e.world import Loner3eSheet, Loner3eWorld, TagKind
from aidm.engines.scenes.tools import Enter, JoinParty, Kill, Leave, LeaveParty, Reveal

AND_AT = 4  # both dice 4+ sharpens the answer to -and
BUT_AT = 3  # both dice 3 or under softens it to -but

type Position = Literal["advantage", "neutral", "disadvantage"]


class ChangeTags(Frozen):
    """A character here gains or loses tags: a thing taken or lost, a lasting mark, a lesson."""

    verb: Literal["change_tags"]
    entity_id: CheckedEntityId = Field(description="Exact id of the player or someone here.")
    kind: TagKind = Field(
        description="`gear` for a thing taken or lost; `condition` for a lasting mark such as "
        "`Battle Worn` or `Poisoned`; `skill` or `frailty` only when the story plainly wrote one."
    )
    gained: tuple[str, ...] = Field(
        default=(), description="Title-case tags gained, such as `Rusty Key`."
    )
    lost: tuple[str, ...] = Field(default=(), description="Exact tags lost, lifted or used up.")


class Drive(Frozen):
    """What a living character wants, why, and who stands in their way, once play has shown it."""

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


type WorldChange = Reveal | Enter | Leave | ChangeTags | Drive | Kill | JoinParty | LeaveParty


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Question(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the player or actor here who takes the action."
    )
    question: str = Field(
        min_length=1,
        description="Closed question where yes means the actor gets what they want.",
    )
    position: Position = Field(
        default="neutral",
        description="Which side the relevant tags and situation favour.",
    )
    edge: str = Field(
        default="",
        description="Tag or circumstance that sets the position. Empty for neutral.",
    )
    opponent_id: CheckedEntityId | None = Field(
        default=None,
        description=("Exact id of the character here that resists. Null when nothing fights back."),
    )


class Outcome(Frozen):
    """One of the six answers, carrying the luck an exchange costs the side that lost it."""

    name: Slug
    harm: int


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or a character here.")


def outcome_for(chance: int, risk: int) -> Outcome:
    if chance == risk:
        return Outcome(name="yes-but", harm=1)
    side, sign = ("yes", 1) if chance > risk else ("no", -1)
    if min(chance, risk) >= AND_AT:
        return Outcome(name=f"{side}-and", harm=3 * sign)
    if max(chance, risk) <= BUT_AT:
        return Outcome(name=f"{side}-but", harm=sign)
    return Outcome(name=side, harm=2 * sign)


def conflict_prompt(world: Loner3eWorld, actor: Loner3eSheet, opponent: Loner3eSheet) -> str:
    foe = actor if opponent.id == world.player.id else opponent
    return (
        f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
        "attack, try something else, or break away — what do you do?"
    )


def twist_pairing(
    subject: int, action: int, twists: tuple[tuple[str, str], ...]
) -> tuple[str, str]:
    """Subject from one d6, action from the other, as the SRD's twist table is read."""
    return twists[subject - 1][0], twists[action - 1][1]


def twist_note(subject: str, action: str) -> str:
    return (
        f"A twist has just interrupted the scene: {subject.upper()} / {action.upper()} — the "
        "narration showed it arriving. Develop it this turn: what it set in motion, what it "
        "costs, what it changes."
    )


def defeat_note(name: str) -> str:
    return (
        f"{name} has run out of luck and lost this conflict. Ask nothing further of it: say how it "
        "ends for them — taken, severely injured, broken off, cornered, conceding — write any "
        "lasting mark the ending leaves with `change_tags` (a `condition`), and let the story "
        "move on."
    )


def pack_meanings(
    entries: Sequence[DecisionOption], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)
