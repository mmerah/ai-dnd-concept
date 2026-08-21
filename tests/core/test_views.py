from core_test_support import LONER3E

from aidm.app.views import journal_markdown
from aidm.engines.loner3e.engine import Mechanics, Sheet
from aidm.state.model import (
    Counter,
    Entity,
    EntityId,
    Exchange,
    Exit,
    Game,
    Kind,
    Line,
    ScenarioMeta,
    Thread,
    WorldState,
)
from aidm.turn.context import player_scene


def _entity(entity_id: str, kind: Kind, name: str, brief: str, **fields: object) -> Entity:
    return Entity.model_validate(
        {"id": entity_id, "kind": kind, "name": name, "brief": brief} | fields
    )


def state() -> Game:
    entities = (
        _entity(
            "study",
            "location",
            "Study",
            "A small room.",
            known=True,
            exits=[Exit(to=EntityId("crypt"))],
        ),
        _entity("player", "actor", "Kael", "A hunter.", known=True, parent_id="study"),
        _entity("mara", "actor", "Mara", "A known scribe.", known=True, parent_id="study"),
        _entity("hidden-actor", "actor", "The Secret", "Unrevealed canon.", parent_id="study"),
        _entity("crypt", "location", "Crypt", "A sealed vault.", known=False),
    )
    threads = (
        Thread(
            id="the-vault",
            title="The Vault",
            note="Director steering text",
            clock=Counter(current=1, maximum=4),
        ),
    )
    held = Game(
        scenario_id="whispering-vault",
        character_id="kael",
        scenario=ScenarioMeta(title="Test", premise="Test"),
        engine=LONER3E,
        world=WorldState(
            entities=list(entities),
            threads=list(threads),
        ),
        mechanics=Mechanics(
            sheets={entity.id: Sheet() for entity in entities if entity.kind == "actor"}
        ),
    )
    return held.committed()


def test_the_player_scene_holds_no_unrevealed_entity_or_unknown_exit() -> None:
    scene = player_scene(state())

    assert "The Secret" not in str(scene.model_dump())
    assert "crypt" not in {exit.to for exit in scene.exits}
    assert EntityId("mara") in {entity.id for entity in scene.here}


def test_the_journal_export_writes_the_chronicle_and_leaks_no_steering_note() -> None:
    held = state().draft()
    held.history = (
        Exchange(
            prompt="What do I do?",
            lines=(
                Line(text="You step into the study."),
                Line(speaker_id=EntityId("mara"), text="Shut the door behind you."),
            ),
        ),
    )

    markdown = journal_markdown(held.committed())

    assert "# Test" in markdown
    assert "What do I do?" in markdown
    assert "You step into the study." in markdown
    assert "**Mara:** Shut the door behind you." in markdown
    assert "**The Vault**" in markdown
    assert "[1 / 4]" in markdown
    assert "Director steering text" not in markdown
