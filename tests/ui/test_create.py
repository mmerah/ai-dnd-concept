from pathlib import Path

from nicegui import Client, ui
from support.table import ENGINES_BUILT, LONER3E, ScriptedSpawner, offline_settings

from aidm.app.launch import CatalogEntry, LauncherCatalog
from aidm.app.runtime import Runtime
from aidm.core.entities import EngineId, Slug
from aidm.ui.create import ScenarioForm, _drop_stale  # pyright: ignore[reportPrivateUsage]

TWENTYFOURXX = EngineId("twentyfourxx")
ANDROID: dict[Slug, str] = {
    "specialty": "muscle",
    "specialty-choice": "hand-to-hand",
    "weapon": "sword",
    "origin": "android",
    "body": "case",
}


def test_a_free_text_step_keeps_its_answer_which_the_page_keys_by_label() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"increase-1": "Piloting"}

    _drop_stale(engine.creation_steps(picks), picks)

    assert picks["increase-1"] == "Piloting"


def test_a_constrained_step_still_loses_an_answer_it_no_longer_offers() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"body": "not-on-offer"}

    _drop_stale(engine.creation_steps(picks), picks)

    assert "body" not in picks


def test_picking_a_character_made_with_ap01_fantasy_selects_it(tmp_path: Path) -> None:
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
    runtime = Runtime(offline_settings(tmp_path), lambda _: ScriptedSpawner())
    form = ScenarioForm(runtime, catalog)
    client = Client(ui.page("/"))
    try:
        with client:
            form.build()
        assert form.supplements is not None and form.supplements.value == ["ap01-fantasy"]
    finally:
        client.delete()


def test_rolling_a_seed_writes_one_of_the_chosen_packs_seeds(tmp_path: Path) -> None:
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
    runtime = Runtime(offline_settings(tmp_path), lambda _: ScriptedSpawner())
    form = ScenarioForm(runtime, catalog)
    client = Client(ui.page("/"))
    try:
        with client:
            form.build()
            form.roll_seed()
        assert form.premise.value in ENGINES_BUILT[LONER3E].packs.installed["ap01-fantasy"].seeds
    finally:
        client.delete()
