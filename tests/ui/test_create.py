from support.table import ENGINES_BUILT

from aidm.core.entities import EngineId, Slug
from aidm.ui.create import _drop_stale  # pyright: ignore[reportPrivateUsage]

TWENTYFOURXX = EngineId("twentyfourxx")
ANDROID: dict[Slug, str] = {
    "specialty": "muscle",
    "specialty-choice": "hand-to-hand",
    "weapon": "sword",
    "origin": "android",
    "body": "case",
}


def test_a_free_text_step_keeps_its_answer_which_the_page_keys_by_label() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"increase-1": "Piloting"}

    _drop_stale(engine.creation_steps(picks), picks)

    assert picks["increase-1"] == "Piloting"


def test_a_constrained_step_still_loses_an_answer_it_no_longer_offers() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"body": "not-on-offer"}

    _drop_stale(engine.creation_steps(picks), picks)

    assert "body" not in picks
