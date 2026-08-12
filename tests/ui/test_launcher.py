import shutil
from pathlib import Path

from core_test_support import STORY, updated
from ui_test_support import SCENARIOS, ui_settings

from aidm.app.launcher import LauncherController, LaunchTarget, load_catalog
from aidm.app.session import Runtime
from aidm.config import Settings
from aidm.content.store import ENCODING, FileSaves
from aidm.state.base import EngineId
from aidm.state.world import GameState


def _opening_state(config: Settings, engine: EngineId) -> GameState:
    """The launcher reads saves, so a test needs a state a real game would have written."""
    target = LaunchTarget(
        slug="poc",
        scenario_id="whispering-vault",
        character_id="kael",
        engine=engine,
    )
    return Runtime(config).session(target).state


def _scenarios_copy(tmp_path: Path) -> Path:
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS, scenarios)
    return scenarios


def test_an_overlay_decides_which_rules_a_scenario_offers(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path))
    controller = LauncherController(catalog)

    assert catalog.scenario("whispering-vault").engines == ("story",)
    assert [option.id for option in catalog.characters] == ["kael"]
    controller.choose_engine(STORY)

    assert [option.id for option in controller.compatible_characters()] == ["kael"]
    assert controller.new_game().model_dump() == {
        "slug": "whispering-vault--kael--story",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
        "engine": "story",
    }


def test_content_is_offered_only_for_the_rulesets_it_ships(tmp_path: Path) -> None:
    """An overlay's presence is the whole compatibility check, so this item is the first that lets a
    directory sit under `scenarios/` offering nothing. The home screen is the only way into the app,
    so an unplayable directory has to be skipped rather than break it."""
    scenarios = _scenarios_copy(tmp_path)
    (scenarios / "notes").mkdir()
    shutil.copytree(scenarios / "whispering-vault", scenarios / "aaa-draft")
    (scenarios / "aaa-draft" / "story.json").unlink()

    controller = LauncherController(load_catalog(ui_settings(tmp_path, scenarios)))

    assert [option.id for option in controller.catalog.scenarios] == ["whispering-vault"]
    assert controller.available_engines() == ("story",)
    assert controller.selected_engine == "story"


def test_launcher_lists_and_resolves_an_existing_save(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    FileSaves(tmp_path).save("old-story-game", _opening_state(config, STORY))

    controller = LauncherController(load_catalog(config))
    saved = controller.catalog.save("old-story-game")

    assert (saved.scenario_title, saved.character_title, saved.turn) == (
        "The Whispering Vault",
        "Kael",
        0,
    )
    assert controller.resume(saved.slug).model_dump() == {
        "slug": "old-story-game",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
        "engine": "story",
    }


def test_a_save_whose_rules_were_withdrawn_is_reported_not_offered(tmp_path: Path) -> None:
    """The save still names its origin; that origin no longer ships the overlay it needs."""
    config = ui_settings(tmp_path)
    state = _opening_state(config, STORY)
    FileSaves(tmp_path).save("withdrawn", updated(state, engine="dnd5e"))

    saved = load_catalog(config).save("withdrawn")

    assert not saved.resumable
    assert saved.problem == "scenario 'whispering-vault' no longer offers the 'dnd5e' engine"


def test_a_save_from_another_build_is_reported_not_offered(tmp_path: Path) -> None:
    """Unreadable, not absent: offering it as a new game would crash on navigation."""
    config = ui_settings(tmp_path)
    slug = "whispering-vault--kael--story"
    state = _opening_state(config, STORY)
    FileSaves(tmp_path).save(slug, updated(state, save_version=state.save_version - 1))

    controller = LauncherController(load_catalog(config))

    assert [save.slug for save in controller.catalog.saves] == []
    assert [broken.slug for broken in controller.catalog.unreadable] == [slug]
    assert "save is version" in controller.catalog.unreadable[0].problem
    assert controller.new_game().slug == slug


def test_one_corrupt_save_does_not_hide_the_others_and_stays_readable(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    FileSaves(tmp_path).save("good", _opening_state(config, STORY))
    (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)

    catalog = load_catalog(config)

    assert [save.slug for save in catalog.saves] == ["good"]
    assert [broken.slug for broken in catalog.unreadable] == ["broken"]
    problem = catalog.unreadable[0].problem
    assert "\n" not in problem
    assert len(problem) <= 200
