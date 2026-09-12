from pathlib import Path

import pytest
from pydantic import ValidationError
from support.table import offline_settings

from aidm.config import RoleConfig, RoleSettings, Settings, read_settings, save_settings
from aidm.ui.settings import changes, refusal_text


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


def test_a_validation_error_reads_as_one_line_per_field() -> None:
    with pytest.raises(ValidationError) as raised:
        _ = Settings.model_validate({"roles": {"master": {"timeout": -1}}})

    text = refusal_text(raised.value)
    assert text.startswith("roles.master.timeout: ")
    assert "type=" not in text
    assert "http" not in text
