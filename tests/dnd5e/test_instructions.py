from aidm.engines.dnd5e.direction import CONSEQUENCE_TYPES
from aidm.engines.dnd5e.engine import build_dnd5e_engine


def test_every_consequence_documents_itself_into_the_live_director_prompt() -> None:
    """Assert the prompt the Director is actually given, not the text it is assembled from."""
    live = build_dnd5e_engine().director.instructions()
    for consequence in CONSEQUENCE_TYPES:
        action = consequence.model_fields["action"].default
        assert isinstance(action, str)
        assert action in live
        assert consequence.GUIDANCE.strip() in live
