import pytest

from aidm.core.creation import MANY, CreationStep, check_picks, picked_many
from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption

STEP = CreationStep(
    id="supplements",
    label="Table sets beyond the SRD",
    options=(DecisionOption(id="one", label="One"), DecisionOption(id="two", label="Two")),
    multiple=True,
)


def test_a_multiple_step_takes_no_answer_or_several_offered_ones() -> None:
    check_picks((STEP,), {})
    check_picks((STEP,), {"supplements": ""})
    check_picks((STEP,), {"supplements": MANY.join(("one", "two"))})
    assert picked_many({"supplements": MANY.join(("one", "two"))}, "supplements") == ("one", "two")


def test_a_multiple_step_refuses_a_part_it_does_not_offer() -> None:
    with pytest.raises(Refusal, match="'supplements' offers no 'three'"):
        check_picks((STEP,), {"supplements": MANY.join(("one", "three"))})


def test_an_allows_text_step_accepts_a_typed_answer_but_a_closed_step_still_refuses_one() -> None:
    open_step = CreationStep(
        id="increase-1",
        label="Skill increase",
        options=(DecisionOption(id="climbing", label="Climbing"),),
        allows_text=True,
    )
    check_picks((open_step, STEP), {"increase-1": "Sabotage", "supplements": ""})
    with pytest.raises(Refusal, match="'supplements' offers no 'three'"):
        check_picks((open_step, STEP), {"increase-1": "climbing", "supplements": "three"})
