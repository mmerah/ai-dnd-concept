from aidm.engines.core import mechanics_of
from aidm.engines.twentyfourxx.engine import complete_chapter
from aidm.engines.twentyfourxx.rules import ItemSheet, Sheet, TwentyfourxxState
from aidm.state.entities import EntityId
from aidm.state.model import Game


def sheets(state: Game) -> dict[EntityId, Sheet]:
    """The blob's sheets: a copy, so changing state needs `rules(world, ...)`."""
    return mechanics_of(state.world, TwentyfourxxState).sheets


def items(state: Game) -> dict[EntityId, ItemSheet]:
    return mechanics_of(state.world, TwentyfourxxState).items


def at_boundary(state: Game) -> Game:
    """One chapter recorded — the job is done — for everyone who worked it."""
    draft = state.draft()
    _ = complete_chapter(draft)
    return draft.committed()
