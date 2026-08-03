from aidm.base import Entity
from aidm.facts import Fact

from ..state import Dnd5eActor, Dnd5eItem
from .resolution import Resolution


def reveal(ctx: Resolution, target: Entity | Dnd5eActor | Dnd5eItem) -> list[Fact]:
    """Reveal hidden entities before a fact names them."""
    entity = target if isinstance(target, Entity) else target.entity
    return ctx.draft.reveal(entity)
