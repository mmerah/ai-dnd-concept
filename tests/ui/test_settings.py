from pathlib import Path

import pytest
from nicegui import Client, ui
from pydantic import SecretStr, ValidationError
from support.table import offline_settings, updated

from aidm.config import (
    ProviderConfig,
    RoleConfig,
    RoleSettings,
    Settings,
    read_settings,
    save_settings,
)
from aidm.ui.settings import (
    SettingsForm,
    _widget,  # pyright: ignore[reportPrivateUsage]
    changes,
    refusal_text,
)


def test_only_a_real_edit_is_written(tmp_path: Path) -> None:
    settings = updated(
        offline_settings(tmp_path),
        roles=RoleSettings(narrator=RoleConfig(model="sonnet")).model_dump(),
    )
    assert changes(
        settings,
        {
            ("providers", "openrouter", "api_key"): "",
            ("providers", "openrouter", "base_url"): "",
            ("media", "enabled"): True,
            ("media", "model"): None,
            ("roles", "narrator", "timeout"): 90.0,
        },
    ) == {
        ("providers", "openrouter", "base_url"): None,
        ("media", "enabled"): "true",
        ("media", "model"): None,
        ("roles", "narrator", "timeout"): "90",
    }


def test_settings_are_frozen(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="frozen"):
        offline_settings(tmp_path).roles = RoleSettings()


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


def test_a_second_save_on_the_same_form_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ROLES__NARRATOR__MODEL", raising=False)
    monkeypatch.chdir(tmp_path)

    notified: list[str] = []

    def spy_notify(message: str, **_kwargs: object) -> None:
        notified.append(message)

    monkeypatch.setattr("aidm.ui.settings.ui.notify", spy_notify)

    # The stale snapshot's blind spot: a second save that moves a box back to the snapshot's
    # own value looks like no change at all, so it must be re-read after every save.
    form = SettingsForm(offline_settings(tmp_path))
    client = Client(ui.page("/"))
    try:
        with client:
            widget = ui.input(value="fable")
            form.boxes = {("roles", "narrator", "model"): widget}
            form.save()

            widget.value = "sonnet"
            notified.clear()
            form.save()
    finally:
        client.delete()

    assert read_settings().roles.narrator.model == "sonnet"
    assert "Nothing changed." not in notified


def test_a_validation_error_reads_as_one_line_per_field() -> None:
    with pytest.raises(ValidationError) as raised:
        _ = Settings.model_validate({"roles": {"master": {"timeout": -1}}})

    text = refusal_text(raised.value)
    assert text.startswith("roles.master.timeout: ")
    assert "type=" not in text
    assert "http" not in text


def test_a_stored_secret_is_never_read_back_into_the_page() -> None:
    field = ProviderConfig.model_fields["api_key"]
    stored = _widget("api key", field, SecretStr("sk-live-123"))
    blank = _widget("api key", field, SecretStr(""))

    assert stored.value in (None, "")
    assert stored.props["placeholder"] == "set — type to replace"
    assert blank.props["placeholder"] == "not set"
