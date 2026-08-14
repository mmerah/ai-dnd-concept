from random import Random

from pydantic import Field

from aidm.engines.counters import adjust, counter_fact, read_mechanics, write_mechanics
from aidm.engines.loader import Offer, ProposalBase, Subsystem
from aidm.engines.sheets import resolved_threads
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.dice import roll_pool
from aidm.state.facts import Fact, explained_fact
from aidm.state.plan import check_draft
from aidm.state.world import GameState

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


class TwentyfourxxAdvancement(Subsystem):
    id = "advancement"
    proposal_type = Advance

    def offers(self, state: GameState) -> tuple[Offer, ...]:
        # One job's advance per resolved thread, tracked directly rather than inferred.
        earned = resolved_threads(state.world)
        sheets = read_mechanics(state, Mechanics).sheets
        return tuple(
            _offer(state, subject_id)
            for subject_id in (PLAYER_ID, *state.world.party())
            if earned > sheets[subject_id].jobs.current
        )

    def resolve(
        self, draft: GameState, offer: Offer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        assert isinstance(proposal, Advance)
        mechanics = read_mechanics(draft, Mechanics)
        sheet = mechanics.sheets[offer.subject_id]
        subject = draft.world.require(offer.subject_id)

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

        sheet.jobs.current += 1
        jobs_fact = counter_fact(subject, "jobs", sheet.jobs, 1, "a job's advance taken")

        write_mechanics(draft, mechanics)
        return (grown, dice_fact, *credit_facts, jobs_fact)

    def violation(self, state: GameState, offer: Offer, proposal: ProposalBase) -> str | None:
        return check_draft(
            state,
            lambda draft: self.resolve(draft, offer, proposal, Random(0)),
            "the sheet this leaves",
        )


def _on_sheet(sheet: Sheet, named: str) -> str:
    """A proposal that miscases a skill must raise the one already written, not take a twin."""
    return next((skill for skill in sheet.skills if skill.lower() == named.lower()), named)


def _offer(state: GameState, subject_id: EntityId) -> Offer:
    return Offer(
        subject_id=subject_id,
        prompt=f"{state.world.require(subject_id).name} finishes a job.",
        text=GROWTH,
    )
