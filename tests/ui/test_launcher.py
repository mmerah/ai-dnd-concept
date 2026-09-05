import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import JsonValue
from support.loner import TARGET
from support.table import (
    BREATHLESS,
    ENGINES_BUILT,
    LONER3E,
    TUNNELGOONS,
    TWENTYFOURXX,
    ScriptedSpawner,
    narrowed,
)
from support.ui import REPOSITORY_ROOT, SCENARIOS, ui_settings

from aidm.app.launch import LauncherCatalog
from aidm.app.runtime import Runtime
from aidm.config import Settings
from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING, FileStore, Library
from aidm.core.model import ScenarioMeta
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.seam import AnyEngine

MIRROR = EngineId("mirror")
_MIRRORED = Loner3eEngine()
_MIRRORED.id = MIRROR
# A second engine installed, so the engine the launcher pairs on is observable at all.
INSTALLED = {**ENGINES_BUILT, MIRROR: _MIRRORED}
KAEL_FOR_EACH = [
    ("kael", LONER3E),
    ("kael", TUNNELGOONS),
    ("kael", BREATHLESS),
    ("kael", TWENTYFOURXX),
]


def _catalog(settings: Settings, engines: Mapping[EngineId, AnyEngine]) -> LauncherCatalog:
    library = Library(settings.scenarios_dir, settings.characters_dir)
    return LauncherCatalog.read(library, FileStore(settings.saves_dir), engines)


def _opening_state(settings: Settings) -> Loner3eGame:
    """The launcher reads saves, so a test needs a state a real game would have written."""
    state = Runtime(settings, ScriptedSpawner()).session(TARGET).state
    state = narrowed(state, Loner3eGame)
    return state


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
    catalog = _catalog(ui_settings(tmp_path), ENGINES_BUILT)

    assert catalog.scenario("whispering-vault").title == "The Whispering Vault"
    assert [(entry.id, entry.engine) for entry in catalog.characters] == KAEL_FOR_EACH
    assert catalog.target("whispering-vault", "kael") == TARGET


def test_a_character_the_catalog_does_not_hold_is_refused(tmp_path: Path) -> None:
    catalog = _catalog(ui_settings(tmp_path), ENGINES_BUILT)

    with pytest.raises(Refusal, match="no character 'nobody'"):
        _ = catalog.target("whispering-vault", "nobody")


def test_a_directory_holding_no_canon_is_skipped(tmp_path: Path) -> None:
    scenarios = _scenarios_copy(tmp_path)
    (scenarios / "notes").mkdir()
    shutil.copytree(scenarios / "whispering-vault", scenarios / "aaa-draft")

    catalog = _catalog(ui_settings(tmp_path, scenarios), ENGINES_BUILT)

    assert [entry.id for entry in catalog.scenarios] == ["aaa-draft", "whispering-vault"]


def test_a_scenario_naming_an_uninstalled_engine_is_skipped(tmp_path: Path) -> None:
    catalog = _catalog(ui_settings(tmp_path, _declaring(tmp_path, "cairn2e")), ENGINES_BUILT)

    assert not catalog.scenarios


def test_a_character_is_offered_only_to_the_rules_it_is_written_for(tmp_path: Path) -> None:
    catalog = _catalog(ui_settings(tmp_path, _declaring(tmp_path, MIRROR)), INSTALLED)

    assert [entry.id for entry in catalog.characters_for(LONER3E)] == ["kael"]
    assert catalog.characters_for(MIRROR) == ()
    with pytest.raises(Refusal, match="no character 'kael' is written for the 'mirror' rules"):
        _ = catalog.target("whispering-vault", "kael")


def test_a_save_whose_engine_is_not_the_scenarios_is_not_listed(tmp_path: Path) -> None:
    FileStore(tmp_path).save("whispering-vault--kael", _opening_state(ui_settings(tmp_path)))

    catalog = _catalog(ui_settings(tmp_path, _declaring(tmp_path, MIRROR)), INSTALLED)

    # The scenario and the character are both still there; only the rules disagree.
    assert [(entry.id, entry.engine) for entry in catalog.characters] == KAEL_FOR_EACH
    assert not catalog.saves


def test_launcher_lists_and_resolves_an_existing_save(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path)
    FileStore(tmp_path).save("whispering-vault--kael", _opening_state(settings))

    catalog = _catalog(settings, ENGINES_BUILT)
    (saved,) = catalog.saves

    assert (saved.scenario_title, saved.character_title, saved.turn, saved.rules) == (
        "The Whispering Vault",
        "Kael",
        0,
        "LONER 3E",
    )
    assert catalog.scenario("whispering-vault").rules == "LONER 3E"
    assert saved.target == TARGET


def test_a_save_filed_under_another_stem_is_not_listed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = ui_settings(tmp_path)
    FileStore(tmp_path).save("old-game", _opening_state(settings))

    assert not _catalog(settings, ENGINES_BUILT).saves
    assert "filed under another name" in caplog.text


@pytest.mark.parametrize(
    "change",
    ({"engine": "retired"}, {"scenario_id": "gone"}, {"character_id": "nobody"}),
    ids=("engine withdrawn", "scenario deleted", "character deleted"),
)
def test_a_save_whose_origin_is_gone_is_not_listed(tmp_path: Path, change: dict[str, str]) -> None:
    settings = ui_settings(tmp_path)
    # JSON lets Loner3eGame refuse a withdrawn engine tag while the catalog reads the envelope.
    orphan = json.loads(_opening_state(settings).model_dump_json()) | change
    (tmp_path / "orphan.json").write_text(json.dumps(orphan), encoding="utf-8")

    assert not _catalog(settings, ENGINES_BUILT).saves


def test_a_save_that_fails_to_restore_is_skipped_not_listed(tmp_path: Path) -> None:
    """A stale save is invalid outright: the catalog skips it rather than listing it unopenable."""
    settings = ui_settings(tmp_path)
    state = _opening_state(settings)
    FileStore(tmp_path).save("whispering-vault--kael", state)
    broken = state.model_dump(mode="json")
    broken["payload"]["cast"]["ghost"] = {"name": "Ghost"}
    _ = (tmp_path / "unopenable.json").write_text(json.dumps(broken), encoding=ENCODING)

    catalog = _catalog(settings, ENGINES_BUILT)

    assert [save.target.slug for save in catalog.saves] == ["whispering-vault--kael"]


def test_the_catalog_reports_where_a_save_left_off(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path)
    dumped = _opening_state(settings).model_dump(mode="json")
    _ = (tmp_path / "whispering-vault--kael.json").write_text(json.dumps(dumped), encoding=ENCODING)

    (saved,) = _catalog(settings, ENGINES_BUILT).saves

    assert saved.where == "The Abbot's Study"


def test_a_save_the_app_cannot_read_does_not_hide_the_others(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path)
    state = _opening_state(settings)
    FileStore(tmp_path).save("whispering-vault--kael", state)
    _ = (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)
    stale: dict[str, JsonValue] = json.loads(state.model_dump_json()) | {"turn": -1}
    _ = (tmp_path / "stale.json").write_text(json.dumps(stale), encoding=ENCODING)

    catalog = _catalog(settings, ENGINES_BUILT)

    assert [save.target.slug for save in catalog.saves] == ["whispering-vault--kael"]


def test_a_save_that_is_not_utf8_is_skipped_not_raised(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = ui_settings(tmp_path)
    FileStore(tmp_path).save("whispering-vault--kael", _opening_state(settings))
    _ = (tmp_path / "binary.json").write_bytes(b"\xff\xfe not text")

    catalog = _catalog(settings, ENGINES_BUILT)

    assert [save.target.slug for save in catalog.saves] == ["whispering-vault--kael"]
    assert "skipping save 'binary'" in caplog.text


SOURCE_MD = REPOSITORY_ROOT / "tests/core/fixtures/source/drowned-road.md"
_OPENING_ITEM: JsonValue = {
    "id": "bell-rope",
    "name": "the bell rope",
    "brief": "Frayed, and still wet.",
}
_OPENING: dict[str, JsonValue] = {
    "place": "sunken-bell",
    "title": "The Bell Under the Water",
    "question": "Can you reach the bell tower before the tide turns again?",
    "situation": "The tide has taken the lower town and left the bell tower standing in it, "
    "and something down there still rings the hour.",
    "present": ["hana"],
    "hidden": ["bell-rope"],
    "arc": "Farther down, the bell tower's keeper is still owed for the crossing, and has not "
    "yet been met.",
    "cast": {
        "hana": {
            "id": "hana",
            "name": "Hana",
            "brief": "A ferrywoman who knows the flooded streets.",
            "concept": "A ferrywoman",
        },
        "bell-rope": _OPENING_ITEM,
    },
}


async def test_a_written_opening_becomes_a_playable_scenario(tmp_path: Path) -> None:
    settings = ui_settings(tmp_path, tmp_path / "scenarios")
    thin = json.dumps({**_OPENING, "present": ["nobody-here"]})
    spawner = ScriptedSpawner(answers={"worldsmith": [thin, json.dumps(_OPENING)]})
    runtime = Runtime(settings, spawner)

    meta = ScenarioMeta(
        title="The Sunken Bell",
        premise="The tide took the lower town.",
        scope="One crossing, before the tide turns.",
        art_style="woodcut",
    )
    name = await runtime.new_scenario(LONER3E, meta, None, ("srd",), "kael")

    # The scene bar refuses the first answer, and the reason goes back with the re-prompt.
    assert "these name nobody" in spawner.prompts[1][1]
    # The selected pack is the setting's vocabulary, so the worldsmith is given its tables.
    assert "Quiet Hands" in spawner.prompt("worldsmith")
    catalog = _catalog(settings, runtime.engines)
    state = runtime.session(catalog.target(name, "kael")).state
    engine = runtime.engines[state.engine]
    assert (name, len(engine.history(state))) == ("the-sunken-bell", 0)
    assert state.payload.run.title == "The Bell Under the Water"
    assert state.payload.player.name == "Kael"
    assert state.payload.source.startswith("PREMISE:")
    world = json.loads((settings.scenarios_dir / name / "world.json").read_text(encoding=ENCODING))
    assert world["meta"]["art_style"] == "woodcut"


async def test_an_opening_the_rules_will_not_play_never_reaches_disk(tmp_path: Path) -> None:
    """A structurally broken cast entry fails to parse on both tries, so nothing reaches disk."""
    scenarios = tmp_path / "scenarios"
    cast: dict[str, JsonValue] = {
        "hana": {
            "id": "hana-imposter",
            "name": "Hana",
            "brief": "A ferrywoman.",
        }
    }
    broken = json.dumps(_OPENING | {"cast": {**cast, "bell-rope": _OPENING_ITEM}})
    spawner = ScriptedSpawner(answers={"worldsmith": [broken, broken]})
    runtime = Runtime(ui_settings(tmp_path, scenarios), spawner)

    with pytest.raises(Refusal, match="filed under"):
        _ = await runtime.new_scenario(
            LONER3E,
            ScenarioMeta(title="The Sunken Bell", premise="The tide.", scope="One crossing."),
            None,
            ("srd",),
            "kael",
        )

    assert not scenarios.exists()


async def test_a_scenario_written_from_a_document_keeps_it_beside_the_world(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios"
    spawner = ScriptedSpawner(answers={"worldsmith": [json.dumps(_OPENING)]})
    runtime = Runtime(ui_settings(tmp_path, scenarios), spawner)

    name = await runtime.new_scenario(
        LONER3E,
        ScenarioMeta(title="The Sunken Bell", premise="", scope="One crossing."),
        SOURCE_MD,
        ("srd",),
        "kael",
    )

    assert (scenarios / name / "source.md").is_file()
    catalog = _catalog(runtime.settings, runtime.engines)
    state = runtime.session(catalog.target(name, "kael")).state
    assert state.payload.source.startswith("SOURCE DOCUMENT:")
    # The premise the player never wrote is the scene's own words.
    assert state.scenario.premise == _OPENING["situation"]
