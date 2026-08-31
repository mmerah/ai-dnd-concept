import pytest
from core_test_support import initialized, updated

from aidm.engines.loner3e.state import ActorSheet, LonerSheet
from aidm.kits.scenes.boundary import QUIET_TURNS, SCENE_TURN_CAP, scene_spent
from aidm.kits.scenes.state import Entity, Thread
from aidm.kits.scenes.tools import ChangeWorld, apply_change
from aidm.kits.scenes.worldsmith import MIN_SITUATION, SceneDraft, apply_scene, scene_refusal
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import Fact, cards
from aidm.state.model import Game
from aidm.state.play import Exchange

MAP = EntityId("vault-map")
RING = EntityId("ring")
MARA = EntityId("mara")
TOMAS = EntityId("tomas")

SITUATION = (
    "A frost-rimed colonnade around a dead garden, and the way down is somewhere under it. "
    "Nothing here has been swept in a long while."
)


def changed_facts(draft: Game, verb: str, **fields: object) -> list[Fact]:
    change = ChangeWorld.model_validate({"change": {"verb": verb, **fields}})
    return apply_change(draft.world, change.change)


def changed(draft: Game, verb: str, **fields: object) -> list[str]:
    return [fact.trace for fact in changed_facts(draft, verb, **fields)]


def _carded(turns: int) -> tuple[Exchange, ...]:
    """Turns that each landed something, so only the cap can end the scene."""
    card = Fact(kind="trait_added", trace="something happened", told=True, card="Something")
    return tuple(
        Exchange(prompt="I press on.", scene="The Abbot's Study", lines=(), facts=(card,))
        for _ in range(turns)
    )


def refused(draft: Game, verb: str, **fields: object) -> str:
    with pytest.raises(ValueError) as raised:
        _ = changed(draft, verb, **fields)
    return str(raised.value)


def test_reveal_moves_a_hidden_entity_into_the_scene_and_tells_the_player() -> None:
    _, state = initialized()
    draft = state.draft()
    traces = changed(draft, "reveal", entity_id=MAP)
    assert MAP in draft.world.current.present
    assert MAP not in draft.world.current.hidden
    assert draft.world.require(MAP).known
    assert "the vault map" in traces[0]
    _ = draft.committed()


def test_only_what_is_hidden_here_can_be_revealed() -> None:
    _, state = initialized()
    assert "not hidden here" in refused(state.draft(), "reveal", entity_id=MARA)


def test_an_item_is_carried_by_its_holder_and_here_by_the_scene() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "reveal", entity_id=MAP)
    _ = changed(draft, "move_item", item_id=MAP, to="player")
    assert draft.world.require(MAP).carried_by == PLAYER_ID
    _ = changed(draft, "move_item", item_id=MAP, to="scene")
    # Dropping clears the holder and leaves the item lying here.
    assert draft.world.require(MAP).carried_by is None
    assert MAP in draft.world.current.present


def test_an_actor_who_is_not_here_cannot_be_acted_on() -> None:
    _, state = initialized()
    assert "not here" in refused(state.draft(), "kill", actor_id=TOMAS)


def test_a_death_drops_what_it_carried_and_ends_companionship() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "reveal", entity_id=MAP)
    _ = changed(draft, "move_item", item_id=MAP, to=MARA)
    _ = changed(draft, "join_party", actor_id=MARA)
    _ = changed(draft, "kill", actor_id=MARA)
    assert draft.world.require(MARA).trait("dead") is not None
    assert draft.world.require(MAP).carried_by is None
    assert MARA not in draft.world.companions
    _ = draft.committed()


def test_a_scene_that_settled_says_so() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "advance_thread", thread_id="vault-seal", status="resolved")
    assert draft.world.spent
    assert scene_spent(draft) == draft.world.spent


def test_a_scene_with_nothing_left_to_find_is_spent() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "reveal", entity_id=MAP)
    assert scene_spent(draft) == "everything here has been found"


def test_a_scene_nobody_ends_is_ended_by_the_cap() -> None:
    _, state = initialized()
    quiet = updated(state, turn=QUIET_TURNS)
    assert scene_spent(quiet) == f"nothing landed for {QUIET_TURNS} turns"
    assert scene_spent(updated(state, turn=SCENE_TURN_CAP)) is not None
    assert scene_spent(state) is None


def _next_scene(
    present: tuple[str, ...] = (MARA,), hidden: tuple[str, ...] = (TOMAS,)
) -> SceneDraft[LonerSheet]:
    return SceneDraft[LonerSheet](
        place="cloister",
        title="The Cloister",
        situation=SITUATION,
        present=present,
        hidden=hidden,
    )


def test_the_player_and_what_the_party_carries_follow_into_the_next_scene() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "reveal", entity_id=MAP)
    _ = changed(draft, "move_item", item_id=MAP, to="player")
    apply_scene(draft.world, _next_scene(), turn=4)
    here = draft.world.current.present
    # The player is added by code and the map came with them; Mara stayed only because she is named.
    assert PLAYER_ID in here and MAP in here
    assert draft.world.opened_at == 4
    assert [one.id for one in draft.world.played] == ["study-1"]
    assert draft.world.spent == ""
    _ = draft.committed()


def test_an_id_the_worldsmith_got_wrong_resolves_by_name_before_it_is_refused() -> None:
    _, state = initialized()
    draft = state.draft()
    # The probe's failure: the worldsmith writes a display name where an exact id was asked for.
    apply_scene(draft.world, _next_scene(present=("Mara",)), turn=1)
    assert draft.world.current.present == (PLAYER_ID, MARA)
    with pytest.raises(ValueError, match="no such id or name"):
        apply_scene(state.draft().world, _next_scene(present=(EntityId("nobody"),)), turn=1)


def test_the_scene_bar_names_what_a_thin_scene_is_missing() -> None:
    _, state = initialized()
    thin = SceneDraft[LonerSheet](place="nowhere", title="Nowhere", situation="x" * MIN_SITUATION)
    assert scene_refusal(thin, state.world) == (
        "the scene needs at least one cast member besides the player; "
        "at least one hidden entity — something to find; "
        "at least one existing cast member brought back"
    )
    assert scene_refusal(_next_scene(), state.world) is None


def test_an_entity_is_never_lost_when_a_scene_leaves_it_behind() -> None:
    _, state = initialized()
    draft = state.draft()
    apply_scene(draft.world, _next_scene(), turn=1)
    assert draft.world.last_seen(MAP) == "The Abbot's Study"
    assert MAP in draft.world.cast


def test_a_sheet_survives_the_save_whole() -> None:
    _, state = initialized()
    back = Game.model_validate_json(state.model_dump_json())
    sheet = back.world.player.sheet
    assert isinstance(sheet, ActorSheet)
    assert sheet.concept == "A Wary Relic-Hunter"
    assert back.model_dump_json() == state.model_dump_json()


def test_the_cast_may_not_name_someone_it_does_not_hold() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.world.current = draft.world.current.model_copy(update={"present": ("ghost",)})
    with pytest.raises(ValueError, match="not in the cast"):
        _ = draft.committed()


def test_an_improvised_item_lands_in_the_players_hands() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "improvise_item", name="a handful of gravel")
    made = draft.world.require(EntityId("a-handful-of-gravel"))
    assert made.carried_by == PLAYER_ID and made.known
    _ = draft.committed()


def test_an_entity_the_scene_hides_is_one_the_player_has_not_met() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.world.cast[MAP] = Entity[LonerSheet](
        id=MAP, kind="item", name="the vault map", brief="a chart", known=True
    )
    with pytest.raises(ValueError, match="already met"):
        _ = draft.committed()


def test_what_the_dead_carried_is_left_where_they_fell() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.world.cast[RING] = Entity[LonerSheet](
        id=RING, kind="item", name="a signet ring", brief="a ring", known=True, carried_by=MARA
    )
    _ = changed(draft, "kill", actor_id=MARA)
    # The trace says the ring fell loose here, so a later turn has to be able to pick it up.
    assert RING in draft.world.current.present
    assert changed(draft, "move_item", item_id=RING, to="player")
    _ = draft.committed()


def test_a_corpse_takes_no_further_part() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "kill", actor_id=MARA)
    assert "dead" in refused(draft, "add_trait", entity_id=MARA, name="Bleeding Out", text="x")
    assert "dead" in refused(draft, "remove_trait", entity_id=MARA, trait_id="dead")


def test_someone_who_is_not_here_takes_no_trait() -> None:
    _, state = initialized()
    assert "not here" in refused(state.draft(), "add_trait", entity_id=TOMAS, name="Weary", text="")


def test_a_move_that_changes_nothing_is_refused_rather_than_carded() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "reveal", entity_id=MAP)
    assert "already lying here" in refused(draft, "move_item", item_id=MAP, to="scene")
    _ = changed(draft, "move_item", item_id=MAP, to="player")
    assert "already held by player" in refused(draft, "move_item", item_id=MAP, to="player")


def test_a_companion_stops_travelling_and_a_stranger_never_started() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "join_party", actor_id=MARA)
    assert changed(draft, "leave_party", actor_id=MARA)
    assert MARA not in draft.world.companions
    assert "does not travel" in refused(draft, "leave_party", actor_id=MARA)


def test_a_trait_that_was_never_there_cannot_be_removed() -> None:
    _, state = initialized()
    refusal = refused(state.draft(), "remove_trait", entity_id=MARA, trait_id="brave")
    assert "carries no trait 'brave'" in refusal


def test_an_improvised_item_never_takes_an_id_the_cast_already_holds() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "improvise_item", name="Mara")
    assert MARA in draft.world.cast and EntityId("mara-2") in draft.world.cast


def test_a_fact_about_someone_unmet_reaches_neither_player_nor_narrator() -> None:
    _, state = initialized()
    draft = state.draft()
    # Here, but not yet found: a trait on it must not put its name in front of the player.
    draft.world.current = draft.world.current.model_copy(
        update={"hidden": (), "present": (*draft.world.current.present, MAP)}
    )
    landed = changed_facts(draft, "add_trait", entity_id=MAP, name="Torn", text="")
    assert landed and not any(fact.told for fact in landed)
    assert not cards(landed)


def test_the_player_is_in_every_scene_and_never_hidden_in_one() -> None:
    _, state = initialized()
    draft = state.draft()
    apply_scene(draft.world, _next_scene(present=("kael",), hidden=("Kael", TOMAS)), turn=1)
    assert PLAYER_ID in draft.world.current.present
    assert PLAYER_ID not in draft.world.current.hidden
    _ = draft.committed()


def test_a_scene_that_hides_someone_already_met_is_refused_whole() -> None:
    _, state = initialized()
    draft = state.draft()
    with pytest.raises(ValueError, match="already met"):
        apply_scene(draft.world, _next_scene(present=(), hidden=(MARA,)), turn=1)
    # Refused before the first write: the world still stands in the scene it was in.
    assert draft.world.current.id == "study-1"
    assert draft.world.played == ()


def test_what_a_companion_carries_follows_without_being_revealed() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "join_party", actor_id=MARA)
    draft.world.cast[RING] = Entity[LonerSheet](
        id=RING, kind="item", name="a signet ring", brief="a ring", carried_by=MARA
    )
    apply_scene(draft.world, _next_scene(present=()), turn=1)
    assert RING in draft.world.current.present
    assert not draft.world.require(RING).known


def test_the_scene_bar_will_not_deadlock_once_every_thread_resolves() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "advance_thread", thread_id="vault-seal", status="resolved")
    opened = _next_scene()
    refusal = scene_refusal(opened, draft.world)
    assert refusal is not None
    assert "at least one standing thread, opened here or already running" in refusal
    # The worldsmith opens a thread in the same draft, which is the way out.
    with_thread = opened.model_copy(
        update={"threads": {"the-stair": Thread(id="the-stair", title="What waits below")}}
    )
    assert scene_refusal(with_thread, draft.world) is None


def test_a_save_and_its_payload_agree_on_which_rules_they_play() -> None:
    _, state = initialized()
    raw = state.model_dump(mode="json") | {"engine": "retired"}
    with pytest.raises(ValueError, match="carries a 'loner3e' payload"):
        _ = Game.model_validate(raw)


def test_the_turn_cap_ends_a_scene_that_kept_landing_things() -> None:
    _, state = initialized()
    busy = updated(state, turn=SCENE_TURN_CAP, history=_carded(SCENE_TURN_CAP))
    assert scene_spent(busy) == f"{SCENE_TURN_CAP} turns have passed here"
