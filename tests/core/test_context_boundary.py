from core_test_support import ENGINES_BUILT, LONER3E, initialized, with_entity

from aidm.core.entities import EntityId
from aidm.core.views import NarratorView
from aidm.engines.core import AnyEngine
from aidm.engines.loner3e.world import Loner3eGame, LonerCharacter
from aidm.turn.context import ANSWERED_BY_OPTION, render_narrator, render_picture

SECRET = EntityId("hidden-actor")


def _state() -> Loner3eGame:
    """An unmet character and a known one, both here, so both leak paths are open at once."""
    _, state = initialized()
    state = with_entity(
        state,
        LonerCharacter(
            id=SECRET, name="The Secret", brief="Unrevealed canon.", concept="A Watcher"
        ),
    )
    return with_entity(
        state,
        LonerCharacter(id=EntityId("ledger"), name="a ledger", brief="Mara's notes.", known=True),
    )


def _engine() -> AnyEngine:
    return ENGINES_BUILT[LONER3E]


def _master_prompt(held: Loner3eGame, prompt: str, *, resumed: str = "") -> str:
    return render_picture(
        _engine().master_sections(held),
        held,
        _engine().history(held),
        prompt,
        resumed=resumed,
    )


def test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon() -> None:
    held = _state()
    narrator = _engine().narrator_view(held)
    master = _engine().master_sections(held)

    assert set(NarratorView.model_fields) == {
        "place",
        "title",
        "situation",
        "art_prompt",
        "focus",
        "subjects",
        "speakers",
    }
    dumped = str(narrator.model_dump())
    assert "The Secret" not in dumped
    assert held.payload.world.current.secret not in dumped
    assert held.payload.world.current.secret in str(master)


def test_the_master_is_shown_the_hidden_canon_and_the_tags_in_play() -> None:
    held = _state()

    master = _master_prompt(held, "I look around.")

    assert "Kael[player]" in master
    assert "a ledger[ledger]" in master
    assert "The Secret[hidden-actor]" in master
    # Hidden here: the map the player has not found yet.
    assert "the vault map[vault-map]" in master
    assert "concept: A Wary Relic-Hunter" in master
    assert "luck: 6/6" in master


def test_the_narrator_prompt_carries_only_what_the_player_has_met() -> None:
    held = _state()

    prompt = render_narrator(
        _engine().narrator_view(held),
        evidence="- the map was found",
        prompt="What does Mara say?",
    )

    assert "Mara" in prompt
    assert "The Secret" not in prompt
    assert "hidden-actor" not in prompt
    assert held.payload.world.current.secret not in prompt


def test_the_narrator_prompt_carries_only_what_the_player_has_read() -> None:
    held = _state()

    prompt = render_narrator(
        _engine().narrator_view(held),
        evidence="- the map was found",
        prompt="What does Mara say?",
        passages=("Water drips.",),
    )

    assert "Water drips." in prompt


def test_a_chosen_option_is_not_shown_as_the_players_own_words() -> None:
    resumed = "asked: A hit is coming.\nthe player chose: Take the hit\n- the hit lands in full"

    master = _master_prompt(_state(), "Take the hit", resumed=resumed)

    assert master.count("Take the hit") == 1
    assert master.endswith(f"PLAYER ACTION:\n{ANSWERED_BY_OPTION}")
