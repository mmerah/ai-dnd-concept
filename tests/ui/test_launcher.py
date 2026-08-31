import json
import shutil
from pathlib import Path

import pytest
from core_test_support import ENGINES_BUILT, LONER3E
from pydantic import JsonValue
from ui_test_support import SCENARIOS, ui_settings

from aidm.app.launch import LaunchTarget, launch_target, load_catalog
from aidm.app.runtime import Runtime
from aidm.app.spawn import ScriptedSpawner
from aidm.config import Settings
from aidm.content.io import ENCODING, FileStore
from aidm.state.model import Game


def _opening_state(settings: Settings) -> Game:
    """The launcher reads saves, so a test needs a state a real game would have written."""
    target = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael")
    return Runtime(settings, ScriptedSpawner()).session(target).state


def _scenarios_copy(tmp_path: Path) -> Path:
    """Copy only the shipped scenario so generated local scenarios cannot affect counts."""
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS / "whispering-vault", scenarios / "whispering-vault")
    return scenarios


def _declaring(tmp_path: Path, engine: str) -> Path:
    scenarios = _scenarios_copy(tmp_path)
    world = scenarios / "whispering-vault" / "world.json"
    canon: dict[str, JsonValue] = json.loads(world.read_text(encoding=ENCODING))
    canon["engine"] = engine
    _ = world.write_text(json.dumps(canon), encoding=ENCODING)
    return scenarios


def test_an_overlay_decides_which_rules_a_character_offers(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path), ENGINES_BUILT)

    assert catalog.scenario("whispering-vault").engines == ("loner3e",)
    assert [entry.id for entry in catalog.characters_for(LONER3E)] == ["kael"]
    assert launch_target(catalog, "whispering-vault", "kael").model_dump() == {
        "slug": "whispering-vault--kael",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
    }


def test_a_character_without_the_rules_the_scenario_names_is_refused(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path), ENGINES_BUILT)

    with pytest.raises(ValueError, match="has no 'loner3e' rules written for it"):
        _ = launch_target(catalog, "whispering-vault", "nobody")


def test_a_directory_holding_no_canon_is_skipped(tmp_path: Path) -> None:
    scenarios = _scenarios_copy(tmp_path)
    (scenarios / "notes").mkdir()
    shutil.copytree(scenarios / "whispering-vault", scenarios / "aaa-draft")

    catalog = load_catalog(ui_settings(tmp_path, scenarios), ENGINES_BUILT)

    assert [entry.id for entry in catalog.scenarios] == ["aaa-draft", "whispering-vault"]


def test_a_scenario_naming_an_uninstalled_engine_is_skipped(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path, _declaring(tmp_path, "cairn2e")), ENGINES_BUILT)

    assert not catalog.scenarios


def test_launcher_lists_and_resolves_an_existing_save(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path)
    FileStore(tmp_path).save("old-game", _opening_state(settings))

    (saved,) = load_catalog(settings, ENGINES_BUILT).saves

    assert (saved.scenario_title, saved.character_title, saved.turn) == (
        "The Whispering Vault",
        "Kael",
        0,
    )
    assert saved.target.model_dump() == {
        "slug": "old-game",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
    }


@pytest.mark.parametrize(
    "change",
    ({"engine": "retired"}, {"scenario_id": "gone"}, {"character_id": "nobody"}),
    ids=("engine withdrawn", "scenario deleted", "character deleted"),
)
def test_a_save_whose_origin_is_gone_is_not_listed(tmp_path: Path, change: dict[str, str]) -> None:
    settings = ui_settings(tmp_path)
    # Written as JSON: `Game` refuses a withdrawn engine tag, and the catalog reads the envelope.
    orphan = json.loads(_opening_state(settings).model_dump_json()) | change
    (tmp_path / "orphan.json").write_text(json.dumps(orphan), encoding="utf-8")

    assert not load_catalog(settings, ENGINES_BUILT).saves


def test_a_save_the_app_cannot_read_does_not_hide_the_others(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path)
    state = _opening_state(settings)
    FileStore(tmp_path).save("good", state)
    _ = (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)
    stale: dict[str, JsonValue] = json.loads(state.model_dump_json())
    stale["history"] = [{"prompt": "test", "lines": [], "events": [], "outcomes": []}]
    _ = (tmp_path / "stale.json").write_text(json.dumps(stale), encoding=ENCODING)

    catalog = load_catalog(settings, ENGINES_BUILT)

    assert [save.target.slug for save in catalog.saves] == ["good"]
