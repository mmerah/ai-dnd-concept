from aidm.base import PLAYER_ID, EntityId
from aidm.facts import Fact

from ..access import Dnd5eWorld
from ..content.vocabulary import ConditionName
from ..identity import ENGINE_ID
from ..state import Dnd5eActor
from . import common


def change(
    world: Dnd5eWorld, target_id: EntityId | None, condition: ConditionName, *, ends: bool
) -> list[Fact]:
    target = world.target(target_id)
    active = not ends
    seen: list[Fact] = [*common.reveal(world, target)]
    if not target.stats.apply_condition(condition, active=active):
        return seen
    return [*seen, _condition_changed(target, condition, active=active)]


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
