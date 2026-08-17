from abc import ABC, abstractmethod
from pathlib import Path
from random import Random
from typing import ClassVar

from aidm.content.store import engine_text
from aidm.state.base import PLAYER_ID, Counter, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.plan import check_draft
from aidm.state.world import GameState

from .counters import counter_fact


class Offer(Frozen):
    """One change advancement holds open for one subject, already resolved out of content."""

    subject_id: EntityId
    prompt: str
    text: str = ""


class ProposalBase(Frozen):
    """What the advisor writes, in the engine's own vocabulary."""


class Advancement(ABC):
    """One advance per boundary the fiction closed, per party member."""

    id: ClassVar[Slug] = "advancement"
    proposal_type: ClassVar[type[ProposalBase]]
    ledger_key: ClassVar[Slug]
    occasion: ClassVar[str]
    offer_text: ClassVar[str]
    spent_why: ClassVar[str]

    def __init__(self, engine_dir: Path) -> None:
        self.instructions = engine_text(engine_dir / f"{self.id}.md")

    def offers(self, state: GameState) -> tuple[Offer, ...]:
        earned = self.earned(state)
        return tuple(
            Offer(
                subject_id=subject_id,
                prompt=f"{state.world.require(subject_id).name} {self.occasion}.",
                text=self.offer_text,
            )
            for subject_id in (PLAYER_ID, *state.world.party())
            if earned > self.ledger(state, subject_id).current
        )

    def resolve(
        self, draft: GameState, offer: Offer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        granted = self.grant(draft, offer.subject_id, proposal, rng)
        ledger = self.ledger(draft, offer.subject_id)
        ledger.current += 1
        subject = draft.world.require(offer.subject_id)
        return (*granted, counter_fact(subject, self.ledger_key, ledger, 1, self.spent_why))

    def violation(self, state: GameState, offer: Offer, proposal: ProposalBase) -> str | None:
        return check_draft(
            state,
            lambda draft: self.resolve(draft, offer, proposal, Random(0)),
            "the sheet this leaves",
        )

    @abstractmethod
    def ledger(self, state: GameState, subject_id: EntityId) -> Counter: ...

    @abstractmethod
    def earned(self, state: GameState) -> int:
        """How many boundaries the fiction has closed: what an advance is owed against."""

    @abstractmethod
    def grant(
        self, draft: GameState, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        """Writes what the proposal buys; moving the ledger itself belongs to the base."""
