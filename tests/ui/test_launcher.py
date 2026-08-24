import json
import shutil
from pathlib import Path

from core_test_support import LONER3E, updated
from pydantic import JsonValue
from ui_test_support import SCENARIOS, ui_settings

from aidm.app.launch import LauncherController, LaunchTarget, load_catalog
from aidm.app.runtime import Runtime
from aidm.config import Settings
from aidm.content.io import ENCODING, FileStore, SavedGame
from aidm.state.entities import EngineId
from aidm.state.model import Game


def _opening_state(config: Settings, engine: EngineId) -> Game:
    """The launcher reads saves, so a test needs a state a real game would have written."""
    target = LaunchTarget(
        slug="poc",
        scenario_id="whispering-vault",
        character_id="kael",
        engine=engine,
    )
    return Runtime(config).session(target).state


def _scenarios_copy(tmp_path: Path) -> Path:
    """Copy only the shipped scenario so generated local scenarios cannot affect counts."""
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS / "whispering-vault", scenarios / "whispering-vault")
    return scenarios


def _declaring(tmp_path: Path, *engines: str) -> Path:
    scenarios = _scenarios_copy(tmp_path)
    world = scenarios / "whispering-vault" / "world.json"
    canon: dict[str, JsonValue] = json.loads(world.read_text(encoding=ENCODING))
    canon["engines"] = list(engines)
    _ = world.write_text(json.dumps(canon), encoding=ENCODING)
    return scenarios


def test_an_overlay_decides_which_rules_a_character_offers(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path))
    controller = LauncherController(catalog)

    assert catalog.scenario("whispering-vault").engines == ("loner3e", "twentyfourxx")
    assert [option.id for option in catalog.characters] == ["kael"]
    controller.choose_scenario("whispering-vault")
    controller.choose_engine(LONER3E)

    assert [option.id for option in controller.compatible_characters()] == ["kael"]
    assert controller.new_game().model_dump() == {
        "slug": "whispering-vault--kael--loner3e",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
        "engine": "loner3e",
    }


def test_a_directory_holding_no_canon_is_skipped(tmp_path: Path) -> None:
    scenarios = _scenarios_copy(tmp_path)
    (scenarios / "notes").mkdir()
    shutil.copytree(scenarios / "whispering-vault", scenarios / "aaa-draft")

    controller = LauncherController(load_catalog(ui_settings(tmp_path, scenarios)))

    assert [option.id for option in controller.catalog.scenarios] == [
        "aaa-draft",
        "whispering-vault",
    ]
    controller.choose_scenario("aaa-draft")
    assert controller.available_engines() == ("loner3e", "twentyfourxx")
    assert controller.selected_engine == "loner3e"


def test_a_scenario_offers_only_the_rules_it_names(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path, _declaring(tmp_path, "loner3e")))

    assert catalog.scenario("whispering-vault").engines == ("loner3e",)


def test_a_scenario_naming_an_uninstalled_engine_is_skipped(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path, _declaring(tmp_path, "cairn2e")))

    assert not catalog.scenarios


def test_launcher_lists_and_resolves_an_existing_save(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    FileStore(tmp_path).save("old-game", SavedGame.of(_opening_state(config, LONER3E)))

    controller = LauncherController(load_catalog(config))
    saved = controller.catalog.save("old-game")

    assert (saved.scenario_title, saved.character_title, saved.turn) == (
        "The Whispering Vault",
        "Kael",
        0,
    )
    assert controller.resume(saved.slug).model_dump() == {
        "slug": "old-game",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
        "engine": "loner3e",
    }


def test_a_save_whose_rules_were_withdrawn_is_reported_not_offered(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    state = _opening_state(config, LONER3E)
    FileStore(tmp_path).save("withdrawn", updated(SavedGame.of(state), engine="retired"))

    saved = load_catalog(config).save("withdrawn")

    assert not saved.resumable
    assert saved.problem == "scenario 'whispering-vault' no longer offers the 'retired' engine"


def test_one_corrupt_save_does_not_hide_the_others_and_stays_readable(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    FileStore(tmp_path).save("good", SavedGame.of(_opening_state(config, LONER3E)))
    (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)

    catalog = load_catalog(config)

    assert [save.slug for save in catalog.saves] == ["good"]
    assert [broken.slug for broken in catalog.unreadable] == ["broken"]
    problem = catalog.unreadable[0].problem
    assert "\n" not in problem
    assert len(problem) <= 200

    controller = LauncherController(catalog)
    controller.choose_scenario("whispering-vault")
    assert controller.new_game().slug == "whispering-vault--kael--loner3e"


def test_a_save_whose_body_is_stale_is_reported_not_offered(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    body = json.loads(SavedGame.of(_opening_state(config, LONER3E)).model_dump_json())
    body["history"] = [{"prompt": "test", "lines": [], "events": [], "outcomes": []}]
    (tmp_path / "stale.json").write_text(json.dumps(body), encoding=ENCODING)

    catalog = load_catalog(config)

    assert not catalog.saves
    assert [broken.slug for broken in catalog.unreadable] == ["stale"]
    assert "\n" not in catalog.unreadable[0].problem


def test_a_save_whose_mechanics_are_broken_is_reported_not_offered(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    body = json.loads(SavedGame.of(_opening_state(config, LONER3E)).model_dump_json())
    body["mechanics"] = {"not": "the loner3e shape"}
    (tmp_path / "broken-mechanics.json").write_text(json.dumps(body), encoding=ENCODING)

    catalog = load_catalog(config)

    assert not catalog.saves
    assert [broken.slug for broken in catalog.unreadable] == ["broken-mechanics"]
