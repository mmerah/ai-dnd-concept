import pytest
from core_test_support import EnvFileFreeSettings
from pydantic import SecretStr, ValidationError

from aidm.config import ROLE_DEFAULTS, ProviderConfig, Providers, RoleConfig


def keyed_providers() -> Providers:
    return Providers(
        openrouter=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test"))
    )


def test_a_partial_env_override_leaves_every_other_role_playable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__DIRECTOR__MODEL", "stub/model")
    config = EnvFileFreeSettings(providers=keyed_providers())
    assert config.role("director").model == "stub/model"
    assert config.role("narrator") == RoleConfig()


def test_a_partial_override_keeps_the_roles_own_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__SCENARIO_CREATOR__MODEL", "stub/strong")
    config = EnvFileFreeSettings(providers=keyed_providers())
    found = config.role("scenario_creator")
    defaults = ROLE_DEFAULTS["scenario_creator"]
    assert found.model == "stub/strong"
    assert (found.max_tokens, found.reasoning_effort) == (
        defaults.max_tokens,
        defaults.reasoning_effort,
    )


def test_a_role_on_a_keyless_provider_is_refused() -> None:
    config = EnvFileFreeSettings(
        providers=Providers(
            openrouter=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr(""))
        ),
    )
    with pytest.raises(ValueError, match="no api_key"):
        config.role("director")


def test_a_role_no_stage_is_built_for_is_refused() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        EnvFileFreeSettings(roles={"bard": RoleConfig()}, providers=keyed_providers())  # pyright: ignore[reportArgumentType]
