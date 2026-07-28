"""SRD conditions taking hold and lifting."""

from ...domain.models import ApplyCondition, ConditionChanged, Event
from . import common
from .resolution import Resolution


def change(ctx: Resolution, consequence: ApplyCondition) -> list[Event]:
    """Immunity and redundancy are absorbed, not narrated: a devil the poison never touched, or a
    second helping of `prone`, changed nothing and so is not an event. `with_condition` is asked
    rather than re-implemented, so the rule cannot drift from the one the reducer applies. The
    reveal happens either way: the Director acted on someone the player must have seen."""
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
