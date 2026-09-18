from collections.abc import Callable
from pathlib import Path

from nicegui import Client, ui
from support.game import TARGET
from support.table import ENGINES_BUILT, offline_settings

from aidm.app.launch import LauncherCatalog
from aidm.core.io import FileStore, Library
from aidm.ui.app import LaunchForm


def test_an_unresumable_save_renders_no_start_button(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    settings = offline_settings(tmp_path)
    _ = (tmp_path / f"{TARGET.slug}.json").write_bytes(b"\xff\xfe not text")
    library = Library(settings.scenarios_dir, settings.characters_dir)
    catalog = LauncherCatalog.read(library, FileStore(settings.saves_dir), ENGINES_BUILT)
    assert catalog.unresumable == (TARGET.slug,)

    form = LaunchForm(catalog)
    form.scenario_id = TARGET.scenario_id
    form.character_id = TARGET.character_id
    client = page()

    form.form()

    elements = client.elements.values()
    assert not any(isinstance(element, ui.button) for element in elements)
    assert any(
        isinstance(element, ui.label) and "cannot be resumed" in element.text
        for element in elements
    )
