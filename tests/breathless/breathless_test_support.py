from aidm.engines.breathless.rules import BreathlessState, ItemSheet, Sheet
from aidm.engines.core import mechanics_of
from aidm.state.entities import EntityId
from aidm.state.model import Game


def sheet(state: Game, entity_id: EntityId) -> Sheet:
    """One actor sheet out of the blob: a copy, so changing state needs `rules()`."""
    return mechanics_of(state.world, BreathlessState).sheets[entity_id]


def item_sheet(state: Game, entity_id: EntityId) -> ItemSheet:
    """The die an item is, out of the blob; a copy, like `sheet`."""
    return mechanics_of(state.world, BreathlessState).items[entity_id]
