from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    changed,
    initialized,
    narrated,
    opened,
    played,
    tool_call,
)

from aidm.core.entities import EntityId
from aidm.core.facts import Fact, cards
from aidm.core.model import AnyGame
from aidm.engines.core import PLAYER_ID
from aidm.engines.loner3e.tools import outcome_for
from aidm.turn.run import Turn

MAP = EntityId("vault-map")
FOUND = changed("reveal", entity_id="vault-map")
TAKEN = changed("change_tags", entity_id=PLAYER_ID, kind="gear", gained=["the vault map"])
ASKED = tool_call("roll_question", actor_id=PLAYER_ID, question="Does the door give?")


async def test_a_turn_runs_the_master_then_the_narrator_on_a_safe_prompt(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(
        table,
        "I search beneath the desk.",
        FOUND,
        TAKEN,
        narration="A creased chart slides into your hand.",
    )

    assert [role for role, _ in table.spawner.prompts] == ["master", "narrator"]
    assert [fact.kind for fact in table.facts] == ["entity_discovered", "tags_changed"]
    assert "the vault map" in state.payload.player.gear
    narrator = table.spawner.prompt("narrator")
    assert "Elena" not in narrator
    # The sheets are the game master's: no tag the engine rolls by reaches the narrator.
    assert "concept" not in narrator
    assert state.turn == 1
    assert state.payload.exchanges()[-1].prompt == "I search beneath the desk."


async def test_the_turn_holds_its_facts_in_resolver_order(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(
        table,
        "I take the map and listen.",
        FOUND,
        TAKEN,
        changed("change_tags", entity_id="player", kind="condition", gained=["Listening"]),
    )

    landed = ["The vault map discovered", "Took the vault map", "Now: Listening"]
    assert [fact.card for fact in cards(table.facts)] == landed
    assert [fact.card for fact in state.payload.exchanges()[-1].facts] == landed


async def test_a_narrator_failure_leaves_the_committed_game_untouched(tmp_path: Path) -> None:
    table = opened(tmp_path)
    before = table.service.state.model_dump_json()
    table.spawner.turns.append(table.plays((FOUND, TAKEN)))

    with pytest.raises(ValueError, match="no answer left"):
        await table.service.play("I take the map.")

    assert table.service.state.model_dump_json() == before
    assert table.service.state.payload.exchanges() == ()


async def test_the_engine_rolls_the_outcome_the_facts_then_record(tmp_path: Path) -> None:
    table = opened(tmp_path, rng=Random(2))

    state = await played(
        table,
        "I plead with the door.",
        tool_call(
            "roll_question",
            actor_id="player",
            question="Does the door give before the whispering finds him?",
        ),
        narration="You falter.",
    )

    fired = table.facts
    answer = next(fact for fact in fired if fact.kind == "question_answered")
    chance, risk = answer.dice
    rolled = [fact.trace for fact in fired if fact.kind == "dice_rolled"]
    for die, trace in zip(answer.dice, rolled, strict=True):
        assert trace.endswith(f"[{', '.join(str(v) for v in die.rolled)}]")
    assert answer.card.endswith(f"→ {outcome_for(max(chance.rolled), max(risk.rolled)).name}")
    table.service.engine.validate(state)
    assert any(fact.kind == "dice_rolled" and not fact.told for fact in fired)


async def test_the_master_reacts_in_run_to_its_own_earlier_tool_call(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(
        table,
        "I call the old porter over.",
        changed("enter", entity_id="tomas"),
        changed("join_party", entity_id="tomas"),
    )

    assert state.payload.party == ["tomas"]


async def test_an_illegal_tool_call_is_refused_with_the_reason(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(table, "I wait.", changed("reveal", entity_id="nowhere"), FOUND)

    assert state.payload.require(MAP).known
    assert any("unknown id 'nowhere'" in one for one in table.refusals)


async def test_a_call_its_own_fields_refuse_does_not_kill_the_turn(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(
        table,
        "I press on.",
        changed("drive", entity_id=PLAYER_ID),
        changed("drive", entity_id=PLAYER_ID, goal="Find the way down."),
    )

    assert state.payload.player.goal == "Find the way down."
    assert any("goal, a motive or a nemesis" in one for one in table.refusals)


async def test_a_later_call_in_one_turn_sees_the_earlier_calls_draft(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)

    state = await played(
        table, "I close the book.", tool_call("next_scene"), tool_call("next_scene")
    )

    assert state.payload.run.left is not None
    assert any("already settled" in one for one in table.refusals)


async def test_a_line_spoken_by_someone_not_here_is_re_prompted_with_the_id(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["narrator"] = [
        narrated("You should not be here.", "elena"),
        narrated("The door settles."),
    ]
    table.spawner.turns.append(table.plays(()))

    await table.service.play("I wait.")

    assert any("elena" in prompt for role, prompt in table.spawner.prompts if role == "narrator")
    assert table.service.state.payload.exchanges()[-1].narration == "The door settles."


async def test_a_master_that_crashes_after_applying_still_commits_what_it_applied(
    tmp_path: Path,
) -> None:
    """The exit is the only end signal: what it legally applied is the turn."""
    table = opened(tmp_path)

    def crash() -> None:
        _ = table.call(*FOUND)
        raise OSError("the game master exploded")

    table.spawner.turns.append(crash)
    table.spawner.answers["narrator"] = [narrated("The map is in hand.")]

    await table.service.play("I take the map and read it.")

    assert table.service.state.turn == 1
    assert table.service.state.payload.require(MAP).known


async def test_a_master_that_crashed_after_a_tool_landed_is_not_spawned_again(
    tmp_path: Path,
) -> None:
    """A second spawn would replay the prompt and apply the same mutation twice."""
    table = opened(tmp_path)
    _ = await played(table, "I look around.")

    def crash() -> None:
        _ = table.call(*FOUND)
        raise OSError("the game master exploded")

    table.spawner.turns.append(crash)
    table.spawner.answers["narrator"] = [narrated("The map is in hand.")]
    spawned = len(table.spawner.prompts)

    await table.service.play("I take the map.")

    assert [role for role, _ in table.spawner.prompts[spawned:]].count("master") == 1


async def test_a_master_that_landed_nothing_is_spawned_once_more(tmp_path: Path) -> None:
    table = opened(tmp_path)
    _ = await played(table, "I look around.")

    def crash() -> None:
        raise OSError("the game master never started")

    table.spawner.turns += [crash, crash]
    spawned = len(table.spawner.prompts)

    with pytest.raises(OSError, match="never started"):
        await table.service.play("I take the map.")

    assert [session for role, session in table.spawner.resumed[spawned:] if role == "master"] == [
        None,
        None,
    ]


async def test_a_turn_that_applied_nothing_and_failed_is_refused(tmp_path: Path) -> None:
    table = opened(tmp_path)
    before = table.service.state.model_dump_json()

    def crash() -> None:
        raise OSError("the game master never started")

    table.spawner.turns += [crash, crash]

    with pytest.raises(OSError, match="never started"):
        await table.service.play("I take the map.")

    assert table.service.state.model_dump_json() == before


async def test_two_rolls_in_one_turn_do_not_read_the_same_dice(tmp_path: Path) -> None:
    table = opened(tmp_path, rng=Random(1))

    _ = await played(table, "I try the door twice.", ASKED, ASKED)

    first, second = (fact.dice for fact in table.facts if fact.kind == "question_answered")
    assert first != second


def test_a_refused_call_leaves_the_turn_the_dice_it_had() -> None:
    engine, state = initialized()
    turn = Turn.begin(engine, state, "I try the door.", Random(1))
    before = turn.rng.getstate()

    with pytest.raises(ValueError, match="the rules said no"):
        _ = turn.apply(_rolls_then_refuses)

    assert turn.rng.getstate() == before


def _rolls_then_refuses(draft: AnyGame, rng: Random) -> tuple[Fact, ...]:
    del draft
    _ = rng.random()
    raise ValueError("the rules said no")
