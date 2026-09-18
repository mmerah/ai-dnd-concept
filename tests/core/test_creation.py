import pytest
from support.table import ENGINES_BUILT, TWENTYFOURXX

from aidm.core.creation import ANSWER_MAX, CreationStep, check_picks, drop_stale
from aidm.core.entities import Refusal, Slug
from aidm.core.play import DecisionOption

ANDROID: dict[Slug, str] = {
    "specialty": "muscle",
    "specialty-choice": "hand-to-hand",
    "weapon": "sword",
    "origin": "android",
    "body": "case",
}
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


def test_a_free_text_step_keeps_its_answer_which_the_page_keys_by_label() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"increase-1": "Piloting"}

    drop_stale(engine.creation_steps(("srd",), picks), picks)

    assert picks["increase-1"] == "Piloting"


def test_a_constrained_step_still_loses_an_answer_it_no_longer_offers() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"body": "not-on-offer"}

    drop_stale(engine.creation_steps(("srd",), picks), picks)

    assert "body" not in picks
