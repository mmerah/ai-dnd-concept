from pathlib import Path

import pytest
from ui_test_support import ui_settings

from aidm.application.launcher import LauncherController, load_catalog
from aidm.domain.engine import DependencyStamp
from aidm.domain.state import GameState, WorldState
from aidm.store import ENCODING, FileSaves
from aidm.utils.models import updated
from aidm_ui.bootstrap import create_composition


def test_launcher_filters_characters_by_the_scenario_engine(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    composition = create_composition(config)
    catalog = load_catalog(config, composition.installed_stamp)
    controller = LauncherController(catalog)

    assert {scenario.engine.id for scenario in catalog.scenarios} == {"story", "dnd5e"}
    controller.choose_scenario("whispering_vault_5e")

    assert [character.name for character in controller.compatible_characters()] == ["kael_5e"]
    assert controller.new_game().model_dump() == {
        "slug": "whispering_vault_5e--kael_5e",
        "scenario_name": "whispering_vault_5e",
        "character_name": "kael_5e",
    }


def test_launcher_lists_and_resolves_an_existing_save(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    application = create_composition(config).application("poc", "whispering_vault", "kael")
    FileSaves(tmp_path).save("old-story-game", application.state)

    composition = create_composition(config)
    controller = LauncherController(load_catalog(config, composition.installed_stamp))
    saved = controller.catalog.save("old-story-game")

    assert (saved.scenario_title, saved.character_title, saved.turn) == (
        "The Whispering Vault",
        "Kael",
        0,
    )
    assert controller.resume(saved.slug).model_dump() == {
        "slug": "old-story-game",
        "scenario_name": "whispering_vault",
        "character_name": "kael",
    }


def test_a_save_from_another_build_is_reported_not_offered(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    application = create_composition(config).application("poc", "whispering_vault", "kael")
    stale = updated(application.state, version=application.state.version - 1)
    FileSaves(tmp_path).save("stale", stale)

    composition = create_composition(config)
    controller = LauncherController(load_catalog(config, composition.installed_stamp))
    saved = controller.catalog.save("stale")

    assert not saved.resumable
    assert "save version" in (saved.problem or "")
    with pytest.raises(ValueError, match="save version"):
        _ = controller.resume("stale")


def test_a_save_with_different_engine_dependencies_is_not_offered(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    composition = create_composition(config)
    application = composition.application("poc", "whispering_vault", "kael")
    stale = updated(
        application.state,
        engine=updated(
            application.state.engine,
            dependencies=(DependencyStamp(kind="content-pack", id="old-pack", version="old"),),
        ),
    )
    FileSaves(tmp_path).save("stale-dependencies", stale)

    controller = LauncherController(load_catalog(config, composition.installed_stamp))
    saved = controller.catalog.save("stale-dependencies")

    assert not saved.resumable
    assert "dependencies" in (saved.problem or "")


def test_a_save_with_a_different_engine_schema_is_not_offered(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    composition = create_composition(config)
    application = composition.application("poc", "whispering_vault", "kael")
    stale = _with_schema_version(application.state, 2)
    FileSaves(tmp_path).save("stale-schema", stale)

    controller = LauncherController(load_catalog(config, composition.installed_stamp))
    saved = controller.catalog.save("stale-schema")

    assert not saved.resumable
    assert "schema_version" in (saved.problem or "")


def test_one_corrupt_save_does_not_hide_the_others(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    composition = create_composition(config)
    application = composition.application("poc", "whispering_vault", "kael")
    FileSaves(tmp_path).save("good", application.state)
    (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)

    catalog = load_catalog(config, composition.installed_stamp)

    assert [save.slug for save in catalog.saves] == ["good"]
    assert [broken.slug for broken in catalog.unreadable] == ["broken"]


def _with_schema_version(state: GameState, schema_version: int) -> GameState:
    entities = {
        entity.id: updated(
            entity,
            rules=(
                None
                if entity.rules is None
                else updated(entity.rules, schema_version=schema_version)
            ),
        )
        for entity in state.world.entities.values()
    }
    return updated(
        state,
        engine=updated(state.engine, schema_version=schema_version),
        rules=updated(state.rules, schema_version=schema_version),
        world=WorldState(entities=entities),
    )
