import json
from pathlib import Path

import pytest
from core_test_support import LONER3E, initialized, scenario, updated
from pydantic import ValidationError

from aidm.app.session import build_engine
from aidm.content.store import (
    ENCODING,
    FileStore,
    load_character,
    load_scenario,
    read_source,
    write_scenario,
)
from aidm.state.base import PLAYER_ID
from aidm.state.facts import Fact, narrator_evidence
from aidm.state.trace import Applied, StepTrace, Turn


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


def test_a_trace_round_trips_its_turn_and_applied_entries(tmp_path: Path) -> None:
    """A Turn and an Applied, each carrying real facts, survive an append and a reload unchanged."""
    store = FileStore(tmp_path)
    facts = (
        Fact(kind="dice_rolled", trace="a falling stone: 1d6 [4] -> 4"),
        Fact(kind="counter_changed", trace="Kael luck -1 -> 5/6", narrator="hurt"),
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
    applied = Applied(subject_id=PLAYER_ID, facts=facts)

    store.append_trace("poc", turn)
    store.append_trace("poc", applied)
    reloaded = store.load_trace("poc")

    assert reloaded == (turn, applied)
    director_output = reloaded[0].steps[0].output if isinstance(reloaded[0], Turn) else None
    assert (
        isinstance(director_output, dict)
        and director_output["intent"] == "Kael endures a falling stone."
    )
    assert isinstance(reloaded[1], Applied)


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
    binding = build_engine(LONER3E).binding()
    with pytest.raises(ValueError, match="invalid content id"):
        load_scenario(tmp_path, "../escape", binding)
    with pytest.raises(ValueError, match="invalid content id"):
        load_character(tmp_path, "kael/../..", binding)


def test_write_scenario_round_trips_and_refuses_a_duplicate(tmp_path: Path) -> None:
    original = scenario()
    binding = build_engine(LONER3E).binding()

    write_scenario(tmp_path, "vault-copy", original.world, {LONER3E: original.overlay})
    loaded = load_scenario(tmp_path, "vault-copy", binding)

    assert (loaded.world, loaded.overlay) == (original.world, original.overlay)
    with pytest.raises(ValueError, match="already exists"):
        write_scenario(tmp_path, "vault-copy", original.world, {LONER3E: original.overlay})


def test_a_scenario_expands_from_its_own_source_or_else_from_its_premise(tmp_path: Path) -> None:
    original = scenario()
    premise = "The abbey emptied in a night, and the road out is not where it was."
    grown = updated(original.world, expansion="invented")

    write_scenario(tmp_path, "grown", grown, {LONER3E: original.overlay}, premise)
    write_scenario(tmp_path, "curated", original.world, {LONER3E: original.overlay})
    loaded = load_scenario(tmp_path, "grown", build_engine(LONER3E).binding())

    assert loaded.world.expansion == "invented"
    assert read_source(tmp_path, "grown", "unread").passages("road") == premise
    assert read_source(tmp_path, "curated", premise).passages("road") == premise
