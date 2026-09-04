from support.loner import initialized, with_entity

from aidm.core.entities import EntityId
from aidm.core.facts import Fact
from aidm.core.play import ChapterRecord, Exchange, SceneRecord, SpokenLine
from aidm.core.views import TAIL_EXCHANGES, render_history, render_whole, told_narration
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import Loner3eSheet

SECRET = Loner3eSheet(
    id=EntityId("hidden-actor"),
    name="The Secret",
    brief="Unrevealed canon.",
    concept="A Watcher",
)

OBJECT = Loner3eSheet(
    id=EntityId("a-locked-chest"),
    name="A Locked Chest",
    brief="Iron-bound, and shut fast.",
    known=True,
)


def test_the_narrator_view_names_nobody_in_the_scene_the_player_has_not_met() -> None:
    engine, state = initialized()

    shown = str(engine.narrator_view(with_entity(state, SECRET)).model_dump())

    assert "The Secret" not in shown
    # The vault map is hidden here, and Mara is standing in the room.
    assert "vault map" not in shown
    assert "Mara" in shown


def test_everyone_known_and_present_may_speak() -> None:
    """SRD "Everything is a Character": a thing present and known is a speaker too."""
    engine, state = initialized()

    view = engine.narrator_view(with_entity(state, OBJECT))

    assert OBJECT.id in {speaker.id for speaker in view.speakers}


def test_the_player_view_panels_carry_icon_ids_for_who_is_here() -> None:
    engine, state = initialized()

    view = engine.player_view(with_entity(state, SECRET))

    assert tuple(panel.title for panel in view.panels) == (
        "Character",
        "This scene",
        "Here",
        "Trail",
    )
    here = next(panel for panel in view.panels if panel.title == "Here")
    icon_ids = {row.icon_id for row in here.rows}
    assert PLAYER_ID in icon_ids
    assert EntityId("mara") in icon_ids
    assert all(row.label != "The Secret" for panel in view.panels for row in panel.rows)


def _told(prompt: str) -> Exchange:
    return Exchange(prompt=prompt, lines=(SpokenLine(text=f"{prompt} happens."),))


def test_render_history_prints_an_older_scenes_recap_and_not_its_exchanges() -> None:
    older = SceneRecord(
        title="The Drowned Hall",
        question="What lies beneath the water?",
        recap="You found the drowned hall and left it behind.",
        exchanges=(_told("dropped"),),
    )
    scenes = [older, SceneRecord(title="A1", question="q1"), SceneRecord(title="A2", question="q2")]

    history = render_history(scenes)

    assert "what happened: You found the drowned hall and left it behind." in history
    assert "dropped" not in history


def test_render_history_prints_the_last_two_scenes_whole() -> None:
    recent_a = SceneRecord(title="A1", question="q1", exchanges=(_told("p1"), _told("p2")))
    recent_b = SceneRecord(title="A2", question="q2", exchanges=(_told("p3"),))
    scenes = [SceneRecord(title="Hub", question="q0"), recent_a, recent_b]

    history = render_history(scenes)

    assert "> p1\np1 happens." in history
    assert "> p2\np2 happens." in history
    assert "> p3\np3 happens." in history


def test_render_history_shows_an_older_scenes_last_tail_exchanges_only() -> None:
    prompts = [f"p{number}" for number in range(TAIL_EXCHANGES + 2)]
    older = SceneRecord(title="Hub", question="q0", exchanges=tuple(_told(p) for p in prompts))
    scenes = [older, SceneRecord(title="A1", question="q1"), SceneRecord(title="A2", question="q2")]

    history = render_history(scenes)

    for kept in prompts[-TAIL_EXCHANGES:]:
        assert f"> {kept}" in history
    for dropped in prompts[:-TAIL_EXCHANGES]:
        assert f"> {dropped}\n" not in history


def test_render_history_prints_a_chapters_summary_and_scene_titles_only() -> None:
    swallowed = SceneRecord(title="A0", question="q0", exchanges=(_told("swallowed"),))
    chapter = ChapterRecord(
        title="The First Job",
        verdict="done",
        summary="The player found the ledger and burned it.",
        scenes=(swallowed.title, "The Cloister Walk"),
    )
    recent_a = SceneRecord(title="A1", question="q1", exchanges=(_told("p1"),))
    recent_b = SceneRecord(title="A2", question="q2", exchanges=(_told("p2"),))
    records = [chapter, recent_a, recent_b]

    history = render_history(records)

    assert "CLOSED: The First Job (done)" in history
    assert "what happened: The player found the ledger and burned it." in history
    assert "scenes: A0; The Cloister Walk" in history
    assert "> swallowed" not in history
    assert told_narration(records) == ("p1 happens.", "p2 happens.")


def test_render_whole_prints_the_trace_of_an_untold_fact() -> None:
    hidden = Fact(kind="region_added", trace="a hidden region opens beyond the vault", told=False)
    scene = SceneRecord(
        title="The Vault",
        question="q",
        exchanges=(
            Exchange(prompt="p1", lines=(SpokenLine(text="p1 happens."),), facts=(hidden,)),
        ),
    )

    whole = render_whole([scene])

    assert "SCENE: The Vault" in whole
    assert "- a hidden region opens beyond the vault" in whole
    assert "p1 happens." in whole


def test_told_narration_holds_narration_with_no_prompt_or_recap() -> None:
    older = SceneRecord(
        title="Hub", question="q0", recap="What happened before.", exchanges=(_told("dropped"),)
    )
    recent_a = SceneRecord(title="A1", question="q1", exchanges=(_told("p1"),))
    recent_b = SceneRecord(title="A2", question="q2", exchanges=(_told("p2"),))
    scenes = [older, recent_a, recent_b]

    narrated = told_narration(scenes)

    assert narrated == ("p1 happens.", "p2 happens.")
    assert not any("dropped" in text for text in narrated)
    assert not any("What happened before." in text for text in narrated)
