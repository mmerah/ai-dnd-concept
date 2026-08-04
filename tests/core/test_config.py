import pytest
from pydantic import SecretStr

from aidm.core.config import ProviderConfig, Providers, RoleConfig, Settings


def keyed_providers() -> Providers:
    return Providers(
        openrouter=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test"))
    )


def test_a_partial_env_override_leaves_every_other_role_playable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__DIRECTOR__MODEL", "stub/model")
    config = Settings(providers=keyed_providers())
    assert config.role("director").model == "stub/model"
    assert config.role("narrator") == RoleConfig()


def test_a_role_on_a_keyless_provider_is_refused() -> None:
    config = Settings(
        providers=Providers(
            openrouter=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr(""))
        )
    )
    with pytest.raises(ValueError, match="no api_key"):
        config.role("director")
