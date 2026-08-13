from typing import Self

from pydantic import Field, ValidationError, model_validator

from aidm.engines.counters import counter_fact
from aidm.engines.loader import Advancement, AdvancementOffer, ProposalBase
from aidm.state.apply import explained_fact
from aidm.state.base import PLAYER_ID
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .mechanics import read, write

MAX_EDGES = 4
MAX_GEAR = 4
OFFER = AdvancementOffer(
    prompt="A milestone is reached.",
    text=(
        "Say how the character has changed. One change only: a new edge, a new piece of "
        "signature gear, or a burden left behind."
    ),
)


class Milestone(ProposalBase):
    """The one change a milestone buys. The engine records the milestone itself."""

    gain_edge: str = Field(default="", description="A new capability tag in title case, or empty.")
    gain_gear: str = Field(
        default="", description="A new signature gear tag in title case, or empty."
    )
    lose_burden: str = Field(
        default="",
        description="A burden written on the sheet, copied exactly, that the character leaves "
        "behind — or empty.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")

    @model_validator(mode="after")
    def _one_change(self) -> Self:
        if [bool(self.gain_edge), bool(self.gain_gear), bool(self.lose_burden)].count(True) != 1:
            raise ValueError("a milestone buys exactly one change")
        return self


class OracleAdvancement(Advancement):
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
        facts: list[Fact] = []
        if proposal.gain_edge:
            sheet.edges = (*sheet.edges, proposal.gain_edge)
            facts.append(
                explained_fact(
                    player,
                    "edge_gained",
                    f"{player.name} gained edge {proposal.gain_edge}",
                    {"edge": proposal.gain_edge},
                    proposal.why,
                    narrate=False,
                )
            )
        if proposal.gain_gear:
            sheet.gear = (*sheet.gear, proposal.gain_gear)
            facts.append(
                explained_fact(
                    player,
                    "gear_gained",
                    f"{player.name} gained gear {proposal.gain_gear}",
                    {"gear": proposal.gain_gear},
                    proposal.why,
                    narrate=False,
                )
            )
        if proposal.lose_burden:
            if proposal.lose_burden not in sheet.burdens:
                raise ValueError(f"{player.name} carries no burden {proposal.lose_burden!r}")
            sheet.burdens = tuple(b for b in sheet.burdens if b != proposal.lose_burden)
            facts.append(
                explained_fact(
                    player,
                    "burden_left",
                    f"{player.name} left burden {proposal.lose_burden} behind",
                    {"burden": proposal.lose_burden},
                    proposal.why,
                    narrate=False,
                )
            )
        sheet.milestones.current += 1
        facts.append(counter_fact(player, "milestones", sheet.milestones, 1, "a milestone spent"))
        write(draft, mechanics)
        return tuple(facts)

    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        del offer
        assert isinstance(proposal, Milestone)
        draft = state.draft()
        try:
            _ = self.advance(draft, proposal)
            after = draft.committed()
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return _within_caps(after)


def _within_caps(after: GameState) -> str | None:
    sheet = read(after).sheets[PLAYER_ID]
    if len(sheet.edges) > MAX_EDGES:
        return (
            f"a character holds at most {MAX_EDGES} edges, and this proposal reaches "
            f"{len(sheet.edges)}"
        )
    if len(sheet.gear) > MAX_GEAR:
        return (
            f"a character holds at most {MAX_GEAR} gear, and this proposal reaches "
            f"{len(sheet.gear)}"
        )
    return None
