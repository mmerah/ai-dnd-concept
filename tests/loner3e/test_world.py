import pytest
from core_test_support import change, initialized
from core_test_support import refused as change_refused
from loner3e_test_support import ENGINE
from pydantic import JsonValue

from aidm.core.entities import EntityId
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eGame, Loner3eSheet
from aidm.engines.scenes.drafts import MIN_SITUATION, SceneDraft
from aidm.engines.scenes.worldsmith import scene_refusal

MAP = EntityId("vault-map")
MARA = EntityId("mara")
TOMAS = EntityId("tomas")

SITUATION = (
    "A frost-rimed colonnade around a dead garden, and the way down is somewhere under it. "
    "Nothing here has been swept in a long while."
)


def changed(draft: Loner3eGame, verb: str, **fields: JsonValue) -> list[str]:
    return [fact.trace for fact in change(ENGINE, draft, verb, **fields)]


def refused(draft: Loner3eGame, verb: str, **fields: JsonValue) -> str:
    return change_refused(ENGINE, draft, verb, **fields)


def test_reveal_moves_a_hidden_entity_into_the_scene_and_tells_the_player() -> None:
    _, state = initialized()
    draft = state.draft()
    traces = changed(draft, "reveal", entity_id=MAP)
    assert MAP in draft.payload.present()
    assert MAP not in draft.payload.hidden()
    assert draft.payload.require(MAP).known
    assert "the vault map" in traces[0]
    _ = draft.commit()


def test_only_what_is_hidden_here_can_be_revealed() -> None:
    _, state = initialized()
    assert "not hidden here" in refused(state.draft(), "reveal", entity_id=MARA)


def test_an_actor_who_is_not_here_cannot_be_acted_on() -> None:
    _, state = initialized()
    assert "not here" in refused(state.draft(), "kill", entity_id=TOMAS)


def test_someone_hidden_here_cannot_be_acted_on_before_the_reveal() -> None:
    # Here, but not yet found: the refusal is what keeps its name from the player and narrator.
    _, state = initialized()
    draft = state.draft()
    assert MAP in draft.payload.hidden()
    assert "not here" in refused(
        draft, "change_tags", entity_id=MAP, kind="condition", gained=["Torn"]
    )


def _next_scene(
    present: tuple[str, ...] = (MARA,), hidden: tuple[str, ...] = (TOMAS,)
) -> SceneDraft[Loner3eSheet]:
    return SceneDraft[Loner3eSheet](
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
    draft.payload.apply_scene(_next_scene(present=()))
    here = draft.payload.present()
    # Mara comes along because she travels with the player; the player is never listed.
    assert MARA in here and PLAYER_ID not in here
    assert [run.place for run in draft.payload.runs[:-1]] == ["abbots-study"]
    _ = draft.commit()


def test_someone_left_behind_is_refilled_when_the_scene_moves_on() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.require(MARA).luck.current = LUCK_MAX - 2

    facts = (
        *ENGINE.leaving(draft),
        *ENGINE.install(draft, _next_scene(present=(), hidden=(TOMAS,))),
    )

    assert MARA not in draft.payload.party
    assert draft.payload.require(MARA).luck.current == LUCK_MAX
    assert any(fact.kind == "counter_changed" for fact in facts)


def test_an_id_the_worldsmith_got_wrong_resolves_by_name_before_it_is_refused() -> None:
    _, state = initialized()
    draft = state.draft()
    # The probe's failure: the worldsmith writes a display name where an exact id was asked for.
    draft.payload.apply_scene(_next_scene(present=("Mara",)))
    assert draft.payload.present() == [MARA]
    with pytest.raises(ValueError, match="no such id or name exists"):
        state.draft().payload.apply_scene(_next_scene(present=(EntityId("nobody"),)))


def test_a_situation_that_names_what_it_hides_is_refused() -> None:
    """`situation` is read to the player, so it must not hand them the find."""
    _, state = initialized()
    told = _next_scene()
    hidden_name = state.payload.require(EntityId(TOMAS)).name
    told = told.model_copy(update={"situation": f"{SITUATION} {hidden_name} waits in the dark."})

    assert scene_refusal(told, state.payload) == (
        f"the scene needs a situation that does not name what is hidden: ['{hidden_name}']"
    )


def test_a_one_word_name_is_a_word_the_situation_may_use() -> None:
    """A prop called `Bell` shares its word with any bell tower; refusing that costs a crossing."""
    _, state = initialized()
    draft = state.draft()
    draft.payload.require(EntityId(TOMAS)).name = "Bell"
    told = _next_scene()
    told = told.model_copy(update={"situation": f"{SITUATION} The bell tower stands over it."})

    assert scene_refusal(told, draft.payload) is None


def test_the_scene_bar_names_what_a_thin_scene_is_missing() -> None:
    _, state = initialized()
    thin = SceneDraft[Loner3eSheet](
        place="nowhere",
        title="Nowhere",
        question="Is there anything here at all?",
        situation="x" * MIN_SITUATION,
    )
    assert scene_refusal(thin, state.payload) == (
        "the scene needs at least one cast member besides the player; "
        "at least one existing cast member brought back"
    )
    assert scene_refusal(_next_scene(), state.payload) is None

    ghost = EntityId("ghost")
    broken = _next_scene().model_copy(
        update={"cast": {ghost: Loner3eSheet(id=ghost, name="Ghost", brief="", alive=False)}}
    )
    assert scene_refusal(broken, state.payload) == (
        "the scene needs cast members as the worldsmith may write them: ['ghost: alive']"
    )


def test_an_entity_is_never_lost_when_a_scene_leaves_it_behind() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.apply_scene(_next_scene())
    assert draft.payload.last_seen(MAP) == "last seen in: The Abbot's Study"
    assert MAP in draft.payload.cast


def test_a_characters_tags_survive_the_save_whole() -> None:
    _, state = initialized()
    back = Loner3eGame.model_validate_json(state.model_dump_json())
    player = back.payload.player
    assert player.concept == "A Wary Relic-Hunter"
    assert back.model_dump_json() == state.model_dump_json()


def test_the_cast_may_not_name_someone_it_does_not_hold() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.run.here = [EntityId("ghost")]
    with pytest.raises(ValueError, match="not in the cast"):
        _ = draft.commit()


def test_a_corpse_takes_no_further_part() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "kill", entity_id=MARA)
    assert not draft.payload.require(MARA).alive
    assert "dead" in refused(draft, "drive", entity_id=MARA, goal="Survive")


def test_the_players_death_cards_you_are_dead() -> None:
    _, state = initialized()
    draft = state.draft()
    facts = change(ENGINE, draft, "kill", entity_id=PLAYER_ID)
    assert [fact.card for fact in facts if fact.card] == ["You are dead"]
    assert not draft.payload.player.alive


def test_a_companion_stops_travelling_and_a_stranger_never_started() -> None:
    _, state = initialized()
    draft = state.draft()
    _ = changed(draft, "join_party", entity_id=MARA)
    assert changed(draft, "leave_party", entity_id=MARA)
    assert MARA not in draft.payload.party
    assert "does not travel" in refused(draft, "leave_party", entity_id=MARA)


def test_the_player_is_in_every_scene_and_is_never_listed_in_one() -> None:
    _, state = initialized()
    draft = state.draft()
    scene = _next_scene(present=("kael",), hidden=("Kael", TOMAS))
    assert "put there by code" in (scene_refusal(scene, draft.payload) or "")


def test_a_scene_that_hides_someone_already_met_is_refused_whole() -> None:
    _, state = initialized()
    draft = state.draft()
    scene = _next_scene(present=(), hidden=(MARA,))
    assert "already met" in (scene_refusal(scene, draft.payload) or "")


def test_change_tags_edits_one_list_and_refuses_what_it_cannot_move() -> None:
    _, state = initialized()
    draft = state.draft()

    assert "at least one" in refused(draft, "change_tags", entity_id=PLAYER_ID, kind="gear")

    traces = changed(draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rusty Key"])
    assert "Rusty Key" in draft.payload.player.gear
    assert traces[0].endswith("gear +Rusty Key")

    assert "already carries" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rusty Key"]
    )

    traces = changed(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", gained=["Listening"]
    )
    assert "Listening" in draft.payload.player.conditions
    assert traces[0].endswith("condition +Listening")

    traces = changed(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", lost=["Listening"]
    )
    assert "Listening" not in draft.payload.player.conditions
    assert traces[0].endswith("condition -Listening")

    assert "carries no condition" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", lost=["Listening"]
    )

    assert "duplicate" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rope", "Rope"]
    )

    _ = changed(draft, "kill", entity_id=MARA)
    assert "dead" in refused(draft, "change_tags", entity_id=MARA, kind="gear", gained=["Rope"])
    _ = draft.commit()


def test_drive_writes_what_play_revealed() -> None:
    _, state = initialized()
    draft = state.draft()

    traces = changed(draft, "drive", entity_id=PLAYER_ID, goal="Get the vault map out alive")
    assert draft.payload.player.goal == "Get the vault map out alive"
    assert "goal: Get the vault map out alive" in traces[0]

    assert "goal, a motive or a nemesis" in refused(draft, "drive", entity_id=PLAYER_ID)

    _ = changed(draft, "kill", entity_id=MARA)
    assert "dead" in refused(draft, "drive", entity_id=MARA, motive="Survive")
    _ = draft.commit()
