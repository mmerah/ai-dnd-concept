from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from aidm.engines.counters import counter_fact
from aidm.engines.loader import Advancement, AdvancementOffer, ProposalBase
from aidm.state.apply import explained_fact
from aidm.state.base import PLAYER_ID, Entity
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .mechanics import Sheet, read, write

OFFER = AdvancementOffer(
    prompt="A milestone is reached.",
    text=(
        "Say how the character has changed. One change only: a new skill, a new piece of "
        "signature gear, a new frailty, or one tag they already carry rewritten."
    ),
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


class Loner3eAdvancement(Advancement):
    proposal_type = Milestone

    def offered(self, state: GameState) -> AdvancementOffer | None:
        # Milestone-driven and deterministic, never inferred by a model: one milestone is earned
        # per resolved thread, so the offer tracks the count directly instead of guessing intent.
        earned = sum(1 for thread in state.world.threads.values() if thread.status == "resolved")
        sheet = read(state).sheets[PLAYER_ID]
        return OFFER if earned > sheet.milestones.current else None

    def advance(self, draft: GameState, proposal: ProposalBase) -> tuple[Fact, ...]:
        assert isinstance(proposal, Milestone)
        mechanics = read(draft)
        sheet = mechanics.sheets[PLAYER_ID]
        player = draft.player
        grown = (
            _rewrite(sheet, player, proposal)
            if proposal.change == "rewrite"
            else _gain(sheet, player, proposal)
        )
        sheet.milestones.current += 1
        spent = counter_fact(player, "milestones", sheet.milestones, 1, "a milestone spent")
        write(draft, mechanics)
        return (grown, spent)

    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        del offer
        assert isinstance(proposal, Milestone)
        draft = state.draft()
        try:
            _ = self.advance(draft, proposal)
            _ = draft.committed()
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return None


def _gain(sheet: Sheet, player: Entity, proposal: Milestone) -> Fact:
    if proposal.change == "skill":
        sheet.skills = (*sheet.skills, proposal.tag)
    elif proposal.change == "gear":
        sheet.gear = (*sheet.gear, proposal.tag)
    else:
        sheet.frailties = (*sheet.frailties, proposal.tag)
    return explained_fact(
        player,
        f"{proposal.change}_gained",
        f"{player.name} gained {proposal.change} {proposal.tag}",
        {"tag": proposal.tag},
        proposal.why,
        narrate=False,
    )


def _rewrite(sheet: Sheet, player: Entity, proposal: Milestone) -> Fact:
    old, new = proposal.tag, proposal.into
    if old in sheet.skills:
        sheet.skills = _swapped(sheet.skills, old, new)
    elif old in sheet.frailties:
        sheet.frailties = _swapped(sheet.frailties, old, new)
    elif old in sheet.gear:
        sheet.gear = _swapped(sheet.gear, old, new)
    else:
        raise ValueError(f"{player.name} carries no tag {old!r} to rewrite")
    return explained_fact(
        player,
        "tag_rewritten",
        f"{player.name} rewrote {old} as {new}",
        {"was": old, "tag": new},
        proposal.why,
        narrate=False,
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)
