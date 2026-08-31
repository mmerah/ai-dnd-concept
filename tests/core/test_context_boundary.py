from core_test_support import ENGINES_BUILT, LONER3E, initialized, with_entity

from aidm.engines.core import Engine
from aidm.engines.loner3e.state import ActorSheet, LonerSheet
from aidm.kernel.views import NarratorView
from aidm.kits.scenes.state import Entity
from aidm.state.entities import EntityId
from aidm.state.model import Game
from aidm.turn.context import ANSWERED_BY_OPTION, render_narrator, render_picture

SECRET = EntityId("hidden-actor")


def _state() -> Game:
    """An unmet actor in the scene, holding an item, so both leak paths are open at once."""
    _, state = initialized()
    state = with_entity(
        state,
        Entity[LonerSheet](
            id=SECRET,
            kind="actor",
            name="The Secret",
            brief="Unrevealed canon.",
            sheet=ActorSheet(concept="A Watcher"),
        ),
    )
    return with_entity(
        state,
        Entity[LonerSheet](
            id=EntityId("ledger"),
            kind="item",
            name="a ledger",
            brief="Mara's notes.",
            known=True,
            carried_by=SECRET,
        ),
    )


def _engine() -> Engine:
    return ENGINES_BUILT[LONER3E]


def _master_prompt(held: Game, prompt: str, *, resumed: str = "") -> str:
    return render_picture(
        _engine().views(held).master.sections,
        held,
        prompt,
        resumed=resumed,
    )


def test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon() -> None:
    held = _state()
    views = _engine().views(held)

    assert set(NarratorView.model_fields) == {
        "place",
        "title",
        "situation",
        "art_prompt",
        "question",
        "subjects",
        "speakers",
    }
    dumped = str(views.narrator.model_dump())
    assert "The Secret" not in dumped
    assert held.world.current.secret not in dumped
    assert held.world.current.secret in str(views.master.sections)


def test_a_carried_item_never_names_the_holder_the_player_has_not_met() -> None:
    held = _state()

    assert "carried by the npc The Secret[hidden-actor]" in _master_prompt(held, "I look around.")
    assert "The Secret" not in str(_engine().views(held).narrator.model_dump())


def test_the_master_is_shown_the_hidden_canon_and_the_tags_in_play() -> None:
    held = _state()

    master = _master_prompt(held, "I look around.")

    assert "Kael[player]" in master
    assert "a ledger[ledger] (item)" in master
    assert "The Secret[hidden-actor]" in master
    # Hidden here: the map the player has not found yet.
    assert "the vault map[vault-map]" in master
    assert "concept: A Wary Relic-Hunter" in master
    assert "luck: 6/6" in master


def test_the_narrator_prompt_carries_only_what_the_player_has_met() -> None:
    held = _state()

    prompt = render_narrator(
        _engine().views(held).narrator,
        evidence="- the map was found",
        prompt="What does Mara say?",
    )

    assert "Mara" in prompt
    assert "The Secret" not in prompt
    assert "hidden-actor" not in prompt
    assert held.world.current.secret not in prompt


def test_the_narrator_prompt_carries_only_what_the_player_has_read() -> None:
    held = _state()

    prompt = render_narrator(
        _engine().views(held).narrator,
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
