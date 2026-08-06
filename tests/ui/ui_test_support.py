from pathlib import Path

from pydantic import SecretStr

from aidm.config import ProviderConfig, Providers, Settings

REPOSITORY_ROOT = Path(__file__).parents[2]


SCENARIOS = REPOSITORY_ROOT / "scenarios"


def ui_settings(saves_dir: Path, scenarios_dir: Path = SCENARIOS) -> Settings:
    return Settings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        max_growth=3,
        history_window=6,
        scenarios_dir=scenarios_dir,
        characters_dir=REPOSITORY_ROOT / "characters",
        saves_dir=saves_dir,
    )
