from aidm.base import PLAYER_ID
from aidm.facts import Fact

from ..content.vocabulary import ConditionName
from ..direction import ApplyCondition
from ..identity import ENGINE_ID
from ..state import Dnd5eActor
from . import common
from .resolution import Resolution


def change(ctx: Resolution, consequence: ApplyCondition) -> list[Fact]:
    """Suppress unchanged conditions while still revealing the target."""
    target = ctx.target(consequence.target_id)
    active = not consequence.ends
    seen: list[Fact] = [*common.reveal(ctx, target)]
    if not target.stats.apply_condition(consequence.condition, active=active):
        return seen
    return [*seen, _condition_changed(target, consequence.condition, active=active)]


def _condition_changed(target: Dnd5eActor, condition: ConditionName, *, active: bool) -> Fact:
    who = "the player" if target.id == PLAYER_ID else target.name
    held = "is" if active else "is no longer"
    trace = f"{who} {held} {condition}"
    return Fact(
        source=ENGINE_ID,
        kind="condition_changed",
        trace=trace,
        narrator=trace,
        data={
            "target_id": target.id,
            "target_name": target.name,
            "condition": condition,
            "active": active,
        },
    )
