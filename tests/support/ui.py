from pathlib import Path

from pydantic import SecretStr

from aidm.config import ProviderConfig, Providers, Settings
from support.table import REPOSITORY_ROOT, SCENARIOS, EnvFileFreeSettings


def ui_settings(saves_dir: Path, scenarios_dir: Path = SCENARIOS) -> Settings:
    return EnvFileFreeSettings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        scenarios_dir=scenarios_dir,
        characters_dir=REPOSITORY_ROOT / "characters",
        saves_dir=saves_dir,
    )
