import json
from pathlib import Path

import pytest
from core_test_support import ENGINE_IDS, ENGINES_BUILT, LONER3E, initialized, scenario

from aidm.content.io import (
    ENCODING,
    FileStore,
    load_character,
    load_scenario,
    read_scenarios,
    write_scenario,
)
from aidm.state.facts import EventBadge, MechanicEvent
from aidm.state.play import Exchange


def test_a_saved_games_exchange_events_round_trip(tmp_path: Path) -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.history = (
        Exchange(
            prompt="I take the map.",
            place="the sealed vault",
            lines=(),
            events=(
                MechanicEvent(
                    title="the vault map moved to Kael",
                    badges=(EventBadge(label="Position", value="Neutral"),),
                ),
            ),
        ),
    )
    saved = draft.committed()
    store = FileStore(tmp_path)

    store.save("roundtrip", saved)
    reloaded = store.load("roundtrip")

    assert reloaded is not None
    assert engine.restored(reloaded).history == saved.history


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    with pytest.raises(ValueError, match="invalid content id"):
        load_scenario(tmp_path, "../escape")
    with pytest.raises(ValueError, match="invalid content id"):
        load_character(tmp_path, "kael/../..", engine.id, engine.check_overlay)


def test_write_scenario_round_trips_and_refuses_a_duplicate(tmp_path: Path) -> None:
    original = scenario()

    write_scenario(tmp_path, "vault-copy", original)
    loaded = load_scenario(tmp_path, "vault-copy")

    assert loaded == original
    with pytest.raises(ValueError, match="already exists"):
        write_scenario(tmp_path, "vault-copy", original)


def test_read_scenarios_skips_a_world_that_fails_to_validate(tmp_path: Path) -> None:
    original = scenario()
    write_scenario(tmp_path, "good", original)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "world.json").write_text(json.dumps({"meta": {}}), encoding=ENCODING)

    assert [slug for slug, _ in read_scenarios(tmp_path, ENGINE_IDS)] == ["good"]
