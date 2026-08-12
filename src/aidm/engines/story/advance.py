from typing import Self

from pydantic import Field, ValidationError, model_validator

from aidm.engines.counters import spend
from aidm.engines.loader import Advancement, AdvancementOffer, ProposalBase
from aidm.state.apply import apply_effect, explained_fact
from aidm.state.base import PLAYER_ID, Slug
from aidm.state.effects import TraitChange
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .mechanics import APPROACHES, Approach, read, write

GROWTH_REQUIRED = 3
MAX_APPROACH = 3
MAX_STRESS = 7
OFFER = AdvancementOffer(
    prompt="Three growth marks are ready to spend.",
    text=(
        "Say how the character has changed. One change only: raise an approach, gain an edge or "
        "a bond, leave a burden behind or rewrite it, or become more resilient."
    ),
)


class Growth(ProposalBase):
    """The one change three growth marks buy. The engine spends the marks itself."""

    approach: Approach | None = Field(
        default=None, description="The approach raised by one, or null."
    )
    lose_trait_id: Slug | None = Field(
        default=None,
        description="Exact id of a burden the character leaves behind, or null. With a gain, this "
        "rewrites that burden.",
    )
    gain_trait_id: Slug | None = Field(
        default=None,
        description="Stable hyphenated id of an edge, bond, or rewritten burden gained, or null.",
    )
    gain_text: str = Field(
        default="",
        description="What the gained trait lets the character do, starting `(edge)`, `(bond)`, "
        "or `(burden)`. Required with a gain.",
    )
    resilience: bool = Field(
        default=False, description="True to raise the stress maximum by one instead."
    )
    why: str = Field(description="One short sentence the player reads before confirming.")

    @model_validator(mode="after")
    def _one_change(self) -> Self:
        trait = self.lose_trait_id is not None or self.gain_trait_id is not None
        if [self.approach is not None, trait, self.resilience].count(True) != 1:
            raise ValueError("three growth marks buy exactly one change")
        if (self.gain_trait_id is None) != (not self.gain_text):
            raise ValueError("a gained trait needs its text, and text needs a trait")
        return self


class StoryAdvancement(Advancement):
    proposal_type = Growth

    def offered(self, state: GameState) -> AdvancementOffer | None:
        growth = read(state).actors[PLAYER_ID].growth
        return OFFER if growth.current >= GROWTH_REQUIRED else None

    def advance(self, draft: GameState, proposal: ProposalBase) -> tuple[Fact, ...]:
        assert isinstance(proposal, Growth)
        mechanics = read(draft)
        sheet = mechanics.actors[PLAYER_ID]
        player = draft.player
        facts: list[Fact] = []
        if proposal.approach is not None:
            raised = sheet.raise_approach(proposal.approach)
            facts.append(
                explained_fact(
                    player,
                    "approach_raised",
                    f"{player.name} {proposal.approach} -> {raised}",
                    {"approach": proposal.approach, "value": raised},
                    proposal.why,
                    narrate=False,
                )
            )
        if proposal.resilience:
            stress = sheet.stress
            stress.maximum = (stress.maximum or 0) + 1
            facts.append(
                explained_fact(
                    player,
                    "resilience_gained",
                    f"{player.name} stress maximum -> {stress.maximum}",
                    {"maximum": stress.maximum},
                    proposal.why,
                    narrate=False,
                )
            )
        facts.extend(spend(player, "growth", sheet.growth, GROWTH_REQUIRED, "growth spent"))
        write(draft, mechanics)
        for change in _trait_changes(proposal):
            facts.extend(apply_effect(draft, change))
        return tuple(facts)

    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        del offer
        assert isinstance(proposal, Growth)
        draft = state.draft()
        try:
            _ = self.advance(draft, proposal)
            after = draft.committed()
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return _within_caps(after)


def _trait_changes(proposal: Growth) -> list[TraitChange]:
    changes: list[TraitChange] = []
    if proposal.lose_trait_id is not None:
        changes.append(
            TraitChange(
                mode="remove",
                entity_id=PLAYER_ID,
                trait_id=proposal.lose_trait_id,
                why=proposal.why,
            )
        )
    if proposal.gain_trait_id is not None:
        changes.append(
            TraitChange(
                mode="add",
                entity_id=PLAYER_ID,
                trait_id=proposal.gain_trait_id,
                text=proposal.gain_text,
                why=proposal.why,
            )
        )
    return changes


def _within_caps(after: GameState) -> str | None:
    """Story's caps are absolute, so nothing before the change matters."""
    sheet = read(after).actors[PLAYER_ID]
    if raised := sorted(name for name in APPROACHES if sheet.approach(name) > MAX_APPROACH):
        return f"an approach cannot pass +{MAX_APPROACH}: {raised}"
    stress = sheet.stress.maximum
    if stress is not None and stress > MAX_STRESS:
        return f"the stress maximum cannot pass {MAX_STRESS}, and this proposal reaches {stress}"
    return None
