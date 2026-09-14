import pydantic
import pytest
from support.table import EnvFileFreeSettings

from aidm.config import MediaConfig, ProviderConfig, RoleConfig, RoleSettings, SpeechConfig


def test_a_role_carries_its_own_model_and_inherits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROLES__MASTER__MODEL", "fable")
    settings = EnvFileFreeSettings()
    assert settings.roles.for_name("master").model == "fable"
    assert settings.roles.for_name("narrator").model == "sonnet"


def test_illustration_without_a_key_is_refused() -> None:
    with pytest.raises(ValueError, match="no api_key"):
        _ = EnvFileFreeSettings(media=MediaConfig(enabled=True))


def test_speech_without_a_key_is_refused() -> None:
    with pytest.raises(ValueError, match="no api_key"):
        _ = EnvFileFreeSettings(speech=SpeechConfig(enabled=True))


def test_a_role_on_a_provider_without_a_key_is_refused() -> None:
    with pytest.raises(ValueError, match="master uses provider 'openrouter', which has no api_key"):
        _ = EnvFileFreeSettings(
            roles=RoleSettings(master=RoleConfig(provider="openrouter", model="m"))
        )
    local = EnvFileFreeSettings(roles=RoleSettings(master=RoleConfig(provider="local", model="m")))
    assert local.roles.master.provider == "local"


def test_a_misspelled_role_env_var_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROLES__NARATOR__MODEL", "x")
    with pytest.raises(pydantic.ValidationError, match="narator"):
        _ = EnvFileFreeSettings()


def test_a_malformed_provider_base_url_is_refused() -> None:
    with pytest.raises(pydantic.ValidationError, match="base_url"):
        _ = ProviderConfig(base_url="http://[::1/v1", api_key=pydantic.SecretStr(""))
    with pytest.raises(pydantic.ValidationError, match="base_url"):
        _ = ProviderConfig(base_url="http://localhost:99999/v1", api_key=pydantic.SecretStr(""))
    with pytest.raises(pydantic.ValidationError, match="base_url"):
        _ = ProviderConfig(base_url="not a url", api_key=pydantic.SecretStr(""))


def test_both_shipped_provider_base_urls_still_validate() -> None:
    settings = EnvFileFreeSettings()
    assert settings.providers.openrouter.base_url == "https://openrouter.ai/api/v1"
    assert settings.providers.local.base_url == "http://localhost:11434/v1"


def test_a_valid_base_url_is_kept_exactly_as_given_not_normalized() -> None:
    """`AnyHttpUrl` would append a slash to a bare host, doubling the one `post_bearer` adds."""
    provider = ProviderConfig(base_url="http://localhost:1234", api_key=pydantic.SecretStr(""))
    assert provider.base_url == "http://localhost:1234"
