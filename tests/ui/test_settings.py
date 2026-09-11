from pathlib import Path

import pytest
from pydantic import ValidationError
from support.game import TARGET
from support.table import ScriptedSpawner, offline_settings

from aidm.app.runtime import Runtime
from aidm.config import RoleConfig, RoleSettings, Settings, read_settings, save_settings
from aidm.ui.settings import (
    _refusal_text,  # pyright: ignore[reportPrivateUsage]
    changes,
)


def test_only_a_real_edit_is_written(tmp_path: Path) -> None:
    settings = offline_settings(tmp_path)
    settings.roles = RoleSettings(narrator=RoleConfig(model="sonnet"))
    assert changes(
        settings,
        {
            ("providers", "openrouter", "api_key"): "",
            ("media", "enabled"): True,
            ("media", "model"): None,
            ("roles", "narrator", "timeout"): 90.0,
        },
    ) == {
        ("media", "enabled"): "true",
        ("media", "model"): None,
        ("roles", "narrator", "timeout"): "90",
    }


def test_a_shell_variable_shadows_its_box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA__ENABLED", "false")
    assert changes(offline_settings(tmp_path), {("media", "enabled"): True}) == {}


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
    runtime = Runtime(offline_settings(tmp_path), ScriptedSpawner())
    session = runtime.session(TARGET)
    assert runtime.busy_refusal() is None
    session.phase = "master"
    assert runtime.busy_refusal() == "A turn is in flight in 'whispering-vault--kael'."


def test_a_page_still_holding_a_dropped_session_may_not_play_it(tmp_path: Path) -> None:
    """The reload drops every session, and a tab that kept one would open a second writer."""
    runtime = Runtime(offline_settings(tmp_path), ScriptedSpawner())
    session = runtime.session(TARGET)
    assert runtime.play_refusal(session) is None

    runtime.reload_settings()

    assert runtime.busy_refusal() is None
    assert (
        runtime.play_refusal(session)
        == "The settings changed. Reload this page before you play on."
    )


def test_a_validation_error_reads_as_one_line_per_field() -> None:
    with pytest.raises(ValidationError) as raised:
        _ = Settings.model_validate({"roles": {"master": {"timeout": -1}}})

    text = _refusal_text(raised.value)
    assert text.startswith("roles.master.timeout: ")
    assert "type=" not in text
    assert "http" not in text
