from random import Random

from aidm.engines.counters import adjust
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, Slug
from aidm.state.dice import roll
from aidm.state.effects import Reveal
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .actions import Risk
from .mechanics import Adventurer, read, write

PENALTY: dict[str, int] = {"risky": 0, "demanding": -1, "extreme": -2}
STRONG = 10
MIXED = 7


def resolve_risk(draft: GameState, action: Risk, rng: Random) -> tuple[list[Fact], Slug]:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    mechanics = read(draft)
    sheet = mechanics.actors.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no story sheet")
    _refuse_unless_ready(actor, sheet, action, draft)

    bonus = (
        sheet.approach(action.approach)
        + (1 if action.helping_trait_id is not None else 0)
        - (1 if action.hindering_trait_id is not None else 0)
        + PENALTY[action.difficulty]
    )
    rolled, fact = roll("2d6", action.stakes, rng, vs=MIXED, bonus=bonus)
    facts.append(fact)
    outcome: Slug = (
        "strong" if rolled.total >= STRONG else "mixed" if rolled.total >= MIXED else "setback"
    )
    if outcome == "setback" and actor.id == PLAYER_ID:
        facts.extend(adjust(actor, "growth", sheet.growth, 1, "a setback earns growth"))
    write(draft, mechanics)
    return facts, outcome


def _refuse_unless_ready(actor: Entity, sheet: Adventurer, action: Risk, draft: GameState) -> None:
    if sheet.stress.current == sheet.stress.maximum:
        raise ValueError(
            f"{actor.name} is TAKEN OUT: their stress is at its maximum, so they can risk "
            "nothing. Leave `action` null; what their collapse changes belongs in `effects`."
        )
    if action.hindering_trait_id is not None and actor.trait(action.hindering_trait_id) is None:
        raise ValueError(
            f"{actor.name} carries no trait '{action.hindering_trait_id}', so nothing hinders "
            "them here"
        )
    if action.helping_trait_id is not None and not carries_trait(
        draft, actor, action.helping_trait_id
    ):
        raise ValueError(
            f"{actor.name} carries no trait '{action.helping_trait_id}', on themselves or on an "
            "item they hold, so nothing helps them here"
        )


def carries_trait(draft: GameState, actor: Entity, trait_id: str) -> bool:
    """An edge or a bond sits on the actor; a gear benefit sits on an item the actor holds."""
    if actor.trait(trait_id) is not None:
        return True
    return any(item.trait(trait_id) is not None for item in draft.world.children(actor.id, "item"))
