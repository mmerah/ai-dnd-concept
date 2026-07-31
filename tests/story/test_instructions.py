from aidm_story.direction import STORY_CONSEQUENCE_TYPES
from aidm_story.factory import build_story_engine


def test_every_story_consequence_documents_itself_into_the_live_director_prompt() -> None:
    live = build_story_engine().director.instructions()
    for consequence in STORY_CONSEQUENCE_TYPES:
        action = consequence.model_fields["action"].default
        assert isinstance(action, str)
        assert f"`{action}`" in live
        assert consequence.GUIDANCE.strip() in live
