"""The point of R3: every consequence documents itself into the Director's assembled prompt."""

from aidm.agents import instructions
from aidm.domain.models import CONSEQUENCE_TYPES


def test_every_consequence_is_documented_to_the_director() -> None:
    for consequence in CONSEQUENCE_TYPES:
        assert consequence.GUIDANCE.strip()
        assert str(consequence.model_fields["action"].default) in instructions.DIRECTOR
