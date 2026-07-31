from pathlib import Path

from ui_test_support import ui_settings

from aidm.application.launcher import LauncherController, load_catalog
from aidm.store import ENCODING, FileSaves
from aidm.utils.models import updated
from aidm_ui.bootstrap import create_composition


def test_launcher_filters_characters_by_the_scenario_engine(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    catalog = load_catalog(config)
    controller = LauncherController(catalog)

    assert {scenario.engine for scenario in catalog.scenarios} == {"story", "dnd5e"}
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

    controller = LauncherController(load_catalog(config))
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
    state = application.state
    FileSaves(tmp_path).save("stale", updated(state, save_version=state.save_version - 1))

    catalog = load_catalog(config)

    assert [save.slug for save in catalog.saves] == []
    assert [broken.slug for broken in catalog.unreadable] == ["stale"]
    assert "save is version" in catalog.unreadable[0].problem


def test_an_unresumable_save_is_never_offered_as_a_new_game(tmp_path: Path) -> None:
    """A save the loader refuses is unreadable, not absent: starting over would crash on open."""
    config = ui_settings(tmp_path)
    slug = "whispering_vault--kael"
    application = create_composition(config).application(slug, "whispering_vault", "kael")
    state = application.state
    FileSaves(tmp_path).save(slug, updated(state, save_version=state.save_version - 1))

    controller = LauncherController(load_catalog(config))
    controller.choose_scenario("whispering_vault")

    assert controller.new_game().slug == slug
    assert [save.slug for save in controller.catalog.unreadable] == [slug]


def test_one_corrupt_save_does_not_hide_the_others_and_stays_readable(tmp_path: Path) -> None:
    config = ui_settings(tmp_path)
    application = create_composition(config).application("poc", "whispering_vault", "kael")
    FileSaves(tmp_path).save("good", application.state)
    (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)

    catalog = load_catalog(config)

    assert [save.slug for save in catalog.saves] == ["good"]
    assert [broken.slug for broken in catalog.unreadable] == ["broken"]
    problem = catalog.unreadable[0].problem
    assert "\n" not in problem
    assert len(problem) <= 200
