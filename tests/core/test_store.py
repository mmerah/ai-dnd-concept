import logging
from pathlib import Path

import pytest
from support.game import character, initialized, scenario
from support.table import ENGINES_BUILT, LONER3E, SCENARIO_MODELS, updated

from aidm.core.entities import EngineId, Refusal
from aidm.core.facts import Fact
from aidm.core.io import ENCODING, WORLD_FILE, FileStore, Library, publish, write_text
from aidm.core.play import Exchange

MIRROR = EngineId("mirror")


def test_a_saved_games_history_round_trips(tmp_path: Path) -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.log[-1].exchanges = [
        Exchange(
            words="I take the map.",
            lines=(),
            facts=(
                Fact(
                    trace="the vault map moved to Kael",
                    told=True,
                    card="Took the vault map",
                ),
            ),
        ),
    ]
    saved = draft.commit()
    store = FileStore(tmp_path)

    store.write("roundtrip", saved)
    reloaded = store.read("roundtrip")

    assert reloaded is not None
    assert engine.restore(reloaded).exchanges() == saved.exchanges()


@pytest.mark.parametrize("slug", ("../escape", "/absolute", "bad slug", ""))
def test_storage_rejects_unsafe_slugs(tmp_path: Path, slug: str) -> None:
    store = FileStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage slug"):
        store.read(slug)


def test_content_paths_reject_an_unsafe_id(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    library = Library(tmp_path, tmp_path)
    with pytest.raises(Refusal, match="invalid content id"):
        library.read_scenario("../escape", SCENARIO_MODELS)
    with pytest.raises(Refusal, match="invalid content id"):
        library.read_character("kael/../..", engine.id, engine.character)


def test_write_scenario_round_trips_and_refuses_a_duplicate(tmp_path: Path) -> None:
    original = scenario()
    library = Library(tmp_path, tmp_path)

    library.write_scenario("vault-copy", original)
    loaded = library.read_scenario("vault-copy", SCENARIO_MODELS)

    assert loaded == original
    with pytest.raises(Refusal, match="already exists"):
        library.write_scenario("vault-copy", original)


def _beside_a_broken_world(directory: Path, world: bytes) -> Library:
    library = Library(directory, directory)
    library.write_scenario("good", scenario())
    (directory / "broken").mkdir()
    (directory / "broken" / "world.json").write_bytes(world)
    return library


def test_read_scenarios_skips_a_world_that_fails_to_validate(tmp_path: Path) -> None:
    library = _beside_a_broken_world(tmp_path, b'{"meta": {}}')

    assert [slug for slug, _ in library.read_scenarios(SCENARIO_MODELS)] == ["good"]


def test_read_scenarios_skips_a_world_that_is_not_json(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    library = _beside_a_broken_world(tmp_path, b"{not json")

    with caplog.at_level(logging.WARNING, logger="aidm.core.io"):
        read = [slug for slug, _ in library.read_scenarios(SCENARIO_MODELS)]

    assert read == ["good"]
    assert "not JSON" in caplog.text


def test_read_scenarios_skips_a_world_that_is_not_utf8(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    library = _beside_a_broken_world(tmp_path, b"\xff\xfe{}")

    with caplog.at_level(logging.WARNING, logger="aidm.core.io"):
        read = [slug for slug, _ in library.read_scenarios(SCENARIO_MODELS)]

    assert read == ["good"]
    assert "cannot be read" in caplog.text


def test_a_character_written_for_two_engines_is_read_once_for_each(tmp_path: Path) -> None:
    filed = character()
    library = Library(tmp_path, tmp_path)
    library.write_character(filed)
    library.write_character(updated(filed, engine=MIRROR))

    rows = [
        (name, engine, header.payload.name)
        for name, engine, header in library.read_characters((LONER3E, MIRROR))
    ]

    assert rows == [("kael", LONER3E, "Kael"), ("kael", MIRROR, "Kael")]


def test_read_characters_skips_a_stray_file_and_a_non_slug_folder(tmp_path: Path) -> None:
    library = Library(tmp_path, tmp_path)
    library.write_character(character())
    (tmp_path / ".DS_Store").write_text("", encoding=ENCODING)
    backup = tmp_path / "My Backup"
    backup.mkdir()
    (backup / f"{LONER3E}.json").write_text("{}", encoding=ENCODING)

    rows = [name for name, _, _ in library.read_characters((LONER3E,))]

    assert rows == ["kael"]


def test_read_scenarios_of_a_missing_directory_yields_nothing(tmp_path: Path) -> None:
    missing = tmp_path / "scenarios"

    assert list(Library(missing, missing).read_scenarios(SCENARIO_MODELS)) == []


def test_a_save_that_cannot_be_written_refuses(tmp_path: Path) -> None:
    blocking = tmp_path / "saves"
    blocking.write_text("", encoding=ENCODING)

    with pytest.raises(Refusal, match="cannot be written"):
        write_text(blocking / "game.json", "{}")


def test_a_write_that_fails_midway_leaves_the_old_file_and_no_staged_file(tmp_path: Path) -> None:
    path = tmp_path / "game.json"
    path.write_text("old", encoding=ENCODING)

    def _broken(staged: Path) -> None:
        staged.write_text("partial", encoding=ENCODING)
        raise OSError("disk full")

    with pytest.raises(Refusal, match="cannot be written"):
        publish(path, _broken)

    assert path.read_text(encoding=ENCODING) == "old"
    assert list(tmp_path.iterdir()) == [path]


def test_read_scenarios_skips_a_scenario_whose_world_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    library = Library(tmp_path, tmp_path)
    library.write_scenario("good", scenario())
    broken = tmp_path / "broken" / WORLD_FILE
    broken.parent.mkdir()
    broken.write_text("{}", encoding=ENCODING)
    original_read_text = Path.read_text

    def _read_text(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self == broken:
            raise OSError("permission denied")
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", _read_text)

    with caplog.at_level(logging.WARNING, logger="aidm.core.io"):
        read = [slug for slug, _ in library.read_scenarios(SCENARIO_MODELS)]

    assert read == ["good"]
    assert "cannot be read" in caplog.text
