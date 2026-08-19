from core_test_support import LONER3E, game

from aidm.state import actions
from aidm.state.base import EntityId
from aidm.state.world import AdvanceThread
from aidm.turn.tools import possible

MARA = EntityId("mara")
VAULT_SEAL = "vault-seal"


def test_possible_tracks_the_draft() -> None:
    _, state = game(LONER3E)
    assert possible("move", state) is True  # no predicate: always offered
    assert possible("leave_party", state) is False

    draft = state.draft()
    actions.join_party(draft, MARA)
    state = draft.committed()

    assert possible("leave_party", state) is True


def test_a_thread_put_dormant_can_still_be_moved() -> None:
    """The scene keeps rendering it, so hiding the tool would strand the Director on it."""
    _, state = game(LONER3E)
    draft = state.draft()
    _ = actions.advance_thread(draft, AdvanceThread(thread_id=VAULT_SEAL, status="dormant"))

    assert possible("advance_thread", draft.committed()) is True
