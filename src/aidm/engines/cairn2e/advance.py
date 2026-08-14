from random import Random

from pydantic import Field

from aidm.engines.advancement import ThreadAdvancement
from aidm.engines.loader import ProposalBase
from aidm.state.base import Counter, EntityId, Trait, text_slug
from aidm.state.facts import Fact, explained_fact
from aidm.state.world import GameState

from .mechanics import Mechanics

GROWTH = (
    "Say how the character has changed. One ability only: name it in title case, and say in one "
    "line what it lets them do and what it costs or limits. The engine records the growth itself, "
    "so propose nothing for it."
)


class Growth(ProposalBase):
    """The one ability a growth leaves behind. The engine records the growth itself."""

    ability: str = Field(min_length=1, description="The new ability in title case.")
    text: str = Field(
        min_length=1,
        description="One line: what it lets them do, and the cost or limit it carries.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class Cairn2eAdvancement(ThreadAdvancement):
    proposal_type = Growth
    ledger_key = "growths"
    occasion = "reaches a growth"
    offer_text = GROWTH
    spent_why = "a growth taken"

    def ledger(self, state: GameState, subject_id: EntityId) -> Counter:
        return state.mechanics_as(Mechanics).sheets[subject_id].growths

    def grant(
        self, draft: GameState, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng  # a growth spends nothing random
        assert isinstance(proposal, Growth)
        subject = draft.world.require(subject_id)
        if any(held.name.lower() == proposal.ability.lower() for held in subject.traits):
            raise ValueError(f"{subject.name} already carries {proposal.ability!r}")
        subject.traits.append(
            Trait(
                id=text_slug(proposal.ability, [held.id for held in subject.traits]),
                name=proposal.ability,
                text=proposal.text,
            )
        )
        grown = explained_fact(
            subject,
            "ability_gained",
            f"{subject.name} gained {proposal.ability}",
            {"ability": proposal.ability},
            proposal.why,
            narrate=False,
        )
        return (grown,)
