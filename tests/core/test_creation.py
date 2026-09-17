import pytest

from aidm.core.creation import ANSWER_MAX, CreationStep, check_picks
from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption

STEP = CreationStep(
    id="supplements",
    label="Table sets beyond the SRD",
    options=(DecisionOption(id="one", label="One"), DecisionOption(id="two", label="Two")),
)


def test_a_step_takes_exactly_one_offered_answer() -> None:
    check_picks((STEP,), {"supplements": "one"})
    with pytest.raises(Refusal, match="'supplements' is unanswered"):
        check_picks((STEP,), {"supplements": ""})
    with pytest.raises(Refusal, match="'supplements' offers no 'three'"):
        check_picks((STEP,), {"supplements": "three"})


def test_the_answer_cap_applies_to_a_written_answer() -> None:
    written = CreationStep(id="notes", label="Notes")

    check_picks((written,), {"notes": "x" * ANSWER_MAX})
    with pytest.raises(Refusal, match=f"'notes' takes at most {ANSWER_MAX} characters"):
        check_picks((written,), {"notes": "x" * (ANSWER_MAX + 1)})


def test_an_allows_text_step_accepts_a_typed_answer_but_a_closed_step_still_refuses_one() -> None:
    open_step = CreationStep(
        id="increase-1",
        label="Skill increase",
        options=(DecisionOption(id="climbing", label="Climbing"),),
        allows_text=True,
    )
    check_picks((open_step, STEP), {"increase-1": "Sabotage", "supplements": "one"})
    with pytest.raises(Refusal, match="'supplements' offers no 'three'"):
        check_picks((open_step, STEP), {"increase-1": "climbing", "supplements": "three"})
