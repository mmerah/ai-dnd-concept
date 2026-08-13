import json
from pathlib import Path

import pytest
from core_test_support import LONER3E, initialized, updated
from pydantic import ValidationError

from aidm.content.store import ENCODING, FileSaves, FileTraces, load_character, load_scenario
from aidm.state.facts import CORE, Fact, narrator_evidence
from aidm.state.turn import Advance, StepTrace, Turn


def test_save_and_trace_round_trip(tmp_path: Path) -> None:
    _, state = initialized()
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)
    assert saves.load("missing") is None
    assert saves.shell("missing") is None

    saves.save("current", state)
    assert saves.load("current") == state
    assert saves.slugs() == ("current",)

    turn = Turn(
        prompt="I listen.",
        narration="The abbey settles around you.",
        steps=(
            StepTrace(
                name="director",
                prompt="exact director prompt",
                output={"intent": "Listen.", "tone": "quiet"},
            ),
        ),
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


def test_shell_reads_a_save_whose_world_is_garbage(tmp_path: Path) -> None:
    _, state = initialized()
    saves = FileSaves(tmp_path)
    body = json.loads(state.model_dump_json())
    body["world"] = {"entities": {"player": "garbage"}}
    (tmp_path / "broken.json").write_text(json.dumps(body), encoding=ENCODING)

    shell = saves.shell("broken")

    assert shell is not None
    assert (shell.engine, shell.scenario_id, shell.turn) == (LONER3E, "whispering-vault", 0)
    with pytest.raises(ValidationError):
        saves.load("broken")


def test_a_trace_round_trips_its_turn_and_advance_entries(tmp_path: Path) -> None:
    """A Turn and an Advance, each carrying real facts, survive an append and a reload unchanged."""
    traces = FileTraces(tmp_path)
    facts = (
        Fact(source=CORE, kind="dice_rolled", trace="a falling stone: 1d6 [4] -> 4"),
        Fact(source=CORE, kind="counter_changed", trace="Kael luck -1 -> 5/6", narrator="hurt"),
    )
    turn = Turn(
        prompt="I brace.",
        facts=facts,
        narration="Dust falls.",
        steps=(
            StepTrace(
                name="director",
                output={"intent": "Kael endures a falling stone.", "tone": "dangerous"},
            ),
            StepTrace(name="resolve", output=narrator_evidence(facts)),
        ),
    )
    advance = Advance(facts=facts)

    traces.append("poc", turn)
    traces.append("poc", advance)
    reloaded = traces.load("poc")

    assert reloaded == (turn, advance)
    director_output = reloaded[0].steps[0].output if isinstance(reloaded[0], Turn) else None
    assert (
        isinstance(director_output, dict)
        and director_output["intent"] == "Kael endures a falling stone."
    )
    assert isinstance(reloaded[1], Advance)


def test_a_save_or_trace_from_another_build_is_refused(tmp_path: Path) -> None:
    """A file written before `save_version` existed reads as version 0, not as a schema error."""
    _, state = initialized()
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)
    stale = updated(state, save_version=state.save_version - 1)

    saves.save("stale", stale)
    with pytest.raises(ValueError, match="save is version"):
        saves.load("stale")
    with pytest.raises(ValueError, match="save is version"):
        saves.shell("stale")

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
            narration="The abbey settles around you.",
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
        load_scenario(tmp_path, "../escape", LONER3E)
    with pytest.raises(ValueError, match="invalid content id"):
        load_character(tmp_path, "kael/../..", LONER3E)
