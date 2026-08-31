import json
import shutil
from pathlib import Path

import pytest
from core_test_support import ENGINES_BUILT, ScriptedSpawner
from pydantic import JsonValue
from ui_test_support import REPOSITORY_ROOT, SCENARIOS, ui_settings

from aidm.app.launch import LaunchTarget, launch_target, load_catalog
from aidm.app.runtime import Runtime
from aidm.config import Settings
from aidm.core.io import ENCODING, FileStore
from aidm.core.model import Game


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


def test_the_catalog_pairs_a_scenario_with_a_character(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path), ENGINES_BUILT)

    assert catalog.scenario("whispering-vault").title == "The Whispering Vault"
    assert [entry.id for entry in catalog.characters] == ["kael"]
    assert launch_target(catalog, "whispering-vault", "kael").model_dump() == {
        "slug": "whispering-vault--kael",
        "scenario_id": "whispering-vault",
        "character_id": "kael",
    }


def test_a_character_the_catalog_does_not_hold_is_refused(tmp_path: Path) -> None:
    catalog = load_catalog(ui_settings(tmp_path), ENGINES_BUILT)

    with pytest.raises(ValueError, match="no character 'nobody'"):
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


SOURCE_MD = REPOSITORY_ROOT / "tests/core/fixtures/source/drowned-road.md"
_OPENING_ITEM: JsonValue = {
    "id": "bell-rope",
    "kind": "item",
    "name": "the bell rope",
    "brief": "Frayed, and still wet.",
    "sheet": {"kind": "item"},
}
_OPENING: dict[str, JsonValue] = {
    "place": "sunken-bell",
    "title": "The Bell Under the Water",
    "question": "Can you reach the bell tower before the tide turns again?",
    "situation": "The tide has taken the lower town and left the bell tower standing in it, "
    "and something down there still rings the hour.",
    "present": ["hana"],
    "hidden": ["bell-rope"],
    "cast": {
        "hana": {
            "id": "hana",
            "kind": "actor",
            "name": "Hana",
            "brief": "A ferrywoman who knows the flooded streets.",
            "sheet": {"kind": "actor", "concept": "A ferrywoman"},
        },
        "bell-rope": _OPENING_ITEM,
    },
    "threads": {"the-bell": {"id": "the-bell", "title": "Who rings the bell"}},
}


async def test_a_written_opening_becomes_a_playable_scenario(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path, tmp_path / "scenarios")
    thin = json.dumps(
        {key: value for key, value in _OPENING.items() if key not in ("present", "hidden")}
    )
    spawner = ScriptedSpawner(answers={"worldsmith": [thin, json.dumps(_OPENING)]})
    runtime = Runtime(settings, spawner)

    name = await runtime.new_scenario(
        "The Sunken Bell", "The tide took the lower town.", None, ("srd",), "kael"
    )

    # The scene bar refuses the first answer, and the reason goes back with the re-prompt.
    assert "besides the player" in spawner.prompts[1][1]
    # The selected pack is the setting's vocabulary, so the worldsmith is given its tables.
    assert "Quiet Hands" in spawner.prompt("worldsmith")
    catalog = load_catalog(settings, runtime.engines)
    state = runtime.session(launch_target(catalog, name, "kael")).state
    assert (name, state.turn) == ("the-sunken-bell", 0)
    assert state.world.current.title == "The Bell Under the Water"
    assert state.world.player.name == "Kael"
    assert state.world.source.startswith("PREMISE:")


async def test_an_opening_the_rules_will_not_play_never_reaches_disk(tmp_path: Path) -> None:
    """The scene bar is the kit's; only the engine knows an actor of its own needs a sheet."""
    scenarios = tmp_path / "scenarios"
    cast: dict[str, JsonValue] = {
        "hana": {"id": "hana", "kind": "actor", "name": "Hana", "brief": "A ferrywoman."}
    }
    sheetless = json.dumps(_OPENING | {"cast": {**cast, "bell-rope": _OPENING_ITEM}})
    spawner = ScriptedSpawner(answers={"worldsmith": [sheetless, sheetless]})
    runtime = Runtime(ui_settings(tmp_path, scenarios), spawner)

    with pytest.raises(ValueError, match="has no sheet"):
        _ = await runtime.new_scenario("The Sunken Bell", "The tide.", None, ("srd",), "kael")

    assert not scenarios.exists()


async def test_a_scenario_written_from_a_document_keeps_it_beside_the_world(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios"
    spawner = ScriptedSpawner(answers={"worldsmith": [json.dumps(_OPENING)]})
    runtime = Runtime(ui_settings(tmp_path, scenarios), spawner)

    name = await runtime.new_scenario("The Sunken Bell", "", SOURCE_MD, ("srd",), "kael")

    assert (scenarios / name / "source.md").is_file()
    state = runtime.session(
        launch_target(load_catalog(runtime.settings, runtime.engines), name, "kael")
    ).state
    assert state.world.source.startswith("SOURCE DOCUMENT:")
    # The premise the player never wrote is the scene's own words.
    assert state.scenario.premise == _OPENING["situation"]
