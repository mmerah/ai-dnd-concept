import asyncio
from pathlib import Path
from random import Random
from typing import cast

import pytest
from claude_agent_sdk import McpSdkServerConfig
from core_test_support import (
    CHARACTERS,
    LONER3E,
    SCENARIOS,
    EnvFileFreeSettings,
    change_args,
    scenario_for,
)
from pydantic import JsonValue, ValidationError
from pydantic_ai import ModelRetry

from aidm.app.launch import LaunchTarget
from aidm.app.runtime import Runtime
from aidm.config import Settings
from aidm.harness.claude import ClaudeDriver
from aidm.harness.codemode import Harness
from aidm.harness.exec import ExecDriver
from aidm.harness.mcp import SERVER_NAME, call, offered
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.model import Game

VAULT_MAP = EntityId("vault-map")
MARA = EntityId("mara")

A_QUESTION: dict[str, JsonValue] = {
    "actor_id": PLAYER_ID,
    "question": "Does he hear what waits past the vault door?",
    "position": "advantage",
    "edge": "Quiet Hands",
}
A_CONFLICT: dict[str, JsonValue] = {
    "actor_id": PLAYER_ID,
    "question": "Does he wrest the ledger out of her hands?",
    "opponent_id": MARA,
}


def _settings(tmp_path: Path) -> Settings:
    # No api_key anywhere: code mode plays without one, and this fixture is that claim's test.
    return EnvFileFreeSettings(
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
        saves_dir=tmp_path,
        harness="external",
    )


def test_the_driver_serves_this_app_s_own_mcp_server_in_process(tmp_path: Path) -> None:
    driver = ClaudeDriver(runtime=Runtime(_settings(tmp_path)), slug="whispering-vault--kael")
    options = driver.options()
    assert isinstance(options.mcp_servers, dict)
    served = cast(McpSdkServerConfig, options.mcp_servers[SERVER_NAME])
    assert served["instance"] is not None
    # A second aidm from `.mcp.json` would be a second writer on the same save.
    assert options.strict_mcp_config


def test_the_agent_s_first_listing_already_carries_the_engine_commands(tmp_path: Path) -> None:
    driver = ClaudeDriver(runtime=Runtime(_settings(tmp_path)), slug="whispering-vault--kael")
    assert "roll_question" in {tool.name for tool in offered(driver.opened())}


class _Chatty(ExecDriver):
    """One line, then a child that would outlive the turn."""

    def argv(self, text: str) -> list[str]:
        del text
        return ["sh", "-c", "echo '{\"n\": 1}'; sleep 30"]

    def line(self, event: dict[str, JsonValue]) -> str | None:
        del event
        return "one"


async def test_abandoning_a_turn_kills_the_cli_it_spawned(tmp_path: Path) -> None:
    driver = _Chatty(runtime=Runtime(_settings(tmp_path)))
    playing = driver.play("go")
    assert await anext(playing) == "one"
    process = driver.process
    assert process is not None
    await playing.aclose()
    # A 30s wait here is the failure: the CLI's own children outlived the turn.
    assert await asyncio.wait_for(process.wait(), 5) != 0
    assert driver.process is None


def _opened(tmp_path: Path) -> Harness:
    settings = _settings(tmp_path)
    harness = Harness(settings=settings, runtime=Runtime(settings))
    harness.open_game(f"{scenario_for(LONER3E)}--kael")
    return harness


def _saved(harness: Harness) -> Game:
    session = harness.opened()
    raw = session.store.load(session.slug)
    assert raw is not None
    return session.engine.restored(raw)


def test_a_director_tool_call_lands_on_disk(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    assert "change_world" in {tool.name for tool in offered(harness)}
    _ = call(harness, "start_turn", {"text": "I look around."})
    answered = call(harness, "change_world", change_args("reveal", entity_id=VAULT_MAP))

    assert "vault-map" in answered
    assert _saved(harness).world.require(VAULT_MAP).known


def test_the_save_carries_the_turn_s_cards_as_they_land_and_files_them_at_the_end(
    tmp_path: Path,
) -> None:
    """The page streams mechanics off the save, so a harness in another process shows them too."""
    harness = _opened(tmp_path)

    _ = call(harness, "start_turn", {"text": "I listen at the door."})
    assert _saved(harness).turn_facts == ()
    _ = call(harness, "change_world", change_args("reveal", entity_id=VAULT_MAP))
    assert len(_saved(harness).turn_facts) == 1
    _ = call(harness, "roll_question", A_QUESTION)
    assert len(_saved(harness).turn_facts) == 2

    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "Dust hangs."}]})
    saved = _saved(harness)
    assert saved.turn_facts == ()
    assert len(saved.history[-1].facts) == 2


def test_end_turn_records_the_exchange_and_bumps_the_turn(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    _ = call(harness, "start_turn", {"text": "I look around."})
    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "Dust hangs."}]})

    saved = _saved(harness)
    assert saved.turn == 1
    assert saved.history[-1].prompt == "I look around."
    assert saved.history[-1].narration == "Dust hangs."


def test_a_turn_with_neither_prose_nor_a_decision_is_refused(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    _ = call(harness, "start_turn", {"text": "I wait."})
    with pytest.raises(ModelRetry):
        _ = call(harness, "end_turn", {"lines": []})


def test_no_tool_runs_a_turn_before_start_turn_opens_one(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    with pytest.raises(ModelRetry):
        _ = call(harness, "change_world", change_args("reveal", entity_id=VAULT_MAP))
    with pytest.raises(ModelRetry):
        _ = call(harness, "end_turn", {"lines": []})


def test_a_name_the_engine_does_not_publish_is_refused(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    _ = call(harness, "start_turn", {"text": "I look around."})
    with pytest.raises(ValueError, match="is not a tool of"):
        _ = call(harness, "settle_everything", {})


def test_a_no_args_tool_refuses_junk_arguments(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    with pytest.raises(ValidationError):
        _ = call(harness, "scene", {"junk": 1})


def test_an_open_decision_blocks_every_other_tool_until_it_is_answered(tmp_path: Path) -> None:
    """An unfinished conflict: nothing else lands until the player's next message answers it."""
    harness = _opened(tmp_path)
    harness.opened().rng = Random(0)

    _ = call(harness, "start_turn", {"text": "I grab for the ledger in her hands."})
    _ = call(harness, "roll_question", A_CONFLICT)
    assert _saved(harness).pending is not None
    assert "waiting on the player" in call(
        harness, "change_world", change_args("reveal", entity_id=VAULT_MAP)
    )
    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "She holds on."}]})

    _ = call(harness, "start_turn", {"text": "I let it be."})
    assert _saved(harness).pending is None
    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You step back."}]})


def test_a_viewer_in_another_process_picks_up_what_the_server_committed(tmp_path: Path) -> None:
    harness = _opened(tmp_path)
    viewer = Runtime(harness.settings).session(
        LaunchTarget(
            slug=harness.opened().slug, scenario_id="whispering-vault", character_id="kael"
        )
    )
    assert viewer.state.turn == 0

    _ = call(harness, "start_turn", {"text": "I listen."})
    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "Water drips."}]})

    assert viewer.reload()
    assert viewer.state.turn == 1
    assert not viewer.reload()


def test_opening_a_new_game_writes_the_save_the_viewer_reads(tmp_path: Path) -> None:
    harness = _opened(tmp_path)

    saved = _saved(harness)
    assert saved.turn == 0
    assert saved.history == ()


def test_an_answers_note_is_shown_now_and_spent_rather_than_leaking_a_turn_late(
    tmp_path: Path,
) -> None:
    """`start_turn` takes the note `consume_answer` wrote; `scene()` still shows it mid-turn."""
    harness = _opened(tmp_path)
    harness.opened().rng = Random(0)
    _ = call(harness, "start_turn", {"text": "I grab for the ledger in her hands."})
    _ = call(harness, "roll_question", A_CONFLICT)
    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "She holds on."}]})

    opened = call(harness, "start_turn", {"text": "I let go and step back"})

    assert "paused play" in opened
    assert "paused play" in harness.scene()
    _ = call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You wait."}]})
    assert "paused play" not in harness.scene()
