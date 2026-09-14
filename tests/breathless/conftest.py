import pytest
from support.breathless import small_world

from aidm.engines.breathless.world import BreathlessGame, BreathlessWorld


@pytest.fixture
def draft() -> BreathlessGame:
    return small_world().draft()


@pytest.fixture
def world(draft: BreathlessGame) -> BreathlessWorld:
    return draft.payload
