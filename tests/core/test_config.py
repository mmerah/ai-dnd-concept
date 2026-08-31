import pytest
from core_test_support import EnvFileFreeSettings

from aidm.config import MediaConfig


def test_a_role_carries_its_own_model_and_inherits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__MASTER__MODEL", "fable")
    settings = EnvFileFreeSettings()
    assert settings.roles.for_name("master").model == "fable"
    assert settings.roles.for_name("narrator").model == "sonnet"
    assert settings.roles.for_name("narrator").command == ""


def test_illustration_without_a_key_is_refused() -> None:
    with pytest.raises(ValueError, match="no api_key"):
        _ = EnvFileFreeSettings(media=MediaConfig(enabled=True))
