from random import Random

from pydantic import Field

from aidm.engines.advancement import Advancement, ProposalBase
from aidm.engines.counters import adjust
from aidm.state.base import Counter, EntityId
from aidm.state.dice import roll_pool
from aidm.state.facts import Fact, explained_fact
from aidm.state.world import Game

from .mechanics import Mechanics, Sheet, raised

GROWTH = (
    "Say which skill this job improves. One skill only: a skill already on the sheet rises a "
    "step up the ladder, or a new one is taken at d8. The engine pays the d6 credits and records "
    "the job itself, so propose neither."
)


class Advance(ProposalBase):
    """The one change a job buys. The engine pays the credits and records the job itself."""

    skill: str = Field(
        min_length=1,
        description="The skill this job improves, in title case: one already on the sheet to "
        "raise it a step, or a new one to take at d8.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class TwentyfourxxAdvancement(Advancement):
    proposal_type = Advance
    ledger_key = "jobs"
    occasion = "finishes a job"
    offer_text = GROWTH
    spent_why = "a job's advance taken"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of(state).sheets[subject_id].jobs

    def earned(self, state: Game) -> int:
        return Mechanics.of(state).completed.current

    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        assert isinstance(proposal, Advance)
        sheet = Mechanics.of(draft).sheets[subject_id]
        subject = draft.world.require(subject_id)

        skill = _on_sheet(sheet, proposal.skill)
        die = raised(sheet.skills.get(skill))
        sheet.skills[skill] = die
        grown = explained_fact(
            subject,
            "skill_increased",
            f"{subject.name} raised {skill} to d{die}",
            {"skill": skill, "die": die},
            proposal.why,
            narrate=False,
        )

        earned, dice_fact = roll_pool((6,), "credits earned", rng)
        credit_facts = adjust(subject, "credits", sheet.credits, earned, "paid for the job")
        return (grown, dice_fact, *credit_facts)


def _on_sheet(sheet: Sheet, named: str) -> str:
    """A proposal that miscases a skill must raise the one already written, not take a twin."""
    return next((skill for skill in sheet.skills if skill.lower() == named.lower()), named)
