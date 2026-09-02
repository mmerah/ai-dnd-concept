import pytest
from core_test_support import initialized

from aidm.core.entities import EntityId
from aidm.core.facts import Fact, cards
from aidm.core.play import Exchange
from aidm.engines.core import PLAYER_ID
from aidm.engines.loner3e.tools import ChangeWorld, apply_change
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eGame, LonerCharacter
from aidm.engines.loner3e.worldsmith import install_scene
from aidm.engines.scenes import (
    MIN_SITUATION,
    SCENE_TURN_CAP,
    SPENT_NOTE,
    SceneDraft,
    apply_scene,
    record_exchange,
    scene_refusal,
)

MAP = EntityId("vault-map")
MARA = EntityId("mara")
TOMAS = EntityId("tomas")

SITUATION = (
    "A frost-rimed colonnade around a dead garden, and the way down is somewhere under it. "
    "Nothing here has been swept in a long while."
)


def changed_facts(draft: Loner3eGame, verb: str, **fields: object) -> list[Fact]:
    change = ChangeWorld.model_validate({"change": {"verb": verb, **fields}})
    return apply_change(draft.payload.world, change.change)


def changed(draft: Loner3eGame, verb: str, **fields: object) -> list[str]:
    return [fact.trace for fact in changed_facts(draft, verb, **fields)]


def _carded(turns: int) -> tuple[Exchange, ...]:
    """Turns that each landed something, so only the cap can end the scene."""
    card = Fact(kind="tags_changed", trace="something happened", told=True, card="Something")
    return tuple(Exchange(prompt="I press on.", lines=(), facts=(card,)) for _ in range(turns))


def refused(draft: Loner3eGame, verb: str, **fields: object) -> str:
    with pytest.raises(ValueError) as raised:
        _ = changed(draft, verb, **fields)
    return str(raised.value)


def test_reveal_moves_a_hidden_entity_into_the_scene_and_tells_the_player() -> None:
    _, state = initialized()
    draft = state.draft()
    traces = changed(draft, "reveal", entity_id=MAP)
    assert MAP in draft.payload.world.run.present
    assert MAP not in draft.payload.world.run.hidden
    assert draft.payload.world.require(MAP).known
    assert "the vault map" in traces[0]
    _ = draft.committed()


def test_only_what_is_hidden_here_can_be_revealed() -> None:
    _, state = initialized()
    assert "not hidden here" in refused(state.draft(), "reveal", entity_id=MARA)


def test_an_actor_who_is_not_here_cannot_be_acted_on() -> None:
    _, state = initialized()
    assert "not here" in refused(state.draft(), "kill", entity_id=TOMAS)


def test_finding_everything_here_does_not_end_the_scene() -> None:
    """`hidden` is content, not a clock: the scene's own question is what ends it."""
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "reveal", entity_id=MAP)
    assert not draft.payload.world.run.hidden
    draft.payload.world.run.exchanges.append(Exchange(prompt="I look around.", lines=()))
    assert _spent(draft) == ()


def test_a_scene_nobody_ends_is_ended_by_the_cap() -> None:
    _, state = initialized()
    draft = state.draft()
    idle = Exchange(prompt="I wait.", lines=())
    draft.payload.world.run.exchanges = [idle for _ in range(SCENE_TURN_CAP - 1)]
    assert _spent(draft) != ()
    assert not state.payload.world.run.exchanges  # the draft's turns never reached the state


def _next_scene(
    present: tuple[str, ...] = (MARA,), hidden: tuple[str, ...] = (TOMAS,)
) -> SceneDraft[LonerCharacter]:
    return SceneDraft[LonerCharacter](
        place="cloister",
        title="The Cloister",
        question="Does the cloister walk still reach the stair?",
        situation=SITUATION,
        present=present,
        hidden=hidden,
    )


def test_the_party_follows_into_the_next_scene() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "join_party", entity_id=MARA)
    apply_scene(draft.payload.world, _next_scene(present=()))
    here = draft.payload.world.run.present
    # Mara comes along because she travels with the player; the player is never listed.
    assert MARA in here and PLAYER_ID not in here
    assert [run.scene.place for run in draft.payload.world.runs[:-1]] == ["abbots-study"]
    assert draft.payload.world.run.spent == ""
    _ = draft.committed()


def test_someone_left_behind_is_refilled_when_the_scene_moves_on() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.world.require(MARA).luck.current = LUCK_MAX - 2

    facts = install_scene(draft, _next_scene(present=(), hidden=(TOMAS,)))

    assert MARA not in draft.payload.world.party
    assert draft.payload.world.require(MARA).luck.current == LUCK_MAX
    assert any(fact.kind == "counter_changed" for fact in facts)


def test_an_id_the_worldsmith_got_wrong_resolves_by_name_before_it_is_refused() -> None:
    _, state = initialized()
    draft = state.draft()
    # The probe's failure: the worldsmith writes a display name where an exact id was asked for.
    apply_scene(draft.payload.world, _next_scene(present=("Mara",)))
    assert draft.payload.world.run.present == [MARA]
    with pytest.raises(ValueError, match="these name nobody"):
        apply_scene(state.draft().payload.world, _next_scene(present=(EntityId("nobody"),)))


def test_a_situation_that_names_what_it_hides_is_refused() -> None:
    """`situation` is read to the player, so it must not hand them the find."""
    _, state = initialized()
    told = _next_scene()
    hidden_name = state.payload.world.require(EntityId(TOMAS)).name
    told = told.model_copy(update={"situation": f"{SITUATION} {hidden_name} waits in the dark."})

    assert scene_refusal(told, state.payload.world) == (
        f"the scene needs a situation that does not name what is hidden: ['{hidden_name}']"
    )


def test_a_one_word_name_is_a_word_the_situation_may_use() -> None:
    """A prop called `Bell` shares its word with any bell tower; refusing that costs a crossing."""
    _, state = initialized()
    draft = state.draft()
    draft.payload.world.require(EntityId(TOMAS)).name = "Bell"
    told = _next_scene()
    told = told.model_copy(update={"situation": f"{SITUATION} The bell tower stands over it."})

    assert scene_refusal(told, draft.payload.world) is None


def test_the_scene_bar_names_what_a_thin_scene_is_missing() -> None:
    _, state = initialized()
    thin = SceneDraft[LonerCharacter](
        place="nowhere",
        title="Nowhere",
        question="Is there anything here at all?",
        situation="x" * MIN_SITUATION,
    )
    assert scene_refusal(thin, state.payload.world) == (
        "the scene needs at least one cast member besides the player; "
        "at least one existing cast member brought back"
    )
    assert scene_refusal(_next_scene(), state.payload.world) is None

    ghost = EntityId("ghost")
    broken = _next_scene().model_copy(
        update={"cast": {ghost: LonerCharacter(id=ghost, name="Ghost", brief="", alive=False)}}
    )
    assert scene_refusal(broken, state.payload.world) == (
        "the scene needs cast members as the worldsmith may write them: ['ghost: alive']"
    )


def test_an_entity_is_never_lost_when_a_scene_leaves_it_behind() -> None:
    _, state = initialized()
    draft = state.draft()
    apply_scene(draft.payload.world, _next_scene())
    assert draft.payload.world.last_seen(MAP) == "last seen in: The Abbot's Study"
    assert MAP in draft.payload.world.cast


def test_a_characters_tags_survive_the_save_whole() -> None:
    _, state = initialized()
    back = Loner3eGame.model_validate_json(state.model_dump_json())
    player = back.payload.world.player
    assert player.concept == "A Wary Relic-Hunter"
    assert back.model_dump_json() == state.model_dump_json()


def test_the_cast_may_not_name_someone_it_does_not_hold() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.world.run.present = [EntityId("ghost")]
    with pytest.raises(ValueError, match="not in the cast"):
        _ = draft.committed()


def test_an_entity_the_scene_hides_is_one_the_player_has_not_met() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.world.cast[MAP] = LonerCharacter(
        id=MAP, name="the vault map", brief="a chart", known=True
    )
    with pytest.raises(ValueError, match="already met"):
        _ = draft.committed()


def test_a_corpse_takes_no_further_part() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "kill", entity_id=MARA)
    assert not draft.payload.world.require(MARA).alive
    assert "dead" in refused(draft, "drive", entity_id=MARA, goal="Survive")


def test_the_players_death_cards_you_are_dead() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = changed_facts(draft, "kill", entity_id=PLAYER_ID)
    assert [fact.card for fact in facts if fact.card] == ["You are dead"]
    assert not draft.payload.world.player.alive


def test_a_companion_stops_travelling_and_a_stranger_never_started() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "join_party", entity_id=MARA)
    assert changed(draft, "leave_party", entity_id=MARA)
    assert MARA not in draft.payload.world.party
    assert "does not travel" in refused(draft, "leave_party", entity_id=MARA)


def test_a_fact_about_someone_unmet_reaches_neither_player_nor_narrator() -> None:
    _, state = initialized()
    draft = state.draft()
    # Here, but not yet found: a tag change on it must not put its name in front of the player.
    run = draft.payload.world.run
    run.hidden = []
    run.present = [*run.present, MAP]
    landed = changed_facts(draft, "change_tags", entity_id=MAP, kind="condition", gained=["Torn"])
    assert landed and not any(fact.told for fact in landed)
    assert not cards(landed)


def test_the_player_is_in_every_scene_and_is_never_listed_in_one() -> None:
    _, state = initialized()
    draft = state.draft()
    with pytest.raises(ValueError, match="put there by code"):
        apply_scene(draft.payload.world, _next_scene(present=("kael",), hidden=("Kael", TOMAS)))


def test_a_scene_that_hides_someone_already_met_is_refused_whole() -> None:
    _, state = initialized()
    draft = state.draft()
    with pytest.raises(ValueError, match="already met"):
        apply_scene(draft.payload.world, _next_scene(present=(), hidden=(MARA,)))
    # Refused before the first write: the world still stands in the scene it was in.
    assert draft.payload.world.current.place == "abbots-study"
    assert draft.payload.world.runs[:-1] == []


def test_the_turn_cap_ends_a_scene_that_kept_landing_things() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.world.run.exchanges = list(_carded(SCENE_TURN_CAP - 1))
    assert _spent(draft) == (SPENT_NOTE.format(reason=f"{SCENE_TURN_CAP} turns have passed here"),)


def test_change_tags_edits_one_list_and_refuses_what_it_cannot_move() -> None:
    _, state = initialized()
    draft = state.draft()

    assert "at least one" in refused(draft, "change_tags", entity_id=PLAYER_ID, kind="gear")

    traces = changed(draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rusty Key"])
    assert "Rusty Key" in draft.payload.world.player.gear
    assert traces[0].endswith("gear +Rusty Key")

    assert "already carries" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rusty Key"]
    )

    traces = changed(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", gained=["Listening"]
    )
    assert "Listening" in draft.payload.world.player.conditions
    assert traces[0].endswith("condition +Listening")

    traces = changed(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", lost=["Listening"]
    )
    assert "Listening" not in draft.payload.world.player.conditions
    assert traces[0].endswith("condition -Listening")

    assert "carries no condition" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", lost=["Listening"]
    )

    assert "duplicate" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rope", "Rope"]
    )

    _ = changed(draft, "kill", entity_id=MARA)
    assert "dead" in refused(draft, "change_tags", entity_id=MARA, kind="gear", gained=["Rope"])
    _ = draft.committed()


def test_drive_writes_what_play_revealed() -> None:
    _, state = initialized()
    draft = state.draft()

    traces = changed(draft, "drive", entity_id=PLAYER_ID, goal="Get the vault map out alive")
    assert draft.payload.world.player.goal == "Get the vault map out alive"
    assert "goal: Get the vault map out alive" in traces[0]

    assert "goal, a motive or a nemesis" in refused(draft, "drive", entity_id=PLAYER_ID)

    _ = changed(draft, "kill", entity_id=MARA)
    assert "dead" in refused(draft, "drive", entity_id=MARA, motive="Survive")
    _ = draft.committed()


def _spent(draft: Loner3eGame) -> tuple[str, ...]:
    """One more turn here, and what the master is told about the scene looking finished."""
    world = draft.payload.world
    return record_exchange(
        world, "I wait.", (), (), "", someone_dead=any(not one.alive for one in world.here())
    )
