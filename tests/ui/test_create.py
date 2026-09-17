from pathlib import Path

import pytest
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

    _drop_stale(engine.creation_steps(("srd",), picks), picks)

    assert picks["increase-1"] == "Piloting"


def test_a_constrained_step_still_loses_an_answer_it_no_longer_offers() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    picks = dict(ANDROID) | {"body": "not-on-offer"}

    _drop_stale(engine.creation_steps(("srd",), picks), picks)

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
        assert form.packs == ("srd", "ap01-fantasy")
    finally:
        client.delete()


def test_rolling_a_seed_writes_one_of_the_selected_packs_seeds(tmp_path: Path) -> None:
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


def test_a_third_supplement_is_refused_and_the_select_goes_back_to_the_two_in_play(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    notified: list[str] = []

    def spy_notify(message: str, **_kwargs: object) -> None:
        notified.append(message)

    monkeypatch.setattr("aidm.ui.widgets.ui.notify", spy_notify)
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
            assert form.supplements is not None
            form.supplements.value = ["ap01-fantasy", "ap02-space", "ap03-superheroes"]
        assert form.packs == ("srd", "ap01-fantasy")
        assert form.supplements.value == ["ap01-fantasy"]
    finally:
        client.delete()
    assert notified and "at most" in notified[0]
