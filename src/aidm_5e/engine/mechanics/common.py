from aidm.domain.entities import BaseEntity, Entity
from aidm.domain.facts import CoreFact

from ...models import Dnd5eActor, Dnd5eItem
from .resolution import Resolution


def reveal(ctx: Resolution, target: Entity | Dnd5eActor | Dnd5eItem) -> list[CoreFact]:
    """Reveal hidden entities before a fact names them."""
    entity = target if isinstance(target, BaseEntity) else target.entity
    return ctx.draft.reveal(entity)
