from random import Random

from aidm.engines.loader import Engine, Resolved
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, Slug
from aidm.state.dice import roll
from aidm.state.effects import AdjustCounter, Reveal
from aidm.state.world import GameState, sheet_of

from .actions import Risk

PENALTY: dict[str, int] = {"risky": 0, "demanding": -1, "extreme": -2}
STRONG = 10
MIXED = 7


def resolve_risk(engine: Engine, draft: GameState, action: Risk, rng: Random) -> Resolved:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id), engine.default_rules)
    sheet = sheet_of(draft, actor.id)

    stress = sheet.counters.get("stress")
    if stress is None:
        raise ValueError(f"{actor.name} has no 'stress' pool on their sheet")
    if stress.current == stress.maximum:
        raise ValueError(
            f"{actor.name} is TAKEN OUT: their stress is at its maximum, so they can risk "
            "nothing. Write what their collapse means into `intent` instead."
        )
    if action.hindering_tag_id is not None and sheet.tag(action.hindering_tag_id) is None:
        raise ValueError(
            f"{actor.name} carries no tag '{action.hindering_tag_id}', so nothing hinders them here"
        )
    if action.helping_tag_id is not None and not carries_tag(draft, actor, action.helping_tag_id):
        raise ValueError(
            f"{actor.name} carries no tag '{action.helping_tag_id}', on their own sheet or on an "
            "item they hold, so nothing helps them here"
        )
    if action.approach not in sheet.numbers:
        raise ValueError(f"{actor.name} has no {action.approach!r} on their sheet")

    bonus = (
        sheet.numbers[action.approach]
        + (1 if action.helping_tag_id is not None else 0)
        - (1 if action.hindering_tag_id is not None else 0)
        + PENALTY[action.difficulty]
    )
    rolled, fact = roll("2d6", action.stakes, rng, vs=MIXED, bonus=bonus)
    facts.append(fact)
    outcome: Slug = (
        "strong" if rolled.total >= STRONG else "mixed" if rolled.total >= MIXED else "setback"
    )
    if outcome == "setback" and actor.id == PLAYER_ID:
        facts.extend(
            apply_effect(
                draft,
                AdjustCounter(
                    entity_id=action.actor_id,
                    counter="growth",
                    delta=1,
                    why="a setback earns growth",
                ),
                engine.default_rules,
            )
        )
    return facts, outcome


def carries_tag(draft: GameState, actor: Entity, tag_id: str) -> bool:
    """An edge or a bond sits on the sheet; a gear benefit sits on an item the actor holds."""
    if sheet_of(draft, actor.id).tag(tag_id) is not None:
        return True
    held = draft.world.children(actor.id, "item")
    return any(sheet_of(draft, item.id).tag(tag_id) is not None for item in held)
