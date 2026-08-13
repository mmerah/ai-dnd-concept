from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.counters import counter_fact, read_mechanics, write_mechanics
from aidm.engines.loader import Offer, ProposalBase, Subsystem
from aidm.state.base import PLAYER_ID, Entity, EntityId
from aidm.state.facts import Fact, explained_fact
from aidm.state.plan import check_draft
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


class Loner3eAdvancement(Subsystem):
    id = "advancement"
    proposal_type = Milestone

    def offers(self, state: GameState) -> tuple[Offer, ...]:
        # Milestone-driven and deterministic, never inferred by a model: one milestone is earned
        # per resolved thread, so the offer tracks the count directly instead of guessing intent.
        earned = sum(1 for thread in state.world.threads.values() if thread.status == "resolved")
        sheets = read_mechanics(state, Mechanics).sheets
        return tuple(
            _offer(state, subject_id)
            for subject_id in (PLAYER_ID, *state.world.party())
            if earned > sheets[subject_id].milestones.current
        )

    def resolve(
        self, draft: GameState, offer: Offer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng  # a milestone spends nothing random
        assert isinstance(proposal, Milestone)
        mechanics = read_mechanics(draft, Mechanics)
        sheet = mechanics.sheets[offer.subject_id]
        subject = draft.world.require(offer.subject_id)
        grown = (
            _rewrite(sheet, subject, proposal)
            if proposal.change == "rewrite"
            else _gain(sheet, subject, proposal)
        )
        sheet.milestones.current += 1
        spent = counter_fact(subject, "milestones", sheet.milestones, 1, "a milestone spent")
        write_mechanics(draft, mechanics)
        return (grown, spent)

    def violation(self, state: GameState, offer: Offer, proposal: ProposalBase) -> str | None:
        return check_draft(
            state,
            lambda draft: self.resolve(draft, offer, proposal, Random(0)),
            "the sheet this leaves",
        )


def _offer(state: GameState, subject_id: EntityId) -> Offer:
    return Offer(
        subject_id=subject_id,
        prompt=f"{state.world.require(subject_id).name} reaches a milestone.",
        text=GROWTH,
    )


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
