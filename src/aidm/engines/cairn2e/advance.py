from random import Random

from pydantic import Field

from aidm.engines.counters import counter_fact, read_mechanics, write_mechanics
from aidm.engines.loader import Offer, ProposalBase, Subsystem
from aidm.engines.sheets import resolved_threads
from aidm.state.base import PLAYER_ID, EntityId, Trait, text_slug
from aidm.state.facts import Fact, explained_fact
from aidm.state.plan import check_draft
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


class Cairn2eAdvancement(Subsystem):
    id = "advancement"
    proposal_type = Growth

    def offers(self, state: GameState) -> tuple[Offer, ...]:
        # Growth-driven and deterministic, never inferred by a model: one growth is earned per
        # resolved thread, so the offer tracks the count directly instead of guessing intent.
        earned = resolved_threads(state.world)
        sheets = read_mechanics(state, Mechanics).sheets
        return tuple(
            _offer(state, subject_id)
            for subject_id in (PLAYER_ID, *state.world.party())
            if earned > sheets[subject_id].growths.current
        )

    def resolve(
        self, draft: GameState, offer: Offer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng  # a growth spends nothing random
        assert isinstance(proposal, Growth)
        mechanics = read_mechanics(draft, Mechanics)
        sheet = mechanics.sheets[offer.subject_id]
        subject = draft.world.require(offer.subject_id)
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
        sheet.growths.current += 1
        spent = counter_fact(subject, "growths", sheet.growths, 1, "a growth taken")
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
        prompt=f"{state.world.require(subject_id).name} reaches a growth.",
        text=GROWTH,
    )
