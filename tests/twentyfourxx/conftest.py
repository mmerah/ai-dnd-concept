import pytest
from support.twentyfourxx import small_world

from aidm.engines.twentyfourxx.world import TwentyfourxxGame, TwentyfourxxWorld


@pytest.fixture
def draft() -> TwentyfourxxGame:
    return small_world().draft()


@pytest.fixture
def world(draft: TwentyfourxxGame) -> TwentyfourxxWorld:
    return draft.world
