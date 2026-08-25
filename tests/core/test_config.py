import pytest
from core_test_support import EnvFileFreeSettings
from pydantic import SecretStr, ValidationError

from aidm.config import ProviderConfig, Providers, RoleConfig, Roles


def keyed_providers() -> Providers:
    return Providers(
        openrouter=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test"))
    )


def test_a_partial_env_override_leaves_every_other_role_playable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__DIRECTOR__MODEL", "stub/model")
    settings = EnvFileFreeSettings(providers=keyed_providers())
    assert settings.role("director").model == "stub/model"
    assert settings.role("narrator") == RoleConfig()


def test_a_partial_override_keeps_the_roles_own_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__SCENARIO_CREATOR__MODEL", "stub/strong")
    settings = EnvFileFreeSettings(providers=keyed_providers())
    found = settings.role("scenario_creator")
    defaults = Roles().scenario_creator
    assert found.model == "stub/strong"
    assert (found.max_tokens, found.reasoning_effort) == (
        defaults.max_tokens,
        defaults.reasoning_effort,
    )


def keyless_providers() -> Providers:
    return Providers(
        openrouter=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr(""))
    )


def test_a_role_on_a_keyless_provider_is_refused() -> None:
    settings = EnvFileFreeSettings(providers=keyless_providers())
    with pytest.raises(ValueError, match="no api_key"):
        settings.role("director")


def test_configuring_one_role_does_not_key_check_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__DIRECTOR__PROVIDER", "local")
    assert EnvFileFreeSettings(providers=keyless_providers()).role("director").provider == "local"


def test_a_role_no_stage_is_built_for_is_refused() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EnvFileFreeSettings(roles={"bard": RoleConfig()}, providers=keyed_providers())  # pyright: ignore[reportArgumentType]
