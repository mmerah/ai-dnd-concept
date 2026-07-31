from aidm.domain.engine import EngineStamp
from aidm_ui.components.engine import EngineAppearance, engine_appearance


def test_engine_badge_clearly_distinguishes_story_from_5e() -> None:
    story = engine_appearance(EngineStamp(id="story", rules_version=1, schema_version=1))
    dnd5e = engine_appearance(EngineStamp(id="dnd5e", rules_version=1, schema_version=1))

    assert story == EngineAppearance(label="STORY · RULES V1", colour="deep-purple-6")
    assert dnd5e == EngineAppearance(label="D&D 5E · RULES V1", colour="red-9")
