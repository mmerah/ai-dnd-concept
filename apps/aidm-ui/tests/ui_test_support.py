from pathlib import Path

from aidm.config import ProviderConfig, Providers, Roles, Settings
from pydantic import SecretStr

REPOSITORY_ROOT = Path(__file__).parents[3]


def ui_settings(saves_dir: Path) -> Settings:
    return Settings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        roles=Roles(),
        max_growth=3,
        history_window=6,
        scenarios_dir=REPOSITORY_ROOT / "scenarios",
        characters_dir=REPOSITORY_ROOT / "characters",
        saves_dir=saves_dir,
    )
