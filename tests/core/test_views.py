from core_test_support import LONER3E

from aidm.app.views import JournalView, journal_markdown, played_turns, player_scene
from aidm.engines.loner3e.mechanics import Mechanics, Sheet
from aidm.state.base import PLAYER_ID, Counter, Entity, EntityId, Exit, Kind
from aidm.state.facts import Fact
from aidm.state.history import Exchange, Line
from aidm.state.trace import Applied, Turn
from aidm.state.world import Game, Memory, ScenarioMeta, Thread, WorldState


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
    memories = (
        Memory(owner=None, text="The vault has stood for a century."),
        Memory(owner=EntityId("hidden-actor"), text="The Secret keeps a hidden ledger."),
    )
    held = Game(
        scenario_id="whispering-vault",
        character_id="kael",
        scenario=ScenarioMeta(title="Test", premise="Test"),
        engine=LONER3E,
        world=WorldState(
            entities=list(entities),
            threads=list(threads),
            memories=list(memories),
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


def test_the_journal_holds_no_steering_note_and_no_memory_of_someone_unmet() -> None:
    view = JournalView.of(state())

    assert "Director steering text" not in str(view.model_dump())
    assert "The Secret keeps a hidden ledger." not in view.memories
    assert "The vault has stood for a century." in view.memories
    assert view.threads[0].clock == "1 / 4"


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
    assert "The vault has stood for a century." in markdown
    assert "Director steering text" not in markdown
    assert "The Secret keeps a hidden ledger." not in markdown


def test_a_turn_shows_the_player_only_the_facts_it_may_narrate() -> None:
    """One trace entry per turn, paired from the end, so an unbacked older turn shows nothing."""
    history = (
        Exchange(prompt="Before the trace", lines=(Line(text="You arrive."),)),
        Exchange(prompt="What do I do?", lines=(Line(text="The seal gives."),)),
    )
    turn = Turn(
        prompt="What do I do?",
        narration="The seal gives.",
        facts=(
            Fact(kind="rolled", trace="rolled 4", narrator="the seal cracks"),
            Fact(kind="entity_created", trace="new actor: The Secret"),
        ),
    )
    played = played_turns(history, [Applied(subject_id=PLAYER_ID), turn])

    assert [entry.outcomes for entry in played] == [(), ("the seal cracks",)]
