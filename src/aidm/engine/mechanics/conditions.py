from ...domain.models.consequences import ApplyCondition
from ...domain.models.events import ConditionChanged, Event
from . import common
from .resolution import Resolution


def change(ctx: Resolution, consequence: ApplyCondition) -> list[Event]:
    """Suppress unchanged conditions while still revealing the target."""
    target = ctx.target(consequence.target_id)
    active = not consequence.ends
    if target.stats.with_condition(consequence.condition, active=active) == target.stats:
        return common.reveal(target)
    changed = ConditionChanged(
        target_id=target.id,
        target_name=target.name,
        condition=consequence.condition,
        active=active,
    )
    return [*common.reveal(target), changed]
