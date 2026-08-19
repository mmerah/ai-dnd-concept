import json
from dataclasses import fields
from pathlib import Path

import pytest
from core_test_support import LONER3E, initialized, scenario, updated
from pydantic import ValidationError

from aidm.app.registry import build_engine
from aidm.content.store import (
    ENCODING,
    FileStore,
    SavedGame,
    load_character,
    load_scenario,
    read_source,
    write_scenario,
)
from aidm.state.world import Game


def test_a_save_carries_every_field_the_played_game_holds() -> None:
    """A field added to `Game` and forgotten in `SavedGame.of` would silently never persist."""
    assert {field.name for field in fields(Game)} | {"save_version"} == set(SavedGame.model_fields)


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


def test_a_save_from_another_build_is_refused(tmp_path: Path) -> None:
    """A file written before `save_version` existed reads as version 0, not as a schema error."""
    _, state = initialized()
    store = FileStore(tmp_path)
    saved = SavedGame.of(state)
    stale = updated(saved, save_version=saved.save_version - 1)

    store.save("stale", stale)
    with pytest.raises(ValueError, match="save is version"):
        store.load("stale")
    with pytest.raises(ValueError, match="save is version"):
        store.shell("stale")

    store.save("ancient", saved)
    body = json.loads((tmp_path / "ancient.json").read_text(encoding=ENCODING))
    del body["save_version"]
    (tmp_path / "ancient.json").write_text(json.dumps(body), encoding=ENCODING)
    with pytest.raises(ValueError, match="save is version 0"):
        store.load("ancient")


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.load(slug)


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
