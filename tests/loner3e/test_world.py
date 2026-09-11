import pytest
from pydantic import JsonValue
from support.game import ENGINE, MAP, MARA, SITUATION, initialized
from support.table import change
from support.table import refused as change_refused

from aidm.core.entities import Refusal
from aidm.core.play import Exchange
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eCast, Loner3eGame
from aidm.engines.scenes.tools import NextDraft, SceneDraft
from aidm.engines.scenes.worldsmith import check_scene

TOMAS = "tomas"
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."


def changed(draft: Loner3eGame, name: str, **fields: JsonValue) -> list[str]:
    return [fact.trace for fact in change(ENGINE, draft, name, **fields)]


def refused(draft: Loner3eGame, name: str, **fields: JsonValue) -> str:
    return change_refused(ENGINE, draft, name, **fields)


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
) -> SceneDraft[Loner3eCast]:
    return SceneDraft[Loner3eCast](
        place="cloister",
        title="The Cloister",
        focus="Does the cloister walk still reach the stair?",
        situation=SITUATION,
        present=present,
        hidden=hidden,
        arc="Farther along, the stair still leads down to what Tomas would not speak of.",
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

    _ = ENGINE.leaving(draft)
    _ = ENGINE.install(draft, _next_scene(present=(), hidden=(TOMAS,)))

    assert MARA not in draft.payload.party
    assert draft.payload.require(MARA).luck.current == LUCK_MAX


def test_install_stamps_the_recap_on_the_chapter_left() -> None:
    _, state = initialized()
    draft = state.draft()
    # A chapter with no exchanges yet is dropped, not kept as the one left; give it one first.
    draft.log[-1].exchanges.append(Exchange(words="They wait.", lines=()))

    _ = ENGINE.install(draft, NextDraft[Loner3eCast](**_next_scene().model_dump(), recap=RECAP))

    assert draft.log[-2].recap == RECAP
    assert draft.log[-1].recap == ""


def test_an_id_the_worldsmith_got_wrong_resolves_by_name_before_it_is_refused() -> None:
    _, state = initialized()
    draft = state.draft()
    # The probe's failure: the worldsmith writes a display name where an exact id was asked for.
    draft.payload.apply_scene(_next_scene(present=("Mara",)))
    assert draft.payload.present() == [MARA]
    with pytest.raises(Refusal, match="no such id or name exists"):
        state.draft().payload.apply_scene(_next_scene(present=("nobody",)))


def test_a_one_word_name_is_a_word_the_situation_may_use() -> None:
    """A prop called `Bell` shares its word with any bell tower; refusing that costs a crossing."""
    _, state = initialized()
    draft = state.draft()
    draft.payload.require(TOMAS).name = "Bell"
    scene = _next_scene()
    scene = scene.model_copy(update={"situation": f"{SITUATION} The bell tower stands over it."})

    check_scene(scene, draft.payload)


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
    draft.payload.run.here = ["ghost"]
    with pytest.raises(Refusal, match="not in the cast"):
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


def test_change_tags_edits_one_list_and_refuses_what_it_cannot_move() -> None:
    _, state = initialized()
    draft = state.draft()

    assert "at least one" in refused(draft, "change_tags", entity_id=PLAYER_ID, kind="gear")

    traces = changed(draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rusty Key"])
    assert "Rusty Key" in draft.payload.player.tagged("gear")
    assert traces[0].endswith("gear +Rusty Key")

    assert "already carries" in refused(
        draft, "change_tags", entity_id=PLAYER_ID, kind="gear", gained=["Rusty Key"]
    )

    traces = changed(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", gained=["Listening"]
    )
    assert "Listening" in draft.payload.player.tagged("condition")
    assert traces[0].endswith("condition +Listening")

    traces = changed(
        draft, "change_tags", entity_id=PLAYER_ID, kind="condition", lost=["Listening"]
    )
    assert "Listening" not in draft.payload.player.tagged("condition")
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


def test_the_cast_lines_say_who_the_player_has_met() -> None:
    _, state = initialized()

    lines = state.payload.cast_lines().splitlines()

    assert any(line.strip() == "met; last seen in: The Abbot's Study" for line in lines)
    assert any(line.strip() == "unmet; last seen in: The Abbot's Study" for line in lines)
    assert any(line.strip() == "unmet" for line in lines)
    assert not lines[1].strip().startswith(("met", "unmet"))
