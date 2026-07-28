"""SRD conditions taking hold and lifting."""

from ...content.vocabulary import ConditionName
from ...domain.models import ConditionChanged, EntityId, Event
from . import common
from .resolution import Resolution


def change(
    ctx: Resolution, target_id: EntityId | None, condition: ConditionName, *, active: bool
) -> list[Event]:
    """Immunity and redundancy are absorbed, not narrated: a devil the poison never touched, or a
    second helping of `prone`, changed nothing and so is not an event. `with_condition` is asked
    rather than re-implemented, so the rule cannot drift from the one the reducer applies. The
    reveal happens either way: the Director acted on someone the player must have seen."""
    target = ctx.target(target_id)
    if target.stats.with_condition(condition, active=active) == target.stats:
        return common.reveal(target)
    changed = ConditionChanged(
        target_id=target.id, target_name=target.name, condition=condition, active=active
    )
    return [*common.reveal(target), changed]
