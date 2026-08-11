from typing import Literal

from pydantic import Field, ValidationError

from aidm.engines.counters import Counter, adjust
from aidm.engines.loader import Advancement, Engine
from aidm.state.advancement import AdvancementOffer, ProposalBase
from aidm.state.apply import apply_effect
from aidm.state.base import PLAYER_ID, Entity, Slug
from aidm.state.effects import TraitChange
from aidm.state.facts import Fact
from aidm.state.packs import ContentRef
from aidm.state.world import GameState

from .mechanics import (
    Sheet,
    add_ref,
    counter_of,
    grant_counter,
    read,
    set_number,
    sheet_of,
    write,
)

ADVANCEMENT_READY = "advancement-ready"
LEVEL = "level"
MILESTONE_LEVEL = "milestone-level"
MAX_ABILITY = 20


class PoolGrant(ProposalBase):
    counter: Slug = Field(description="Stable key for the pool, as the feature names it.")
    maximum: int = Field(ge=1, description="How many uses it holds, full when granted.")
    recharge: Literal["short-rest", "long-rest"] = Field(description="What refills it.")


class LevelUp(ProposalBase):
    """One class level. The engine sets `level` and spends the level-up itself."""

    picks: tuple[ContentRef, ...] = Field(
        default=(), description="Exactly the picks the offer asks for, from its options."
    )
    hit_points: int = Field(
        ge=1,
        description="The average of the class hit die (d6 4, d8 5, d10 6, d12 7) plus the "
        "Constitution modifier, at least 1. It raises the hp maximum and fills it.",
    )
    proficiency_bonus: int | None = Field(
        default=None, description="The new proficiency bonus when this level raises it, else null."
    )
    slots: dict[Slug, int] = Field(
        default_factory=dict,
        description="New maximum per `slot-N` this level raises; the added slots arrive filled.",
    )
    granted: tuple[PoolGrant, ...] = Field(
        default=(), description="A pool a newly picked feature brings."
    )
    abilities: dict[Slug, int] = Field(
        default_factory=dict,
        description="An ability score improvement: the new value of each ability raised, never "
        f"above {MAX_ABILITY}.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class Dnd5eAdvancement(Advancement):
    proposal_type = LevelUp

    def __init__(self, engine: Engine) -> None:
        super().__init__(engine.engine_dir)
        self.engine = engine

    def offered(self, state: GameState) -> AdvancementOffer | None:
        player = state.player
        sheet = sheet_of(read(state), player)
        if player.trait(ADVANCEMENT_READY) is None and not _milestone_reached(state, sheet):
            return None
        record = self.engine.record(level_ref(sheet, sheet.numbers[LEVEL] + 1))
        if record is None:
            # The class runs out of level rows at 20, which is the end of advancement, not a fault.
            return None
        return AdvancementOffer(
            prompt=f"{record.name} is ready to take.",
            text=record.text,
            options=record.options,
            choose=record.choose or 0,
        )

    def advance(self, draft: GameState, proposal: ProposalBase) -> tuple[Fact, ...]:
        assert isinstance(proposal, LevelUp)
        mechanics = read(draft)
        player = draft.player
        sheet = sheet_of(mechanics, player)
        why = proposal.why
        facts = [
            *set_number(player, sheet, LEVEL, sheet.numbers[LEVEL] + 1, why),
            *_raise_pool(player, sheet, "hp", proposal.hit_points, why),
        ]
        bonus = proposal.proficiency_bonus
        if bonus is not None:
            facts.extend(set_number(player, sheet, "proficiency-bonus", bonus, why))
        for key, maximum in sorted(proposal.slots.items()):
            counter = counter_of(sheet, player, key)
            facts.extend(_raise_pool(player, sheet, key, maximum - (counter.maximum or 0), why))
        for grant in proposal.granted:
            counter = Counter(current=grant.maximum, maximum=grant.maximum, recharge=grant.recharge)
            facts.append(grant_counter(player, sheet, grant.counter, counter, why))
        for ability, value in sorted(proposal.abilities.items()):
            facts.extend(set_number(player, sheet, ability, value, why))
        for ref in proposal.picks:
            facts.append(add_ref(player, sheet, ref, why))
        write(draft, mechanics)
        if player.trait(ADVANCEMENT_READY) is not None:
            change = TraitChange(
                mode="remove", entity_id=PLAYER_ID, trait_id=ADVANCEMENT_READY, why=why
            )
            facts.extend(apply_effect(draft, change))
        return tuple(facts)

    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        assert isinstance(proposal, LevelUp)
        if outside := sorted(str(ref) for ref in proposal.picks if ref not in offer.options):
            allowed = ", ".join(str(ref) for ref in offer.options) or "(none)"
            return f"{', '.join(outside)} is not on offer here. The legal picks are: {allowed}"
        if len(proposal.picks) != offer.choose:
            return (
                f"this offer takes exactly {offer.choose} picks, the proposal makes "
                f"{len(proposal.picks)}"
            )
        if high := sorted(k for k, v in proposal.abilities.items() if v > MAX_ABILITY):
            return f"an ability score cannot pass {MAX_ABILITY}: {high}"
        draft = state.draft()
        try:
            _ = self.advance(draft, proposal)
            _ = draft.committed()
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return None


def _milestone_reached(state: GameState, sheet: Sheet) -> bool:
    here = sheet_of(read(state), state.world.require(state.player_location))
    earned = here.numbers.get(MILESTONE_LEVEL)
    return earned is not None and sheet.numbers[LEVEL] < earned


def _raise_pool(player: Entity, sheet: Sheet, key: Slug, added: int, why: str) -> list[Fact]:
    """A pool grows by its ceiling and by what fills the room, so a level-up is felt at once."""
    counter = counter_of(sheet, player, key)
    if added <= 0:
        return []
    counter.maximum = (counter.maximum or 0) + added
    return adjust(player, key, counter, added, why)


def level_ref(sheet: Sheet, level: int) -> ContentRef:
    classes = [ref for ref in sheet.refs if ref.collection == "classes"]
    if len(classes) != 1:
        held = ", ".join(str(ref) for ref in classes) or "(none)"
        raise ValueError(f"a 5e character advances by exactly one class, and this one holds {held}")
    return classes[0].sibling("levels", f"{classes[0].index}-{level}")
