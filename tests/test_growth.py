"""Screening is deterministic policy: reject duplicate names, dedup within a batch, then cap —
and every drop is recorded with its reason, never silently discarded."""

from aidm.domain.models.entities import GrowthRequest
from aidm.domain.models.state import GameState
from aidm.engine.growth import screen


def _req(name: str) -> GrowthRequest:
    return GrowthRequest(kind="actor", name=name, brief="b")


def test_a_request_matching_an_existing_name_is_rejected(state: GameState) -> None:
    # "Mara" already exists in canon, spelled here in a different case
    screened = screen([_req("mara"), _req("Elgin")], state.world.entities, cap=3)
    assert [r.name for r in screened.accepted] == ["Elgin"]
    assert [(r.request.name, r.reason) for r in screened.rejected] == [("mara", "duplicate_name")]


def test_a_repeat_within_one_batch_is_created_once(state: GameState) -> None:
    screened = screen([_req("Elgin"), _req("elgin")], state.world.entities, cap=3)
    assert [r.name for r in screened.accepted] == ["Elgin"]
    assert [(r.request.name, r.reason) for r in screened.rejected] == [("elgin", "duplicate_name")]


def test_over_cap_requests_are_rejected_not_dropped(state: GameState) -> None:
    screened = screen([_req(f"N{i}") for i in range(6)], state.world.entities, cap=3)
    assert len(screened.accepted) == 3
    assert [r.reason for r in screened.rejected] == ["over_cap", "over_cap", "over_cap"]
