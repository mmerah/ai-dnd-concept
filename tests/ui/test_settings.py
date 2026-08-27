from dataclasses import dataclass
from pathlib import Path

import pytest
from ui_test_support import ui_settings

from aidm.app.launch import LaunchTarget
from aidm.app.runtime import Runtime
from aidm.config import RoleConfig, Roles, load_settings, save_settings
from aidm.ui.settings import _changes  # pyright: ignore[reportPrivateUsage]


@dataclass(frozen=True)
class FakeBox:
    value: object


def test_only_a_real_edit_is_written(tmp_path: Path) -> None:
    settings = ui_settings(saves_dir=tmp_path)
    settings.roles = Roles(director=RoleConfig(temperature=0.7))
    changed = _changes(
        settings,
        {
            ("providers", "openrouter", "api_key"): FakeBox(""),
            ("media", "enabled"): FakeBox(True),
            ("turn", "recent_exchanges"): FakeBox(20.0),
            ("roles", "director", "max_tokens"): FakeBox(9000.0),
            ("roles", "director", "temperature"): FakeBox(None),
        },
    )
    assert changed == {
        ("media", "enabled"): "true",
        ("roles", "director", "max_tokens"): "9000",
        ("roles", "director", "temperature"): None,
    }


def test_a_shell_variable_shadows_its_box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA__ENABLED", "false")
    settings = ui_settings(saves_dir=tmp_path)
    assert _changes(settings, {("media", "enabled"): FakeBox(True)}) == {}


def test_a_saved_key_reads_back_and_the_rest_of_the_file_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    _ = env.write_text("# keep me\nPROVIDERS__OPENROUTER__API_KEY=test\nMEDIA__ENABLED=true\n")
    for shadowing in ("ROLES__DIRECTOR__MAX_TOKENS", "MEDIA__STYLE", "MEDIA__ENABLED"):
        monkeypatch.delenv(shadowing, raising=False)
    monkeypatch.chdir(tmp_path)
    save_settings(
        {
            ("roles", "director", "max_tokens"): "9000",
            ("media", "style"): 'it is "grim"',
            ("media", "enabled"): None,
        }
    )
    reread = load_settings()
    assert reread.roles.director.max_tokens == 9000
    assert reread.media.style == 'it is "grim"'
    assert reread.media.enabled is False
    assert "# keep me" in env.read_text(encoding="utf-8")


def test_settings_are_not_reloaded_under_a_turn_in_flight(tmp_path: Path) -> None:
    runtime = Runtime(ui_settings(saves_dir=tmp_path))
    session = runtime.session(
        LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael")
    )
    assert runtime.busy_refusal() is None
    session.busy = True
    assert runtime.busy_refusal() == "A turn is in flight in 'poc'."
