import pytest

from aidm.engines.breathless.world import SKILLS
from aidm.engines.breathless.worldsmith import SheetDraft


def test_sheet_draft_rated_off_the_creation_spread_is_refused() -> None:
    with pytest.raises(ValueError, match="three d4"):
        SheetDraft(
            pronouns="he/him",
            job="Bell-ringer",
            skills=dict.fromkeys(SKILLS, 12),
            item="Boat hook",
        )
