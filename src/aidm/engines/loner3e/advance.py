from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.advancement import ProposalBase, ThreadAdvancement
from aidm.state.base import Counter, Entity, EntityId
from aidm.state.facts import Fact, explained_fact
from aidm.state.world import GameState

from .mechanics import Mechanics, Sheet

GROWTH = (
    "Say how the character has changed. One change only: a new skill, a new piece of "
    "signature gear, a new frailty, or one tag they already carry rewritten."
)


class Milestone(ProposalBase):
    """The one change a milestone buys. The engine records the milestone itself."""

    change: Literal["skill", "gear", "frailty", "rewrite"] = Field(
        description="Which of the four growths this milestone spends."
    )
    tag: str = Field(
        min_length=1,
        description="The new tag in title case — or, for a rewrite, the tag already written on "
        "the sheet, copied exactly.",
    )
    into: str = Field(
        default="",
        description="A rewrite only: what that tag becomes, in title case. Empty otherwise.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")

    @model_validator(mode="after")
    def _rewrite_names_what_it_becomes(self) -> Self:
        if bool(self.into) != (self.change == "rewrite"):
            raise ValueError("`into` belongs to a rewrite and to nothing else")
        return self


class Loner3eAdvancement(ThreadAdvancement):
    proposal_type = Milestone
    ledger_key = "milestones"
    occasion = "reaches a milestone"
    offer_text = GROWTH
    spent_why = "a milestone spent"

    def ledger(self, state: GameState, subject_id: EntityId) -> Counter:
        return state.mechanics_as(Mechanics).sheets[subject_id].milestones

    def grant(
        self, draft: GameState, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng  # a milestone spends nothing random
        assert isinstance(proposal, Milestone)
        sheet = draft.mechanics_as(Mechanics).sheets[subject_id]
        subject = draft.world.require(subject_id)
        grown = (
            _rewrite(sheet, subject, proposal)
            if proposal.change == "rewrite"
            else _gain(sheet, subject, proposal)
        )
        return (grown,)


def _gain(sheet: Sheet, subject: Entity, proposal: Milestone) -> Fact:
    if proposal.change == "skill":
        sheet.skills = (*sheet.skills, proposal.tag)
    elif proposal.change == "gear":
        sheet.gear = (*sheet.gear, proposal.tag)
    else:
        sheet.frailties = (*sheet.frailties, proposal.tag)
    return explained_fact(
        subject,
        f"{proposal.change}_gained",
        f"{subject.name} gained {proposal.change} {proposal.tag}",
        {"tag": proposal.tag},
        proposal.why,
        narrate=False,
    )


def _rewrite(sheet: Sheet, subject: Entity, proposal: Milestone) -> Fact:
    old, new = proposal.tag, proposal.into
    if old in sheet.skills:
        sheet.skills = _swapped(sheet.skills, old, new)
    elif old in sheet.frailties:
        sheet.frailties = _swapped(sheet.frailties, old, new)
    elif old in sheet.gear:
        sheet.gear = _swapped(sheet.gear, old, new)
    else:
        raise ValueError(f"{subject.name} carries no tag {old!r} to rewrite")
    return explained_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new}",
        {"was": old, "tag": new},
        proposal.why,
        narrate=False,
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)
