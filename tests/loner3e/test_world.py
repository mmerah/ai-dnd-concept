from pydantic import JsonValue
from support.game import ENGINE, MARA, SITUATION, initialized
from support.table import change
from support.table import refused as change_refused

from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import LUCK_MAX, TIES_PER_TWIST, Loner3eCast, Loner3eGame
from aidm.engines.scenes.tools import SceneDraft

TOMAS = "tomas"


def changed(draft: Loner3eGame, name: str, **fields: JsonValue) -> list[str]:
    return [fact.trace for fact in change(ENGINE, draft, name, **fields)]


def refused(draft: Loner3eGame, name: str, **fields: JsonValue) -> str:
    return change_refused(ENGINE, draft, name, **fields)


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


def test_someone_left_behind_is_refilled_when_the_scene_moves_on() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.require(MARA).luck.current = LUCK_MAX - 2

    _ = ENGINE.leaving(draft)
    _ = ENGINE.install(draft, _next_scene(present=(), hidden=(TOMAS,)))

    assert MARA not in draft.payload.party
    assert draft.payload.require(MARA).luck.current == LUCK_MAX


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


def test_tick_twist_turns_over_on_the_third_call_and_resets() -> None:
    _, state = initialized()
    draft = state.draft()

    assert draft.payload.tick_twist() is False
    assert draft.payload.twist.current == 1
    assert draft.payload.tick_twist() is False
    assert draft.payload.twist.current == TIES_PER_TWIST - 1
    assert draft.payload.tick_twist() is True
    assert draft.payload.twist.current == 0


def test_the_cast_lines_say_who_the_player_has_met() -> None:
    _, state = initialized()

    lines = state.payload.cast_lines().splitlines()

    assert any(line.strip() == "met; last seen in: The Abbot's Study" for line in lines)
    assert any(line.strip() == "unmet; last seen in: The Abbot's Study" for line in lines)
    assert any(line.strip() == "unmet" for line in lines)
    assert not lines[1].strip().startswith(("met", "unmet"))
