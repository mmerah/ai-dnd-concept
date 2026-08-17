from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.advancement import Advancement, ProposalBase
from aidm.state.base import Counter, Entity, EntityId, Frozen
from aidm.state.facts import Fact, explained_fact
from aidm.state.world import GameState

from .mechanics import Mechanics, Sheet

GROWTH = (
    "Say how the character has changed over this adventure. Each change is one of four: a "
    "new skill, a new piece of signature gear, a new frailty, or one tag they already carry "
    "rewritten."
)


class Change(Frozen):
    """One change the post-adventure update writes."""

    kind: Literal["skill", "gear", "frailty", "rewrite"] = Field(
        description="Which of the four growths this change spends."
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

    @model_validator(mode="after")
    def _rewrite_names_what_it_becomes(self) -> Self:
        if bool(self.into) != (self.kind == "rewrite"):
            raise ValueError("`into` belongs to a rewrite and to nothing else")
        return self


class AdventureGrowth(ProposalBase):
    """Everything this adventure changed on the sheet, at once, as the post-adventure update."""

    changes: tuple[Change, ...] = Field(
        min_length=1,
        max_length=4,
        description="Each change: a new skill, new gear, a new frailty, or one rewrite.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class Loner3eAdvancement(Advancement):
    proposal_type = AdventureGrowth
    ledger_key = "milestones"
    occasion = "finishes an adventure"
    offer_text = GROWTH
    spent_why = "a milestone spent"

    def ledger(self, state: GameState, subject_id: EntityId) -> Counter:
        return state.mechanics_as(Mechanics).sheets[subject_id].milestones

    def earned(self, state: GameState) -> int:
        return state.mechanics_as(Mechanics).completed.current

    def grant(
        self, draft: GameState, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng  # post-adventure growth spends nothing random
        assert isinstance(proposal, AdventureGrowth)
        sheet = draft.mechanics_as(Mechanics).sheets[subject_id]
        subject = draft.world.require(subject_id)
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        return tuple(
            _rewrite(sheet, subject, change, proposal.why)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change, proposal.why)
            for change in proposal.changes
        )


def _gain(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    if change.kind == "skill":
        sheet.skills = (*sheet.skills, change.tag)
    elif change.kind == "gear":
        sheet.gear = (*sheet.gear, change.tag)
    else:
        sheet.frailties = (*sheet.frailties, change.tag)
    return explained_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag}",
        {"tag": change.tag},
        why,
        narrate=False,
    )


def _rewrite(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    old, new = change.tag, change.into
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
        why,
        narrate=False,
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)
