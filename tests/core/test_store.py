import json
import logging
from pathlib import Path

import pytest
from support.loner import character, initialized, scenario
from support.table import ENGINES_BUILT, LONER3E, SCENARIO_MODELS, updated

from aidm.core.entities import EngineId, Refusal
from aidm.core.facts import Fact
from aidm.core.io import (
    ENCODING,
    FileStore,
    read_character,
    read_characters,
    read_scenario,
    read_scenarios,
    write_character,
    write_scenario,
)
from aidm.core.play import Exchange

MIRROR = EngineId("mirror")


def test_a_saved_games_history_round_trips(tmp_path: Path) -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.payload.run.exchanges = [
        Exchange(
            prompt="I take the map.",
            lines=(),
            facts=(
                Fact(
                    kind="entity_moved",
                    trace="the vault map moved to Kael",
                    told=True,
                    card="Took the vault map",
                ),
            ),
        ),
    ]
    saved = draft.commit()
    store = FileStore(tmp_path)

    store.save("roundtrip", saved)
    reloaded = store.load("roundtrip")

    assert reloaded is not None
    assert engine.restore(reloaded).payload.exchanges() == saved.payload.exchanges()


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    with pytest.raises(Refusal, match="invalid content id"):
        read_scenario(tmp_path, "../escape", SCENARIO_MODELS)
    with pytest.raises(Refusal, match="invalid content id"):
        read_character(tmp_path, "kael/../..", engine.id, engine.character)


def test_write_scenario_round_trips_and_refuses_a_duplicate(tmp_path: Path) -> None:
    original = scenario()

    write_scenario(tmp_path, "vault-copy", original)
    loaded = read_scenario(tmp_path, "vault-copy", SCENARIO_MODELS)

    assert loaded == original
    with pytest.raises(Refusal, match="already exists"):
        write_scenario(tmp_path, "vault-copy", original)


def test_read_scenarios_skips_a_world_that_fails_to_validate(tmp_path: Path) -> None:
    original = scenario()
    write_scenario(tmp_path, "good", original)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "world.json").write_text(json.dumps({"meta": {}}), encoding=ENCODING)

    assert [slug for slug, _ in read_scenarios(tmp_path, SCENARIO_MODELS)] == ["good"]


def test_read_scenarios_skips_a_world_that_is_not_json(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_scenario(tmp_path, "good", scenario())
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "world.json").write_text("{not json", encoding=ENCODING)

    with caplog.at_level(logging.WARNING, logger="aidm.core.io"):
        read = [slug for slug, _ in read_scenarios(tmp_path, SCENARIO_MODELS)]

    assert read == ["good"]
    assert "not JSON" in caplog.text


def test_read_scenarios_skips_a_world_that_is_not_utf8(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_scenario(tmp_path, "good", scenario())
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "world.json").write_bytes(b"\xff\xfe{}")

    with caplog.at_level(logging.WARNING, logger="aidm.core.io"):
        read = [slug for slug, _ in read_scenarios(tmp_path, SCENARIO_MODELS)]

    assert read == ["good"]
    assert "is not utf-8" in caplog.text


def test_a_character_written_for_two_engines_is_read_once_for_each(tmp_path: Path) -> None:
    filed = character()
    write_character(tmp_path, filed)
    write_character(tmp_path, updated(filed, engine=MIRROR))

    rows = [
        (name, engine, header.payload.name)
        for name, engine, header in read_characters(tmp_path, (LONER3E, MIRROR))
    ]

    assert rows == [("kael", LONER3E, "Kael"), ("kael", MIRROR, "Kael")]
