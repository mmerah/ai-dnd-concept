import pytest
from core_test_support import EnvFileFreeSettings

from aidm.config import MediaConfig


def test_a_role_with_no_command_of_its_own_falls_back_to_the_masters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__MASTER__COMMAND", "claude -p")
    settings = EnvFileFreeSettings()
    assert settings.roles.for_name("narrator").command == "claude -p"


def test_illustration_without_a_key_is_refused() -> None:
    with pytest.raises(ValueError, match="no api_key"):
        _ = EnvFileFreeSettings(media=MediaConfig(enabled=True))
