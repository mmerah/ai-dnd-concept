from aidm.base import Entity
from aidm.facts import Fact

from ..access import Dnd5eWorld
from ..state import Dnd5eActor, Dnd5eItem


def reveal(world: Dnd5eWorld, target: Entity | Dnd5eActor | Dnd5eItem) -> list[Fact]:
    entity = target if isinstance(target, Entity) else target.entity
    return world.state.reveal(entity)
