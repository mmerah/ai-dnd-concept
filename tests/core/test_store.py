import json
from pathlib import Path

import pytest
from core_test_support import initialized

from aidm.domain.direction import DirectionRecord
from aidm.domain.growth import Growth
from aidm.domain.turn import Turn
from aidm.store import ENCODING, FileSaves, FileTraces
from aidm.utils.models import updated


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
        direction=DirectionRecord(
            engine="story",
            schema_version=1,
            intent="Listen.",
            tone="quiet",
            speaker_id=None,
            mechanics=(),
        ),
        narration="The abbey settles around you.",
        narrator_evidence="- learned of the vault",
        growth=Growth(),
        state=state,
        prompts={"director": "exact director prompt"},
    )
    traces.append("current", turn)
    traces.append("current", updated(turn, prompt="I knock."))
    assert [held.prompt for held in traces.load("current")] == [
        "I listen.",
        "I knock.",
    ]

    saves.discard("current")
    traces.discard("current")
    assert saves.load("current") is None
    assert traces.load("current") == ()


def test_a_save_or_trace_from_another_build_is_refused(tmp_path: Path) -> None:
    _, state = initialized()
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)
    stale = updated(state, save_version=state.save_version - 1)

    saves.save("stale", stale)
    with pytest.raises(ValueError, match="save is version"):
        saves.load("stale")

    traces.append(
        "stale",
        Turn(
            prompt="I listen.",
            direction=DirectionRecord(
                engine="story",
                schema_version=1,
                intent="Listen.",
                tone="quiet",
                speaker_id=None,
                mechanics=(),
            ),
            narration="The abbey settles around you.",
            narrator_evidence="- nothing changed",
            growth=Growth(),
            state=stale,
        ),
    )
    with pytest.raises(ValueError, match="trace is version"):
        traces.load("stale")


def test_a_save_written_before_versioning_is_refused_readably(tmp_path: Path) -> None:
    _, state = initialized()
    saves = FileSaves(tmp_path)
    saves.save("ancient", state)
    body = json.loads((tmp_path / "ancient.json").read_text(encoding=ENCODING))
    del body["save_version"]
    (tmp_path / "ancient.json").write_text(json.dumps(body), encoding=ENCODING)

    with pytest.raises(ValueError, match="save is version 0"):
        saves.load("ancient")


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    saves = FileSaves(tmp_path)
    traces = FileTraces(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        saves.load(slug)
    with pytest.raises(ValueError, match="invalid storage slug"):
        traces.load(slug)
