from aidm.config import Settings


def load_settings() -> Settings:
    return Settings.model_validate({})
