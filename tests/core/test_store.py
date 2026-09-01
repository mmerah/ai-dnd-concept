import json
from pathlib import Path

import pytest
from core_test_support import (
    ENGINES_BUILT,
    LONER3E,
    SCENARIO_MODELS,
    character,
    initialized,
    scenario,
    updated,
)

from aidm.core.entities import EngineId
from aidm.core.facts import Fact
from aidm.core.io import (
    ENCODING,
    FileStore,
    load_character,
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
    draft.payload.world.run.exchanges = [
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
    saved = draft.committed()
    store = FileStore(tmp_path)

    store.save("roundtrip", saved)
    reloaded = store.load("roundtrip")

    assert reloaded is not None
    assert engine.restored(reloaded).payload.world.exchanges() == saved.payload.world.exchanges()


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    with pytest.raises(ValueError, match="invalid content id"):
        read_scenario(tmp_path, "../escape", SCENARIO_MODELS)
    with pytest.raises(ValueError, match="invalid content id"):
        load_character(tmp_path, "kael/../..", engine.id, engine.character)


def test_write_scenario_round_trips_and_refuses_a_duplicate(tmp_path: Path) -> None:
    original = scenario()

    write_scenario(tmp_path, "vault-copy", original)
    loaded = read_scenario(tmp_path, "vault-copy", SCENARIO_MODELS)

    assert loaded == original
    with pytest.raises(ValueError, match="already exists"):
        write_scenario(tmp_path, "vault-copy", original)


def test_read_scenarios_skips_a_world_that_fails_to_validate(tmp_path: Path) -> None:
    original = scenario()
    write_scenario(tmp_path, "good", original)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "world.json").write_text(json.dumps({"meta": {}}), encoding=ENCODING)

    assert [slug for slug, _ in read_scenarios(tmp_path, SCENARIO_MODELS)] == ["good"]


def test_a_character_written_for_two_engines_is_read_once_for_each(tmp_path: Path) -> None:
    written = character()
    write_character(tmp_path, written)
    write_character(tmp_path, updated(written, engine=MIRROR))

    models = {
        LONER3E: ENGINES_BUILT[LONER3E].character,
        MIRROR: ENGINES_BUILT[LONER3E].character,
    }
    rows = [(name, engine) for name, engine, _ in read_characters(tmp_path, models)]

    assert rows == [("kael", LONER3E), ("kael", MIRROR)]
