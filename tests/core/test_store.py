import json
from dataclasses import fields
from pathlib import Path

import pytest
from core_test_support import LONER3E, initialized, scenario
from pydantic import ValidationError

from aidm.app.launch import build_engine, engine_ids
from aidm.content.io import (
    ENCODING,
    FileStore,
    SavedGame,
    load_character,
    load_scenario,
    read_scenarios,
    write_scenario,
)
from aidm.state.model import Game


def test_a_save_carries_every_field_the_played_game_holds() -> None:
    """A field added to `Game` and forgotten in `SavedGame.of` would silently never persist."""
    assert {field.name for field in fields(Game)} == set(SavedGame.model_fields)


def test_shell_reads_a_save_whose_world_is_garbage(tmp_path: Path) -> None:
    _, state = initialized()
    store = FileStore(tmp_path)
    body = json.loads(SavedGame.of(state).model_dump_json())
    body["world"] = {"entities": {"player": "garbage"}}
    (tmp_path / "broken.json").write_text(json.dumps(body), encoding=ENCODING)

    shell = store.shell("broken")

    assert shell is not None
    assert (shell.engine, shell.scenario_id, shell.turn) == (LONER3E, "whispering-vault", 0)
    with pytest.raises(ValidationError):
        store.load("broken")


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    """A game route supplies these ids, and each one names a directory."""
    engine = build_engine(LONER3E)
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

    assert [slug for slug, _, _ in read_scenarios(tmp_path, engine_ids())] == ["good"]
