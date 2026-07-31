from typing import Protocol

from aidm.domain.base import EntityId
from aidm.domain.events import EntityDiscovered

from ...domain.models.events import Dnd5eEvent


class Revealable(Protocol):
    """Anything a rule can name: a core entity or an engine join view over one."""

    @property
    def id(self) -> EntityId: ...
    @property
    def name(self) -> str: ...
    @property
    def known(self) -> bool: ...


def reveal(entity: Revealable) -> list[Dnd5eEvent]:
    """Reveal hidden entities before an event names them."""
    return [] if entity.known else [EntityDiscovered(entity_id=entity.id, name=entity.name)]
