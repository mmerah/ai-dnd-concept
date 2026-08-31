from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    changed,
    loner_at_boundary,
    loner_sheet,
    narrated,
    opened,
    played,
    tool_call,
)
from pydantic import JsonValue

from aidm.core.entities import PLAYER_ID, EntityId
from aidm.core.facts import Fact, cards
from aidm.engines.loner3e.rules import outcome_for
from aidm.turn.run import TurnStep

MAP = EntityId("vault-map")
FOUND = changed("reveal", entity_id="vault-map")
TAKEN = changed("move_item", item_id="vault-map", to="player")


async def test_a_turn_runs_the_master_then_the_narrator_on_a_safe_prompt(tmp_path: Path) -> None:
    table = opened(tmp_path)
    steps: list[TurnStep] = []
    facts: list[Fact] = []

    state = await played(
        table,
        "I search beneath the desk.",
        FOUND,
        TAKEN,
        narration="A creased chart slides into your hand.",
        on_step=steps.append,
        on_fact=facts.append,
    )

    assert tuple(steps) == ("master", "narrator")
    assert [fact.kind for fact in facts] == ["entity_discovered", "entity_moved"]
    assert {one.id for one in state.world.carried_by(PLAYER_ID)} == {"vault-map"}
    narrator = table.spawner.prompt("narrator")
    assert "Elena" not in narrator
    # The sheets are the game master's: no tag the engine rolls by reaches the narrator.
    assert "concept" not in narrator
    assert state.turn == 1
    assert state.history[-1].prompt == "I search beneath the desk."


async def test_on_fact_reports_the_visible_facts_in_resolver_order(tmp_path: Path) -> None:
    table = opened(tmp_path)
    fired: list[Fact] = []

    state = await played(
        table,
        "I take the map and listen.",
        FOUND,
        TAKEN,
        changed("add_trait", entity_id="player", name="Listening", text="listening"),
        on_fact=fired.append,
    )

    landed = ["The vault map discovered", "Took the vault map", "Kael: new trait Listening"]
    assert [fact.card for fact in cards(fired)] == landed
    assert [fact.card for fact in state.history[-1].facts] == landed


async def test_a_narrator_failure_leaves_the_committed_game_untouched(tmp_path: Path) -> None:
    table = opened(tmp_path)
    before = table.service.state.model_dump_json()
    table.spawner.turns.append(table.plays((FOUND, TAKEN)))

    with pytest.raises(ValueError, match="no answer left"):
        await table.service.play("I take the map.")

    assert table.service.state.model_dump_json() == before
    assert table.service.state.history == ()


async def test_the_engine_rolls_the_outcome_the_facts_then_record(tmp_path: Path) -> None:
    table = opened(tmp_path, rng=Random(2))
    fired: list[Fact] = []

    state = await played(
        table,
        "I plead with the door.",
        tool_call(
            "roll_question",
            actor_id="player",
            question="Does the door give before the whispering finds him?",
        ),
        narration="You falter.",
        on_fact=fired.append,
    )

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
        changed("join_party", actor_id="tomas"),
    )

    assert state.world.companions == ["tomas"]


async def test_an_illegal_tool_call_is_refused_with_the_reason(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(table, "I wait.", changed("reveal", entity_id="nowhere"), FOUND)

    assert state.world.require(MAP).known
    assert any("unknown id 'nowhere'" in one for one in table.refusals)


async def test_a_call_its_own_fields_refuse_does_not_kill_the_turn(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(
        table,
        "I press on.",
        changed("advance_thread", thread_id="vault-seal"),
        changed("advance_thread", thread_id="vault-seal", note="The seal is found."),
    )

    assert state.world.threads["vault-seal"].note == "The seal is found."
    assert any("status or its note" in one for one in table.refusals)


async def test_a_later_call_is_judged_against_the_sheet_the_earlier_one_moved(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    growth: dict[str, JsonValue] = {
        "subject_id": PLAYER_ID,
        "changes": [{"kind": "skill", "tag": "Vault-Wise", "why": "the seal gave up its trick"}],
    }

    state = await played(
        table,
        "I close the book.",
        tool_call("complete_chapter"),
        tool_call("advance", **growth),
        tool_call("advance", **growth),
    )

    assert loner_sheet(state, PLAYER_ID).milestones == 1
    assert any("no advance owed" in one for one in table.refusals)


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
    assert table.service.state.history[-1].narration == "The door settles."


async def test_a_master_that_crashes_after_applying_still_commits_what_it_applied(
    tmp_path: Path,
) -> None:
    """The exit is the only end signal: what it legally applied is the turn."""
    table = opened(tmp_path)

    def crash() -> None:
        _ = table.call("start_turn", {})
        _ = table.call(*FOUND)
        raise OSError("the game master exploded")

    table.spawner.turns.append(crash)
    table.spawner.answers["narrator"] = [narrated("The map is in hand.")]

    await table.service.play("I take the map and read it.")

    assert table.service.state.turn == 1
    assert table.service.state.world.require(MAP).known


async def test_a_turn_that_applied_nothing_and_failed_is_refused(tmp_path: Path) -> None:
    table = opened(tmp_path)
    before = table.service.state.model_dump_json()

    def crash() -> None:
        raise OSError("the game master never started")

    table.spawner.turns.append(crash)

    with pytest.raises(OSError, match="never started"):
        await table.service.play("I take the map.")

    assert table.service.state.model_dump_json() == before


async def test_an_owed_advance_is_noted_lands_on_call_and_is_refused_once_spent(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.service.commit(loner_at_boundary(table.service.state))
    growth: dict[str, JsonValue] = {
        "subject_id": PLAYER_ID,
        "changes": [{"kind": "gear", "tag": "Waxed Rope", "why": "he never climbs without it now"}],
    }
    facts: list[Fact] = []

    state = await played(
        table,
        "I keep the rope.",
        tool_call("advance", **growth),
        tool_call("advance", **growth),
        on_fact=facts.append,
    )

    assert "Kael has an advance owed" in table.answers[0]
    assert len(cards(tuple(facts))) == 2
    sheet = loner_sheet(state, PLAYER_ID)
    assert (sheet.gear[-1], sheet.milestones) == ("Waxed Rope", 1)
    assert any("no advance owed" in one for one in table.refusals)
