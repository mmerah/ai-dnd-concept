from core_test_support import initialized

from aidm.engines.core import complete_chapter
from aidm.state import actions
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import player_events
from aidm.state.model import AdvanceThread

CLOISTER = EntityId("cloister")
BELL_TOWER = EntityId("bell-tower")
VAULT = EntityId("vault")
TOMAS = EntityId("tomas")
STUDY = EntityId("study")
LANTERN = EntityId("lantern")
VAULT_MAP = EntityId("vault-map")
MARA = EntityId("mara")


def test_a_visible_move_produces_a_card() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = tuple(actions.move(draft, PLAYER_ID, CLOISTER))

    (event,) = player_events(facts)
    assert event.title == f"{draft.player.name} moved to {draft.world.require(CLOISTER).name}"
    assert "[" not in event.title
    assert event.dice == ()
    assert event.badges == ()


def test_move_card_titles_read_who_moved_and_who_or_where_received_it() -> None:
    _, state = initialized()
    draft = state.draft()

    (taken,) = player_events(tuple(actions.move(draft, VAULT_MAP, PLAYER_ID)))
    assert taken.title == "Took the vault map"

    (given,) = player_events(tuple(actions.move(draft, VAULT_MAP, MARA)))
    assert given.title == "Gave the vault map to Mara"

    (left,) = player_events(tuple(actions.move(draft, LANTERN, STUDY)))
    assert left.title == "Left a guttering lantern at the abbot's study"


def test_advance_thread_produces_no_event() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = tuple(
        actions.advance_thread(draft, AdvanceThread(thread_id="vault-seal", status="active"))
    )

    assert not any(fact.told for fact in facts)
    assert player_events(facts) == ()


def test_completing_the_chapter_produces_a_card() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = tuple(complete_chapter(draft, "the adventure has ended"))

    (event,) = player_events(facts)
    assert event.title == "the adventure has ended"
    assert event.icon == "auto_stories"


def test_gain_improvised_item_produces_a_took_card() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = tuple(actions.improvise(draft, "a handful of gravel"))

    (event,) = player_events(facts)
    assert event.title == "Took a handful of gravel"
    assert event.icon == "back_hand"


def test_the_reveal_tool_produces_a_discovered_card() -> None:
    _, state = initialized()
    draft = state.draft()

    (event,) = player_events(tuple(actions.reveal(draft, VAULT_MAP)))
    assert event.title == "The vault map discovered"
    assert event.icon == "visibility"


def test_the_remaining_core_cards_carry_id_free_titles() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)
    way = draft.world.require(CLOISTER).exit_to(VAULT)
    assert way is not None
    way.known = True  # a locked way must be known to narrate, or unlocking it stays silent

    (unlocked,) = player_events(tuple(actions.unlock_exit(draft, VAULT)))
    assert unlocked.title == "The sealed vault unlocked"

    (joined,) = player_events(tuple(actions.join_party(draft, TOMAS)))
    assert joined.title == "Brother Tomas joins your party"

    (left,) = player_events(tuple(actions.leave_party(draft, TOMAS)))
    assert left.title == "Brother Tomas leaves your party"

    added_facts = tuple(actions.add_trait(draft, TOMAS, "wary", "he watches the door"))
    (added,) = player_events(added_facts)
    assert added.title == "Brother Tomas gained Wary"

    removed_facts = tuple(actions.remove_trait(draft, TOMAS, "wary"))
    (removed,) = player_events(removed_facts)
    assert removed.title == "Brother Tomas lost Wary"


def test_a_tool_call_on_an_unrevealed_entity_produces_nothing() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = tuple(actions.add_trait(draft, BELL_TOWER, "haunted", "a cold draft moves through it"))

    assert not any(fact.told for fact in facts)
    assert player_events(facts) == ()
