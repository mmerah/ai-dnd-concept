from ...domain.models.consequences import ApplyCondition
from ...domain.models.facts import ConditionChanged, Emitted
from . import common
from .resolution import Resolution


def change(ctx: Resolution, consequence: ApplyCondition) -> list[Emitted]:
    """Suppress unchanged conditions while still revealing the target."""
    target = ctx.target(consequence.target_id)
    active = not consequence.ends
    seen: list[Emitted] = [*common.reveal(ctx, target)]
    if not target.stats.apply_condition(consequence.condition, active=active):
        return seen
    changed = ConditionChanged(
        target_id=target.id,
        target_name=target.name,
        condition=consequence.condition,
        active=active,
    )
    return [*seen, changed]
