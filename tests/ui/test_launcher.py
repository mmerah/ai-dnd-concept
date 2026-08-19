import shutil
from pathlib import Path

from core_test_support import LONER3E, updated
from ui_test_support import SCENARIOS, ui_settings

from aidm.app.launcher import LauncherController, LaunchTarget, load_catalog
from aidm.app.session import Runtime
from aidm.config import Settings
from aidm.content.store import ENCODING, FileStore, SavedGame
from aidm.state.base import SAVE_VERSION, EngineId
from aidm.state.world import Game


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
    """Only the shipped scenario: `scenarios/` also holds generated ones, and a catalogue
    assertion that counts them moves every time somebody authors one."""
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS / "whispering-vault", scenarios / "whispering-vault")
    return scenarios


def test_an_overlay_decides_which_rules_a_scenario_offers(tmp_path: Path) -> None:
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


def test_content_is_offered_only_for_the_rulesets_it_ships(tmp_path: Path) -> None:
    """An overlay's presence is the whole compatibility check, so this item is the first that lets a
    directory sit under `scenarios/` offering nothing. The home screen is the only way into the app,
    so an unplayable directory has to be skipped rather than break it."""
    scenarios = _scenarios_copy(tmp_path)
    (scenarios / "notes").mkdir()
    shutil.copytree(scenarios / "whispering-vault", scenarios / "aaa-draft")
    for overlay in (scenarios / "aaa-draft").glob("*.json"):
        if overlay.name != "world.json":
            overlay.unlink()

    controller = LauncherController(load_catalog(ui_settings(tmp_path, scenarios)))

    assert [option.id for option in controller.catalog.scenarios] == ["whispering-vault"]
    assert controller.available_engines() == ("loner3e", "twentyfourxx")
    assert controller.selected_engine == "loner3e"


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
    """The save still names its origin; that origin no longer ships the overlay it needs."""
    config = ui_settings(tmp_path)
    state = _opening_state(config, LONER3E)
    FileStore(tmp_path).save("withdrawn", updated(SavedGame.of(state), engine="retired"))

    saved = load_catalog(config).save("withdrawn")

    assert not saved.resumable
    assert saved.problem == "scenario 'whispering-vault' no longer offers the 'retired' engine"


def test_a_save_from_another_build_is_reported_not_offered(tmp_path: Path) -> None:
    """Unreadable, not absent: offering it as a new game would crash on navigation."""
    config = ui_settings(tmp_path)
    slug = "whispering-vault--kael--loner3e"
    state = _opening_state(config, LONER3E)
    FileStore(tmp_path).save(slug, updated(SavedGame.of(state), save_version=SAVE_VERSION - 1))

    controller = LauncherController(load_catalog(config))
    controller.choose_scenario("whispering-vault")

    assert [save.slug for save in controller.catalog.saves] == []
    assert [broken.slug for broken in controller.catalog.unreadable] == [slug]
    assert "save is version" in controller.catalog.unreadable[0].problem
    assert controller.new_game().slug == slug


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
