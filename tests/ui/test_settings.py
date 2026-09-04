from dataclasses import dataclass
from pathlib import Path

import pytest
from nicegui import ui
from support.loner import TARGET
from support.table import ScriptedSpawner
from support.ui import ui_settings

from aidm.app.runtime import Runtime
from aidm.config import RoleConfig, Roles, read_settings, save_settings
from aidm.ui.settings import SettingsForm, _widget  # pyright: ignore[reportPrivateUsage]


@dataclass(frozen=True)
class FakeBox:
    value: object


def test_only_a_real_edit_is_written(tmp_path: Path) -> None:
    settings = ui_settings(saves_dir=tmp_path)
    settings.roles = Roles(narrator=RoleConfig(model="sonnet"))
    form = SettingsForm(
        settings,
        lambda: None,
        {
            ("providers", "openrouter", "api_key"): FakeBox(""),
            ("media", "enabled"): FakeBox(True),
            ("media", "model"): FakeBox(None),
            ("roles", "narrator", "timeout"): FakeBox(90.0),
        },
    )
    assert form.changes() == {
        ("media", "enabled"): "true",
        ("media", "model"): None,
        ("roles", "narrator", "timeout"): "90",
    }


def test_a_shell_variable_shadows_its_box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA__ENABLED", "false")
    form = SettingsForm(
        ui_settings(saves_dir=tmp_path), lambda: None, {("media", "enabled"): FakeBox(True)}
    )
    assert form.changes() == {}


def test_a_saved_key_reads_back_and_the_rest_of_the_file_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    _ = env.write_text("# keep me\nPROVIDERS__OPENROUTER__API_KEY=test\nMEDIA__ENABLED=true\n")
    for shadowing in ("ROLES__NARRATOR__TIMEOUT", "MEDIA__MODEL", "MEDIA__ENABLED"):
        monkeypatch.delenv(shadowing, raising=False)
    monkeypatch.chdir(tmp_path)
    save_settings(
        {
            ("roles", "narrator", "timeout"): "90",
            ("media", "model"): 'it is "grim"',
            ("media", "enabled"): None,
        }
    )
    reread = read_settings()
    assert reread.roles.narrator.timeout == 90
    assert reread.media.model == 'it is "grim"'
    assert reread.media.enabled is False
    assert "# keep me" in env.read_text(encoding="utf-8")


def test_settings_are_not_reloaded_under_a_turn_in_flight(tmp_path: Path) -> None:
    runtime = Runtime(ui_settings(saves_dir=tmp_path), ScriptedSpawner())
    session = runtime.session(TARGET)
    assert runtime.busy_refusal() is None
    session.phase = "master"
    assert runtime.busy_refusal() == "A turn is in flight in 'whispering-vault--kael'."


def test_a_page_still_holding_a_dropped_session_may_not_play_it(tmp_path: Path) -> None:
    """The reload drops every session, and a tab that kept one would open a second writer."""
    runtime = Runtime(ui_settings(saves_dir=tmp_path), ScriptedSpawner())
    session = runtime.session(TARGET)
    assert runtime.play_refusal(session) is None

    runtime.reload_settings()

    assert runtime.busy_refusal() is None
    assert (
        runtime.play_refusal(session)
        == "The settings changed. Reload this page before you play on."
    )


def test_an_aliased_literal_field_is_a_dropdown() -> None:
    field = RoleConfig.model_fields["provider"]
    assert isinstance(_widget("provider", field, "claude"), ui.select)
