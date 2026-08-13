import json
from pathlib import Path

import pytest
from core_test_support import LONER3E, initialized, updated
from pydantic import ValidationError

from aidm.content.store import ENCODING, FileStore, load_character, load_scenario
from aidm.state.facts import CORE, Fact, narrator_evidence
from aidm.state.turn import Advance, StepTrace, Turn


def test_save_and_trace_round_trip(tmp_path: Path) -> None:
    _, state = initialized()
    store = FileStore(tmp_path)
    assert store.load("missing") is None
    assert store.shell("missing") is None

    store.save("current", state)
    assert store.load("current") == state
    assert store.slugs() == ("current",)

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
    store.append_trace("current", turn)
    store.append_trace("current", updated(turn, prompt="I knock."))
    loaded = [held for held in store.load_trace("current") if isinstance(held, Turn)]
    assert [held.prompt for held in loaded] == [
        "I listen.",
        "I knock.",
    ]

    store.discard("current")
    assert store.load("current") is None
    assert store.load_trace("current") == ()


def test_shell_reads_a_save_whose_world_is_garbage(tmp_path: Path) -> None:
    _, state = initialized()
    store = FileStore(tmp_path)
    body = json.loads(state.model_dump_json())
    body["world"] = {"entities": {"player": "garbage"}}
    (tmp_path / "broken.json").write_text(json.dumps(body), encoding=ENCODING)

    shell = store.shell("broken")

    assert shell is not None
    assert (shell.engine, shell.scenario_id, shell.turn) == (LONER3E, "whispering-vault", 0)
    with pytest.raises(ValidationError):
        store.load("broken")


def test_a_trace_round_trips_its_turn_and_advance_entries(tmp_path: Path) -> None:
    """A Turn and an Advance, each carrying real facts, survive an append and a reload unchanged."""
    store = FileStore(tmp_path)
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

    store.append_trace("poc", turn)
    store.append_trace("poc", advance)
    reloaded = store.load_trace("poc")

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
    store = FileStore(tmp_path)
    stale = updated(state, save_version=state.save_version - 1)

    store.save("stale", stale)
    with pytest.raises(ValueError, match="save is version"):
        store.load("stale")
    with pytest.raises(ValueError, match="save is version"):
        store.shell("stale")

    store.save("ancient", state)
    body = json.loads((tmp_path / "ancient.json").read_text(encoding=ENCODING))
    del body["save_version"]
    (tmp_path / "ancient.json").write_text(json.dumps(body), encoding=ENCODING)
    with pytest.raises(ValueError, match="save is version 0"):
        store.load("ancient")

    store.append_trace(
        "stale",
        Turn(
            prompt="I listen.",
            narration="The abbey settles around you.",
            save_version=stale.save_version,
        ),
    )
    with pytest.raises(ValueError, match="trace is version"):
        store.load_trace("stale")


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load(slug)
    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load_trace(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    """A game route supplies these ids, and each one names a directory."""
    with pytest.raises(ValueError, match="invalid content id"):
        load_scenario(tmp_path, "../escape", LONER3E)
    with pytest.raises(ValueError, match="invalid content id"):
        load_character(tmp_path, "kael/../..", LONER3E)
