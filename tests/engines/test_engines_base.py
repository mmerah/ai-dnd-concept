import pytest
from pydantic import ValidationError
from support.game import initialized

from aidm.core.views import PanelRow, Subject
from aidm.engines.base import Gauge, Person, Thing, here_panel, party_panel, party_section
from aidm.engines.loner3e.world import Loner3eCast, Loner3eGame
from aidm.engines.scenes.worldsmith import named_unmet

KAEL = Loner3eCast(id="kael", name="Kael", brief="", known=True)


def _state() -> Loner3eGame:
    """A counter card drops the name for the played character alone, so it needs the state."""
    _, state = initialized()
    return state


def test_here_panel_leaves_out_the_player_and_carries_an_icon_id_per_row() -> None:
    other = Subject(id="kestrel", label="Kestrel", detail="Runs the dock.")

    panel = here_panel((other,))

    assert panel.title == "Also here"
    assert [row.label for row in panel.rows] == ["Kestrel"]
    assert panel.rows[0].icon_id == other.id


def test_party_section_is_empty_for_nobody_and_party_panel_orders_entity_before_sheet() -> None:
    assert party_section(()) == ()
    assert party_panel(()) == ()

    member = Loner3eCast(
        id="mara", name="Mara", brief="Keeps to herself.", known=True, concept="A Watcher"
    )

    (panel,) = party_panel((member,))
    assert panel.title == "Party"
    assert panel.rows[0] == PanelRow(label="Mara", detail="Keeps to herself.", icon_id=member.id)
    assert panel.rows[1] == PanelRow(label="Concept", detail="A Watcher")

    ((title, body),) = party_section((member,))
    assert (title, body) == ("THE PARTY (led by the player)", member.line())


def test_a_thing_with_no_brief_prints_only_its_tag() -> None:
    lantern = Thing(id="lantern", name="Lantern", brief="")

    assert lantern.line() == "- Lantern[lantern]"


def test_a_dead_person_prints_dead_on_the_first_line_of_line() -> None:
    kestrel = Person(id="kestrel", name="Kestrel", brief="Runs the dock.", alive=False)

    assert kestrel.line().splitlines()[0] == "- Kestrel[kestrel] — Runs the dock. (dead)"


def test_a_person_defaults_to_normal_chattiness_and_refuses_an_unknown_one() -> None:
    kestrel = Person(id="kestrel", name="Kestrel", brief="Runs the dock.")
    assert kestrel.chattiness == "normal"

    with pytest.raises(ValidationError):
        Person.model_validate(
            {"id": "kestrel", "name": "Kestrel", "brief": "", "chattiness": "loud"}
        )


def test_counter_rejects_current_outside_its_bounds() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Gauge(current=-1, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Gauge(current=11, maximum=10)


def test_adjust_clamps_to_the_counters_bounds_and_reports_only_a_real_move() -> None:
    state = _state()
    KAEL.luck.current = 0
    (changed,) = KAEL.luck.change(KAEL, 99, "Luck", "the strain")
    assert (changed.card, KAEL.luck.current) == ("Kael: Luck +6 → 6/6", 6)
    assert KAEL.luck.change(KAEL, 99, "Luck", "the strain") == []
    assert KAEL.luck.adjust(-2) == -2

    player = state.payload.player
    player.luck.current = 0
    (own,) = player.luck.change(player, 1, "Luck", "the strain")
    assert own.card == "Luck +1 → 1/6"


def test_named_unmet_finds_multi_word_names_case_folded_and_bare_ids() -> None:
    text = "The Bell Tower looms over the square; a bell rings, and old-tom watches."
    entities = [
        Thing(id="bell-tower", name="Bell Tower", brief=""),
        Thing(id="the-bell", name="Bell", brief=""),
        Thing(id="town-square", name="town square", brief=""),
        Thing(id="old-tom", name="Tom", brief=""),
    ]
    assert named_unmet(text, entities) == ["Bell Tower", "Tom"]
