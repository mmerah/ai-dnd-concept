from support.loner import initialized, with_entity
from support.table import ENGINES_BUILT, LONER3E

from aidm.core.entities import EntityId
from aidm.core.play import Exchange, SceneRecord, SpokenLine
from aidm.core.views import NarratorView
from aidm.engines.loner3e.world import Loner3eGame, Loner3eSheet
from aidm.engines.seam import AnyEngine
from aidm.turn.context import render_master, render_narrator
from aidm.turn.run import ANSWERED_BY_OPTION

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


def _master_prompt(state: Loner3eGame, prompt: str, *, notes: tuple[str, ...] = ()) -> str:
    return render_master(
        _engine().instructions,
        _engine().master_sections(state),
        state,
        _engine().scenes(state),
        prompt,
        played=len(_engine().history(state)),
        notes=notes,
    )


def test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon() -> None:
    state = _state()
    narrator = _engine().narrator_view(state)
    master = _engine().master_sections(state)

    assert set(NarratorView.model_fields) == {
        "place",
        "title",
        "situation",
        "focus",
        "subjects",
        "speakers",
        "sheet",
    }
    dumped = str(narrator.model_dump())
    assert "The Secret" not in dumped
    assert UNREVEALED not in dumped
    assert UNREVEALED in str(master)


def test_the_master_is_shown_the_hidden_canon_and_the_tags_in_play() -> None:
    state = _state()

    master = _master_prompt(state, "I look around.")

    assert "Kael[player]" in master
    assert "a ledger[ledger]" in master
    assert "The Secret[hidden-actor]" in master
    # Hidden here: the map the player has not found yet.
    assert "the vault map[vault-map]" in master
    assert "concept: A Wary Relic-Hunter" in master
    assert "luck: 6/6" in master


def test_the_narrator_prompt_carries_only_what_the_player_has_met() -> None:
    state = _state()

    prompt = render_narrator(
        _engine().narrator_view(state),
        evidence="- the map was found",
        prompt="What does Mara say?",
        scenes=(),
    )

    assert "Mara" in prompt
    assert "The Secret" not in prompt
    assert "hidden-actor" not in prompt
    assert UNREVEALED not in prompt


def test_the_narrator_prompt_carries_the_players_own_sheet() -> None:
    state = _state()

    prompt = render_narrator(
        _engine().narrator_view(state), evidence="- (nothing changed)", prompt="I wait.", scenes=()
    )

    assert "THE PLAYER'S SHEET:\n- Concept: A Wary Relic-Hunter" in prompt
    assert "- Gear: Pry Bar, Chalk and Wire, A Guttering Lantern" in prompt


def test_the_master_prompt_ends_on_the_action_with_no_empty_waiting_section() -> None:
    master = _master_prompt(_state(), "I look around.")

    assert "WAITING ON THE PLAYER" not in master
    assert master.endswith("PLAYER ACTION:\nI look around.")


def test_the_narrator_prompt_carries_only_what_the_player_has_read() -> None:
    state = _state()

    prompt = render_narrator(
        _engine().narrator_view(state),
        evidence="- the map was found",
        prompt="What does Mara say?",
        scenes=(
            SceneRecord(
                title="t",
                focus="q",
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
