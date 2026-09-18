import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from pydantic import JsonValue
from support.game import TARGET
from support.table import (
    ENGINES_BUILT,
    LONER3E,
    NO_PACKS,
    REPOSITORY_ROOT,
    SCENARIOS,
    TUNNELGOONS,
    TWENTYFOURXX,
    ScriptedSpawner,
    narrowed,
    offline_settings,
    updated,
)

from aidm.app.launch import LauncherCatalog
from aidm.app.runtime import Runtime
from aidm.config import Settings
from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING, FileStore, Library
from aidm.core.model import ScenarioMeta
from aidm.core.play import DecisionOption
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.loner3e.worldsmith import Loner3ePack
from aidm.engines.registry import build_engines
from aidm.engines.seam import AnyEngine

MIRROR = EngineId("mirror")
_MIRRORED = Loner3eEngine(NO_PACKS)
_MIRRORED.id = MIRROR
# A second engine installed, so the engine the launcher pairs on is observable at all.
INSTALLED = {**ENGINES_BUILT, MIRROR: _MIRRORED}
KAEL_FOR_EACH = [
    ("kael", LONER3E),
    ("kael", TUNNELGOONS),
    ("kael", TWENTYFOURXX),
]


def _catalog(settings: Settings, engines: Mapping[EngineId, AnyEngine]) -> LauncherCatalog:
    library = Library(settings.scenarios_dir, settings.characters_dir)
    return LauncherCatalog.read(library, FileStore(settings.saves_dir), engines)


def _opening_state(settings: Settings) -> Loner3eGame:
    """The launcher reads saves, so a test needs a state a real game would have written."""
    runtime = Runtime(settings, spawner=ScriptedSpawner())
    return narrowed(runtime.session(TARGET).state, Loner3eGame)


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


def _retitled(tmp_path: Path) -> Path:
    scenarios = _scenarios_copy(tmp_path)
    world = scenarios / "whispering-vault" / "world.json"
    canon: dict[str, JsonValue] = json.loads(world.read_text(encoding=ENCODING))
    meta = canon["meta"]
    assert isinstance(meta, dict)
    canon["meta"] = meta | {"title": "The Vault, Renamed"}
    _ = world.write_text(json.dumps(canon), encoding=ENCODING)
    return scenarios


def test_the_catalog_pairs_a_scenario_with_a_character(tmp_path: Path) -> None:
    catalog = _catalog(offline_settings(tmp_path), ENGINES_BUILT)

    assert catalog.scenario("whispering-vault").label == "The Whispering Vault"
    assert [(entry.id, entry.engine) for entry in catalog.characters] == KAEL_FOR_EACH
    assert catalog.target("whispering-vault", "kael") == TARGET


def test_a_character_the_catalog_does_not_hold_is_refused(tmp_path: Path) -> None:
    catalog = _catalog(offline_settings(tmp_path), ENGINES_BUILT)

    with pytest.raises(Refusal, match="no character 'nobody'"):
        _ = catalog.target("whispering-vault", "nobody")


def test_a_directory_holding_no_world_is_skipped(tmp_path: Path) -> None:
    scenarios = _scenarios_copy(tmp_path)
    (scenarios / "notes").mkdir()
    shutil.copytree(scenarios / "whispering-vault", scenarios / "aaa-draft")

    catalog = _catalog(offline_settings(tmp_path, scenarios), ENGINES_BUILT)

    assert [entry.id for entry in catalog.scenarios] == ["aaa-draft", "whispering-vault"]


def test_a_scenario_naming_an_uninstalled_engine_is_skipped(tmp_path: Path) -> None:
    catalog = _catalog(offline_settings(tmp_path, _declaring(tmp_path, "cairn2e")), ENGINES_BUILT)

    assert not catalog.scenarios


def test_a_character_is_offered_only_to_the_rules_it_is_written_for(tmp_path: Path) -> None:
    catalog = _catalog(offline_settings(tmp_path, _declaring(tmp_path, MIRROR)), INSTALLED)

    assert [entry.id for entry in catalog.characters_for(LONER3E)] == ["kael"]
    assert catalog.characters_for(MIRROR) == ()
    with pytest.raises(Refusal, match="no character 'kael' is written for the 'mirror' rules"):
        _ = catalog.target("whispering-vault", "kael")


def test_the_catalog_lists_shipped_and_written_packs(tmp_path: Path) -> None:
    written = tmp_path / "loner3e"
    written.mkdir()
    mine = Loner3ePack(
        name="Mine",
        source="",
        license="",
        concepts=(DecisionOption(id="concept", label="Concept"),),
        skills=(DecisionOption(id="skill", label="Skill"),),
        frailties=(DecisionOption(id="frailty", label="Frailty"),),
        gear=(DecisionOption(id="gear", label="Gear"),),
    )
    (written / "mine.json").write_text(mine.model_dump_json(), encoding=ENCODING)

    catalog = _catalog(offline_settings(tmp_path), build_engines(tmp_path))

    by_id = {entry.id: entry for entry in catalog.packs}
    assert by_id["mine"].written is True
    assert by_id["ap01-fantasy"].written is False
    assert by_id["ap01-fantasy"].tables == (
        "36 concepts · 36 skills · 36 frailties · 36 gear · 6 factions · 6 people · "
        "6 monsters · 6 locations · 36 seeds"
    )


def test_launcher_lists_and_resolves_an_existing_save(tmp_path: Path) -> None:
    settings = offline_settings(tmp_path)
    FileStore(tmp_path).write("whispering-vault--kael", _opening_state(settings))

    catalog = _catalog(settings, ENGINES_BUILT)
    (saved,) = catalog.saves

    assert (saved.scenario_label, saved.character_label, saved.turn, saved.rules) == (
        "The Whispering Vault",
        "Kael",
        0,
        "LONER 3E",
    )
    assert catalog.scenario("whispering-vault").rules == "LONER 3E"
    assert saved.target == TARGET


@pytest.mark.parametrize(
    "change",
    ({"engine": "retired"}, {"scenario_id": "gone"}, {"character_id": "nobody"}),
    ids=("engine withdrawn", "scenario deleted", "character deleted"),
)
def test_a_save_whose_origin_is_gone_is_not_listed(tmp_path: Path, change: dict[str, str]) -> None:
    settings = offline_settings(tmp_path)
    # JSON lets Loner3eGame refuse a withdrawn engine tag while the catalog reads the envelope.
    orphan = json.loads(_opening_state(settings).model_dump_json()) | change
    (tmp_path / "orphan.json").write_text(json.dumps(orphan), encoding="utf-8")

    catalog = _catalog(settings, ENGINES_BUILT)

    assert not catalog.saves
    assert catalog.unresumable == ("orphan",)


def test_the_catalog_reports_where_a_save_left_off(tmp_path: Path) -> None:
    settings = offline_settings(tmp_path)
    dumped = _opening_state(settings).model_dump(mode="json")
    _ = (tmp_path / "whispering-vault--kael.json").write_text(json.dumps(dumped), encoding=ENCODING)

    (saved,) = _catalog(settings, ENGINES_BUILT).saves

    assert saved.where == "The Abbot's Study"


def test_a_save_the_app_cannot_read_does_not_hide_the_others(tmp_path: Path) -> None:
    settings = offline_settings(tmp_path)
    state = _opening_state(settings)
    FileStore(tmp_path).write("whispering-vault--kael", state)
    _ = (tmp_path / "broken.json").write_text("{not json", encoding=ENCODING)
    stale: dict[str, JsonValue] = json.loads(state.model_dump_json()) | {"turn": -1}
    _ = (tmp_path / "stale.json").write_text(json.dumps(stale), encoding=ENCODING)

    catalog = _catalog(settings, ENGINES_BUILT)

    assert [save.target.slug for save in catalog.saves] == ["whispering-vault--kael"]


type BadSave = tuple[Settings, Mapping[EngineId, AnyEngine], str]


def _playing_another_engine(tmp_path: Path) -> BadSave:
    """The scenario and the character are both still there; only the rules disagree."""
    FileStore(tmp_path).write(TARGET.slug, _opening_state(offline_settings(tmp_path)))
    return offline_settings(tmp_path, _declaring(tmp_path, MIRROR)), INSTALLED, TARGET.slug


def _filed_under_another_stem(tmp_path: Path) -> BadSave:
    settings = offline_settings(tmp_path)
    FileStore(tmp_path).write("old-game", _opening_state(settings))
    return settings, ENGINES_BUILT, "old-game"


def _playing_an_uninstalled_pack(tmp_path: Path) -> BadSave:
    settings = offline_settings(tmp_path)
    FileStore(tmp_path).write(TARGET.slug, updated(_opening_state(settings), packs=("srd", "gone")))
    return settings, ENGINES_BUILT, TARGET.slug


def _whose_scenario_drifted(tmp_path: Path) -> BadSave:
    FileStore(tmp_path).write(TARGET.slug, _opening_state(offline_settings(tmp_path)))
    return offline_settings(tmp_path, _retitled(tmp_path)), ENGINES_BUILT, TARGET.slug


def _that_will_not_restore(tmp_path: Path) -> BadSave:
    settings = offline_settings(tmp_path)
    state = _opening_state(settings)
    FileStore(tmp_path).write(TARGET.slug, state)
    broken = state.model_dump(mode="json")
    broken["payload"]["cast"]["ghost"] = {"name": "Ghost"}
    _ = (tmp_path / "unopenable.json").write_text(json.dumps(broken), encoding=ENCODING)
    return settings, ENGINES_BUILT, "unopenable"


def _that_is_not_utf8(tmp_path: Path) -> BadSave:
    settings = offline_settings(tmp_path)
    FileStore(tmp_path).write(TARGET.slug, _opening_state(settings))
    _ = (tmp_path / "binary.json").write_bytes(b"\xff\xfe not text")
    return settings, ENGINES_BUILT, "binary"


@pytest.mark.parametrize(
    ("write", "logged"),
    [
        (_playing_another_engine, "its scenario or character is gone"),
        (_filed_under_another_stem, "filed under another name"),
        (_playing_an_uninstalled_pack, "packs not installed for 'loner3e': ['gone']"),
        (_whose_scenario_drifted, "save scenario differs from the one on disk in: title"),
        (_that_will_not_restore, "payload.cast.ghost.id: Field required"),
        (_that_is_not_utf8, "binary.json cannot be read"),
    ],
    ids=(
        "another engine",
        "another stem",
        "an uninstalled pack",
        "a drifted scenario",
        "a state that will not restore",
        "bytes that are not text",
    ),
)
def test_a_save_the_launcher_cannot_resume_is_skipped_not_listed(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    write: Callable[[Path], BadSave],
    logged: str,
) -> None:
    """A stale save is invalid outright: the catalog skips it rather than listing it unopenable."""
    settings, engines, bad = write(tmp_path)

    catalog = _catalog(settings, engines)

    written = sorted(path.stem for path in tmp_path.glob("*.json"))
    assert [save.target.slug for save in catalog.saves] == [stem for stem in written if stem != bad]
    assert bad in catalog.unresumable
    assert logged in caplog.text


SOURCE_MD = REPOSITORY_ROOT / "tests/core/fixtures/source/drowned-road.md"
_OPENING_ITEM: JsonValue = {
    "id": "bell-rope",
    "name": "the bell rope",
    "brief": "Frayed, and still wet.",
}
_OPENING: dict[str, JsonValue] = {
    "place": "sunken-bell",
    "title": "The Bell Under the Water",
    "focus": "Can you reach the bell tower before the tide turns again?",
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
    settings = offline_settings(tmp_path, tmp_path / "scenarios")
    thin = json.dumps({**_OPENING, "present": ["nobody-here"]})
    spawner = ScriptedSpawner(answers={"worldsmith": [thin, json.dumps(_OPENING)]})
    runtime = Runtime(settings, spawner=spawner)

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
    assert (name, len(state.exchanges())) == ("the-sunken-bell", 0)
    assert state.payload.run.title == "The Bell Under the Water"
    assert state.payload.player.name == "Kael"
    assert state.source.startswith("PREMISE:")
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
    runtime = Runtime(offline_settings(tmp_path, scenarios), spawner=spawner)

    with pytest.raises(Refusal, match="the worldsmith answered nothing usable") as failed:
        _ = await runtime.new_scenario(
            LONER3E,
            ScenarioMeta(title="The Sunken Bell", premise="The tide.", scope="One crossing."),
            None,
            ("srd",),
            "kael",
        )

    assert "filed under" not in str(failed.value)
    assert not scenarios.exists()


async def test_new_scenario_refuses_a_character_the_selection_cannot_start(tmp_path: Path) -> None:
    """The mismatch is caught before the worldsmith is spawned, not after it has written."""
    characters = tmp_path / "characters"
    shutil.copytree(REPOSITORY_ROOT / "characters", characters)
    sheet = characters / "kael" / "loner3e.json"
    widened = json.loads(sheet.read_text(encoding=ENCODING)) | {"packs": ["srd", "ap01-fantasy"]}
    sheet.write_text(json.dumps(widened), encoding=ENCODING)
    settings = offline_settings(tmp_path, tmp_path / "scenarios").model_copy(
        update={"characters_dir": characters}
    )
    spawner = ScriptedSpawner()
    runtime = Runtime(settings, spawner=spawner)

    with pytest.raises(Refusal, match="this scenario plays srd"):
        _ = await runtime.new_scenario(
            LONER3E,
            ScenarioMeta(title="The Sunken Bell", premise="The tide.", scope="One crossing."),
            None,
            ("srd",),
            "kael",
        )

    assert spawner.prompts == []


async def test_a_scenario_written_from_a_document_carries_its_text(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios"
    spawner = ScriptedSpawner(answers={"worldsmith": [json.dumps(_OPENING)]})
    runtime = Runtime(offline_settings(tmp_path, scenarios), spawner=spawner)

    name = await runtime.new_scenario(
        LONER3E,
        ScenarioMeta(title="The Sunken Bell", premise="", scope="One crossing."),
        SOURCE_MD,
        ("srd",),
        "kael",
    )

    catalog = _catalog(runtime.settings, runtime.engines)
    state = runtime.session(catalog.target(name, "kael")).state
    assert state.source.startswith("SOURCE DOCUMENT:")
    # The premise the player never wrote is the scene's own words.
    assert state.scenario.premise == _OPENING["situation"]
