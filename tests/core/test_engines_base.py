from aidm.core.entities import EntityId
from aidm.core.views import Subject
from aidm.engines.base import Person, Thing, here_panel


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
