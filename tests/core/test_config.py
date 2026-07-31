import pytest
from core_test_support import settings

from aidm.config import RoleConfig
from aidm.domain.base import ROLES


def test_every_role_resolves_to_its_explicit_configuration() -> None:
    config = settings()
    for role in ROLES:
        assert isinstance(config.roles.for_role(role), RoleConfig)


def test_test_settings_ignore_ambient_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HISTORY_WINDOW", "99")
    monkeypatch.setenv("ROLES__DIRECTOR__MAX_TOKENS", "7")

    config = settings()

    assert config.history_window == 6
    assert config.roles.director.max_tokens == 2048
