from story_test_support import grown, story_game

from aidm.core.sheet import ChangeCounter, SetNumber, SheetDelta
from aidm.engines.story.engine import GROWTH_REQUIRED

SPEND = ChangeCounter(why="the marks are spent", key="growth", delta=-GROWTH_REQUIRED)


def test_growth_opens_an_offer_and_storys_own_caps_refuse_what_breaks_them() -> None:
    engine, state = story_game()
    assert engine.proposal.offered(state) is None

    ready = grown(state)
    offer = engine.proposal.offered(ready)
    assert offer is not None

    legal = SheetDelta(changes=(SetNumber(why="patience earned", key="clever", value=2), SPEND))
    over_cap = SheetDelta(changes=(SetNumber(why="greed", key="bold", value=4), SPEND))
    unspent = SheetDelta(changes=(SetNumber(why="free lunch", key="clever", value=2),))

    assert engine.proposal.check(ready, offer, legal) is None
    assert engine.proposal.check(ready, offer, over_cap) == "an approach cannot pass +3: ['bold']"
    assert "must be spent" in str(engine.proposal.check(ready, offer, unspent))
