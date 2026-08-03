import json
from pathlib import Path
from random import Random

import pytest
from core_test_support import STORY, initialized, updated
from fivee_test_support import initial_5e_game

from aidm.engine import narrator_evidence
from aidm.engines.dnd5e.direction import Damage, Dnd5eDirection, LevelUp
from aidm.engines.dnd5e.direction import dump_direction as dump_5e
from aidm.engines.story.direction import StoryDirection
from aidm.engines.story.direction import dump_direction as dump_story
from aidm.growth import Growth
from aidm.store import ENCODING, FileSaves, FileTraces, load_character, load_scenario
from aidm.turn import Advance, Turn


def test_save_and_trace_round_trip(tmp_path: Path) -> None:
    _, state = initialized()
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)
    assert saves.load("missing") is None

    saves.save("current", state)
    assert saves.load("current") == state
    assert saves.slugs() == ("current",)

    turn = Turn(
        prompt="I listen.",
        direction=dump_story(StoryDirection(intent="Listen.", tone="quiet")),
        narration="The abbey settles around you.",
        narrator_evidence="- learned of the vault",
        growth=Growth(),
        prompts={"director": "exact director prompt"},
    )
    traces.append("current", turn)
    traces.append("current", updated(turn, prompt="I knock."))
    loaded = [held for held in traces.load("current") if isinstance(held, Turn)]
    assert [held.prompt for held in loaded] == [
        "I listen.",
        "I knock.",
    ]

    saves.discard("current")
    traces.discard("current")
    assert saves.load("current") is None
    assert traces.load("current") == ()


def test_a_trace_entry_names_the_engine_that_wrote_it(tmp_path: Path) -> None:
    """A fact and a direction are flat on disk, so the source tag is all a reload has to tell it
    which engine wrote the line — and the mechanics blob has to survive the round trip untouched."""
    engine, state = initial_5e_game()
    traces = FileTraces(tmp_path)
    proposal = Dnd5eDirection(
        intent="Kael endures a falling stone.",
        tone="dangerous",
        mechanics=[Damage(amount=2), LevelUp()],
    )
    transition = engine.resolve(dump_5e(proposal), state, Random(1))
    turn = Turn(
        prompt="I brace.",
        direction=dump_5e(proposal),
        facts=transition.facts,
        narration="Dust falls.",
        narrator_evidence=narrator_evidence(transition.facts),
        growth=Growth(),
    )
    advance = Advance(facts=transition.facts)

    traces.append("5e", turn)
    traces.append("5e", advance)
    reloaded = traces.load("5e")

    assert reloaded == (turn, advance)
    assert isinstance(reloaded[0], Turn) and reloaded[0].direction.engine == "dnd5e"
    assert isinstance(reloaded[1], Advance)
    assert {fact.source for fact in reloaded[1].facts} == {"dnd5e"}


def test_a_save_or_trace_from_another_build_is_refused(tmp_path: Path) -> None:
    """A file written before `save_version` existed reads as version 0, not as a schema error."""
    _, state = initialized()
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)
    stale = updated(state, save_version=state.save_version - 1)

    saves.save("stale", stale)
    with pytest.raises(ValueError, match="save is version"):
        saves.load("stale")

    saves.save("ancient", state)
    body = json.loads((tmp_path / "ancient.json").read_text(encoding=ENCODING))
    del body["save_version"]
    (tmp_path / "ancient.json").write_text(json.dumps(body), encoding=ENCODING)
    with pytest.raises(ValueError, match="save is version 0"):
        saves.load("ancient")

    traces.append(
        "stale",
        Turn(
            prompt="I listen.",
            direction=dump_story(StoryDirection(intent="Listen.", tone="quiet")),
            narration="The abbey settles around you.",
            narrator_evidence="- nothing changed",
            growth=Growth(),
            save_version=stale.save_version,
        ),
    )
    with pytest.raises(ValueError, match="trace is version"):
        traces.load("stale")


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        saves.load(slug)
    with pytest.raises(ValueError, match="invalid storage slug"):
        traces.load(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    """A game route supplies these ids, and each one names a directory."""
    with pytest.raises(ValueError, match="invalid content id"):
        load_scenario(tmp_path, "../escape", STORY)
    with pytest.raises(ValueError, match="invalid content id"):
        load_character(tmp_path, "kael/../..", STORY)
