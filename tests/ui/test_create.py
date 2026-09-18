from collections.abc import Callable
from pathlib import Path

from nicegui import Client
from support.table import ENGINES_BUILT, LONER3E, ScriptedSpawner, offline_settings

from aidm.app.launch import CatalogEntry, LauncherCatalog
from aidm.app.runtime import Runtime
from aidm.ui.create import ScenarioForm


def test_picking_a_character_made_with_ap01_fantasy_selects_it(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    entry = CatalogEntry(
        id="kael",
        engine=LONER3E,
        label="Kael",
        detail="a wanderer",
        rules="LONER 3E",
        look=ENGINES_BUILT[LONER3E].look,
        packs=("srd", "ap01-fantasy"),
    )
    catalog = LauncherCatalog(scenarios=(), characters=(entry,), packs=(), saves=(), unresumable=())
    runtime = Runtime(offline_settings(tmp_path), spawner=ScriptedSpawner())
    form = ScenarioForm(runtime, catalog)
    page()

    form.build()

    assert form.packs == ("srd", "ap01-fantasy")


def test_rolling_a_seed_writes_one_of_the_selected_packs_seeds(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    entry = CatalogEntry(
        id="kael",
        engine=LONER3E,
        label="Kael",
        detail="a wanderer",
        rules="LONER 3E",
        look=ENGINES_BUILT[LONER3E].look,
        packs=("srd", "ap01-fantasy"),
    )
    catalog = LauncherCatalog(scenarios=(), characters=(entry,), packs=(), saves=(), unresumable=())
    runtime = Runtime(offline_settings(tmp_path), spawner=ScriptedSpawner())
    form = ScenarioForm(runtime, catalog)
    page()
    form.build()

    form.roll_seed()

    assert form.premise.value in ENGINES_BUILT[LONER3E].packs.installed["ap01-fantasy"].seeds


def test_a_third_supplement_is_refused_and_the_select_goes_back_to_the_two_in_play(
    tmp_path: Path, page: Callable[[], Client], notified: list[str]
) -> None:
    entry = CatalogEntry(
        id="kael",
        engine=LONER3E,
        label="Kael",
        detail="a wanderer",
        rules="LONER 3E",
        look=ENGINES_BUILT[LONER3E].look,
        packs=("srd", "ap01-fantasy"),
    )
    catalog = LauncherCatalog(scenarios=(), characters=(entry,), packs=(), saves=(), unresumable=())
    runtime = Runtime(offline_settings(tmp_path), spawner=ScriptedSpawner())
    form = ScenarioForm(runtime, catalog)
    page()
    form.build()
    assert form.supplements is not None

    form.supplements.value = ["ap01-fantasy", "ap02-space", "ap03-superheroes"]

    assert form.packs == ("srd", "ap01-fantasy")
    assert form.supplements.value == ["ap01-fantasy"]
    assert notified and "at most" in notified[0]
