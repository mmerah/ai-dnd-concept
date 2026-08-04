import json
from pathlib import Path
from random import Random

import pytest
from core_test_support import STORY, initialized, tool_context, turn_context, updated
from fivee_test_support import initial_5e_game, ruleset

from aidm.core.engine import narrator_evidence
from aidm.core.store import ENCODING, FileSaves, FileTraces, load_character, load_scenario
from aidm.core.tools import DirectorNotes
from aidm.core.turn import Advance, Growth, Turn
from aidm.engines.dnd5e.tools import Dnd5eTools


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
        notes=DirectorNotes(intent="Listen.", tone="quiet"),
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
    """A fact and a direction are flat on disk, so the source tag alone is what tells a reload
    which engine wrote the line — there is no mechanics blob any more."""
    engine, state = initial_5e_game()
    traces = FileTraces(tmp_path)
    context = turn_context(engine, state, Random(1))
    run = tool_context(context)
    tools = Dnd5eTools(ruleset())
    _ = tools.damage(run, amount=2)
    _ = tools.level_up(run)
    facts = tuple(context.facts)
    turn = Turn(
        prompt="I brace.",
        notes=DirectorNotes(intent="Kael endures a falling stone.", tone="dangerous"),
        facts=facts,
        narration="Dust falls.",
        narrator_evidence=narrator_evidence(facts),
        growth=Growth(),
    )
    advance = Advance(facts=facts)

    traces.append("5e", turn)
    traces.append("5e", advance)
    reloaded = traces.load("5e")

    assert reloaded == (turn, advance)
    assert (
        isinstance(reloaded[0], Turn)
        and reloaded[0].notes.intent == "Kael endures a falling stone."
    )
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
            notes=DirectorNotes(intent="Listen.", tone="quiet"),
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
