from core_test_support import initialized

from aidm.state.base import EntityDetail, Kind
from aidm.state.turn import Creation
from aidm.turn.pipeline import admitted


def _creation(kind: Kind, name: str) -> Creation:
    return Creation(
        kind=kind, name=name, brief="New canon.", detail=EntityDetail(description="", hook="")
    )


def test_screening_drops_known_names_repeats_and_excess_then_sorts_locations_first() -> None:
    _, state = initialized()

    kept = admitted(
        (
            _creation("actor", "mara"),  # already in the world, casefolded
            _creation("actor", "Iven"),
            _creation("actor", "iven"),  # repeat within this report, casefolded
            _creation("actor", "Nia"),
            _creation("location", "Sol's Hollow"),
            _creation("actor", "Extra"),  # over the cap, dropped
        ),
        state,
        maximum=3,
    )

    assert [(creation.kind, creation.name) for creation in kept] == [
        ("location", "Sol's Hollow"),
        ("actor", "Iven"),
        ("actor", "Nia"),
    ]
