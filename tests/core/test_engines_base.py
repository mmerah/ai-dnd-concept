import pytest
from pydantic import ValidationError
from support.loner import initialized

from aidm.core.entities import EntityId
from aidm.core.views import Subject
from aidm.engines.base import Counter, Person, Thing, here_panel, named_unmet
from aidm.engines.loner3e.world import Loner3eGame, Loner3eSheet

KAEL = Loner3eSheet(id=EntityId("kael"), name="Kael", brief="", known=True)


def _state() -> Loner3eGame:
    """A counter card drops the name for the played character alone, so it needs the state."""
    _, state = initialized()
    return state


def test_here_panel_puts_the_player_first_with_icon_ids_on_every_row() -> None:
    player = Subject(id=EntityId("player"), name="Sable", brief="Wary and quick.")
    other = Subject(id=EntityId("kestrel"), name="Kestrel", brief="Runs the dock.")

    panel = here_panel(player, (other,))

    assert panel.title == "Here"
    assert [row.label for row in panel.rows] == ["Sable (you)", "Kestrel"]
    assert panel.rows[0].icon_id == player.id
    assert panel.rows[1].icon_id == other.id


def test_a_thing_with_no_brief_prints_only_its_tag() -> None:
    lantern = Thing(id=EntityId("lantern"), name="Lantern", brief="")

    assert lantern.line() == "- Lantern[lantern]"


def test_a_dead_person_prints_dead_on_the_first_line_of_line() -> None:
    kestrel = Person(id=EntityId("kestrel"), name="Kestrel", brief="Runs the dock.", alive=False)

    assert kestrel.line().splitlines()[0] == "- Kestrel[kestrel] — Runs the dock. (dead)"


def test_counter_rejects_current_outside_its_bounds() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Counter(current=-1, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Counter(current=11, maximum=10)


def test_adjust_clamps_to_the_counters_bounds_and_reports_only_a_real_move() -> None:
    state = _state()
    KAEL.luck.current = 0
    (changed,) = KAEL.luck.change(KAEL, 99, "Luck", "the strain")
    assert (changed.card, KAEL.luck.current) == ("Kael: Luck +6 -> 6/6", 6)
    assert KAEL.luck.change(KAEL, 99, "Luck", "the strain") == []
    assert KAEL.luck.adjust(-2) == -2

    player = state.payload.player
    player.luck.current = 0
    (own,) = player.luck.change(player, 1, "Luck", "the strain")
    assert own.card == "Luck +1 -> 1/6"


def test_named_unmet_finds_multi_word_names_case_folded_and_bare_ids() -> None:
    text = "The Bell Tower looms over the square; a bell rings, and old-tom watches."
    entities = [
        Thing(id=EntityId("bell-tower"), name="Bell Tower", brief=""),
        Thing(id=EntityId("the-bell"), name="Bell", brief=""),
        Thing(id=EntityId("town-square"), name="town square", brief=""),
        Thing(id=EntityId("old-tom"), name="Tom", brief=""),
    ]
    assert named_unmet(text, entities) == ["Bell Tower", "Tom"]
