from core_test_support import ENGINES_BUILT, LONER3E, initialized, with_entity

from aidm.core.entities import EntityId
from aidm.core.play import Exchange, SceneRecord, SpokenLine
from aidm.core.views import NarratorView
from aidm.engines.loner3e.world import Loner3eGame, Loner3eSheet
from aidm.engines.seam import AnyEngine
from aidm.turn.context import ANSWERED_BY_OPTION, render_master, render_narrator

SECRET = EntityId("hidden-actor")
UNREVEALED = "Unrevealed canon."


def _state() -> Loner3eGame:
    """An unmet character and a known one, both here, so both leak paths are open at once."""
    _, state = initialized()
    state = with_entity(
        state,
        Loner3eSheet(id=SECRET, name="The Secret", brief=UNREVEALED, concept="A Watcher"),
    )
    return with_entity(
        state,
        Loner3eSheet(id=EntityId("ledger"), name="a ledger", brief="Mara's notes.", known=True),
    )


def _engine() -> AnyEngine:
    return ENGINES_BUILT[LONER3E]


def _master_prompt(held: Loner3eGame, prompt: str, *, notes: tuple[str, ...] = ()) -> str:
    return render_master(
        _engine().instructions,
        _engine().master_sections(held),
        held,
        _engine().scenes(held),
        prompt,
        notes=notes,
    )


def test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon() -> None:
    held = _state()
    narrator = _engine().narrator_view(held)
    master = _engine().master_sections(held)

    assert set(NarratorView.model_fields) == {
        "place",
        "title",
        "situation",
        "focus",
        "subjects",
        "speakers",
    }
    dumped = str(narrator.model_dump())
    assert "The Secret" not in dumped
    assert UNREVEALED not in dumped
    assert UNREVEALED in str(master)


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
        scenes=(),
    )

    assert "Mara" in prompt
    assert "The Secret" not in prompt
    assert "hidden-actor" not in prompt
    assert UNREVEALED not in prompt


def test_the_narrator_prompt_carries_only_what_the_player_has_read() -> None:
    held = _state()

    prompt = render_narrator(
        _engine().narrator_view(held),
        evidence="- the map was found",
        prompt="What does Mara say?",
        scenes=(
            SceneRecord(
                title="t",
                question="q",
                exchanges=(Exchange(prompt="p", lines=(SpokenLine(text="Water drips."),)),),
            ),
        ),
    )

    assert "Water drips." in prompt


def test_a_chosen_option_is_not_shown_as_the_players_own_words() -> None:
    note = (
        'The rules paused play to ask the player: "A hit is coming." They chose: Take the hit. '
        "Already resolved:\n- the hit lands in full"
    )

    master = _master_prompt(_state(), ANSWERED_BY_OPTION, notes=(note,))

    assert master.count("Take the hit") == 1
    assert master.endswith(f"PLAYER ACTION:\n{ANSWERED_BY_OPTION}")
