import asyncio
import shutil
from dataclasses import replace
from pathlib import Path
from random import Random
from typing import cast

import pytest
from claude_agent_sdk import McpSdkServerConfig
from core_test_support import (
    CATCH_BREATH,
    CHARACTERS,
    ENGINES_BUILT,
    LONER3E,
    SCENARIOS,
    TWENTYFOURXX,
    EnvFileFreeSettings,
    change_args,
    scenario_for,
    updated,
    with_entity,
)
from pydantic import JsonValue, ValidationError
from pydantic_ai import ModelRetry

from aidm.app.launch import LaunchTarget
from aidm.app.runtime import Runtime
from aidm.config import AuthoringConfig, Settings
from aidm.content.io import load_scenario
from aidm.harness.claude import ClaudeDriver
from aidm.harness.codemode import Harness
from aidm.harness.exec import ExecDriver
from aidm.harness.mcp import SERVER_NAME, call, offered
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId
from aidm.state.model import Game

VAULT = EntityId("vault")
CLOISTER = EntityId("cloister")
GROWN = EntityId("sub-crypt")


A_QUESTION: dict[str, JsonValue] = {
    "actor_id": PLAYER_ID,
    "question": "Does he hear what waits past the vault door?",
    "position": "advantage",
    "edge": "Quiet Hands",
}
A_NEW_PLACE: dict[str, JsonValue] = {
    "entities": [
        {
            "id": GROWN,
            "kind": "location",
            "name": "the sub-crypt",
            "brief": "Ossuary niches below the cloister.",
        }
    ]
}


def _settings(
    tmp_path: Path, growth_frontier: int = 1, scenarios_dir: Path = SCENARIOS
) -> Settings:
    # No api_key anywhere: code mode plays without one, and this fixture is that claim's test.
    return EnvFileFreeSettings(
        scenarios_dir=scenarios_dir,
        characters_dir=CHARACTERS,
        saves_dir=tmp_path,
        authoring=AuthoringConfig(growth_frontier=growth_frontier),
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


async def test_the_agent_s_first_listing_already_carries_the_engine_commands(
    tmp_path: Path,
) -> None:
    driver = ClaudeDriver(runtime=Runtime(_settings(tmp_path)), slug="whispering-vault--kael")
    assert "roll_question" in {tool.name for tool in await offered(driver.opened())}


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


def _harness(settings: Settings) -> Harness:
    return Harness(settings=settings, runtime=Runtime(settings))


def _opened(tmp_path: Path, engine: str, growth_frontier: int = 1) -> Harness:
    harness = _harness(_settings(tmp_path, growth_frontier))
    slug = f"{scenario_for(EngineId(engine))}--kael"
    harness.open_game(slug)
    return harness


def _offering(harness: Harness) -> None:
    session = harness.opened()
    session.engine = replace(session.legacy, player_actions=(CATCH_BREATH,))


def _growing(tmp_path: Path) -> Harness:
    harness = _opened(tmp_path, "loner3e", growth_frontier=9)
    session = harness.opened()
    session.scenario = updated(session.scenario, grows=True)
    return harness


def _saved(harness: Harness) -> Game:
    session = harness.opened()
    raw = session.store.load(session.slug)
    assert raw is not None
    return session.engine.restored(raw)


async def test_a_director_tool_call_lands_on_disk(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    assert "change_world" in {tool.name for tool in await offered(harness)}
    _ = await call(harness, "start_turn", {"text": "I look around."})
    answered = await call(harness, "change_world", change_args("reveal", entity_id=VAULT))

    assert "vault" in answered
    assert _saved(harness).world.require(VAULT).known


async def test_the_save_carries_the_turn_s_cards_as_they_land_and_files_them_at_the_end(
    tmp_path: Path,
) -> None:
    """The page streams mechanics off the save, so a harness in another process shows them too."""
    harness = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"text": "I listen at the door."})
    assert _saved(harness).turn_facts == ()
    _ = await call(harness, "change_world", change_args("reveal", entity_id=VAULT))
    assert len(_saved(harness).turn_facts) == 1
    _ = await call(harness, "roll_question", A_QUESTION)
    assert len(_saved(harness).turn_facts) == 2

    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "Dust hangs."}]})
    saved = _saved(harness)
    assert saved.turn_facts == ()
    assert len(saved.history[-1].facts) == 2


async def test_end_turn_records_the_exchange_and_bumps_the_turn(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"text": "I look around."})
    _ = await call(
        harness,
        "end_turn",
        {"lines": [{"speaker_id": None, "text": "Dust hangs."}]},
    )

    saved = _saved(harness)
    assert saved.turn == 1
    assert saved.history[-1].prompt == "I look around."
    assert saved.history[-1].narration == "Dust hangs."


async def test_a_turn_with_neither_prose_nor_a_decision_is_refused(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"text": "I wait."})
    with pytest.raises(ModelRetry):
        _ = await call(harness, "end_turn", {"lines": []})


async def test_no_tool_runs_a_turn_before_start_turn_opens_one(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    with pytest.raises(ModelRetry):
        _ = await call(harness, "change_world", change_args("reveal", entity_id=VAULT))
    with pytest.raises(ModelRetry):
        _ = await call(harness, "end_turn", {"lines": []})


async def test_a_resolver_is_not_callable_by_name_from_the_director(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"text": "I look around."})
    with pytest.raises(ValueError, match="is not a tool of"):
        _ = await call(harness, "take_over", {"successor_id": PLAYER_ID})


async def test_a_no_args_tool_refuses_junk_arguments(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    with pytest.raises(ValidationError):
        _ = await call(harness, "scene", {"junk": 1})


async def test_an_open_decision_blocks_every_other_tool_until_it_is_answered(
    tmp_path: Path,
) -> None:
    """The whole suspension chain: a stake, its failed roll, and the hit settled by its pick."""
    harness = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)

    _ = await call(harness, "start_turn", {"text": "I climb the shaft."})
    _ = await call(
        harness,
        "stake_attempt",
        {"actor_id": PLAYER_ID, "goal": "climb the shaft", "hit": True, "risk": "a long fall"},
    )
    assert _saved(harness).pending is not None
    assert "waiting on the player" in await call(
        harness, "change_world", change_args("reveal", entity_id=VAULT)
    )
    _ = await call(
        harness, "end_turn", {"lines": [{"speaker_id": None, "text": "The shaft yawns."}]}
    )

    _ = await call(harness, "start_turn", {"option_id": "proceed"})
    pending = _saved(harness).pending
    assert pending is not None and pending.kind == "defence"
    # The options are the whole pick: the engine settles the hit from the one the player takes.
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You slip."}]})

    _ = await call(harness, "start_turn", {"option_id": "take-it"})
    assert _saved(harness).pending is None
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "It lands."}]})


async def test_a_viewer_in_another_process_picks_up_what_the_server_committed(
    tmp_path: Path,
) -> None:
    harness = _opened(tmp_path, "loner3e")
    viewer = Runtime(harness.settings).session(
        LaunchTarget(
            slug=harness.opened().slug, scenario_id="whispering-vault", character_id="kael"
        )
    )
    assert viewer.state.turn == 0

    _ = await call(harness, "start_turn", {"text": "I listen."})
    _ = await call(
        harness,
        "end_turn",
        {"lines": [{"speaker_id": None, "text": "Water drips."}]},
    )

    assert viewer.reload()
    assert viewer.state.turn == 1
    assert not viewer.reload()


async def test_opening_a_new_game_writes_the_save_the_viewer_reads(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")

    saved = _saved(harness)
    assert saved.turn == 0
    assert saved.history == ()


async def test_an_answers_note_is_shown_now_and_spent_rather_than_leaking_a_turn_late(
    tmp_path: Path,
) -> None:
    """`start_turn` takes the note `consume_answer` wrote; `scene()` still shows it mid-turn."""
    harness = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)
    _ = await call(harness, "start_turn", {"text": "I climb the shaft."})
    _ = await call(
        harness,
        "stake_attempt",
        {"actor_id": PLAYER_ID, "goal": "climb the shaft", "hit": True, "risk": "a long fall"},
    )
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "It yawns."}]})

    opened = await call(harness, "start_turn", {"text": "I back off and look for a rope"})

    assert "paused play" in opened
    assert "paused play" in harness.scene()
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You wait."}]})
    assert "paused play" not in harness.scene()


async def test_end_turn_says_growth_is_due_only_when_it_is(tmp_path: Path) -> None:
    """The server states it off committed state; the model never judges whether it is time."""
    harness = _opened(tmp_path, "loner3e", growth_frontier=9)
    rested: dict[str, JsonValue] = {
        "lines": [{"speaker_id": None, "text": "Quiet settles."}],
    }

    _ = await call(harness, "start_turn", {"text": "I rest."})
    assert "WORLD GROWTH DUE" not in await call(harness, "end_turn", rested)

    session = harness.opened()
    session.scenario = updated(session.scenario, grows=True)
    _ = await call(harness, "start_turn", {"text": "I rest."})
    assert "WORLD GROWTH DUE" in await call(harness, "end_turn", rested)
    assert "WORLD GROWTH DUE" in harness.scene()


async def test_a_growth_run_lands_canon_the_player_has_still_to_find(tmp_path: Path) -> None:
    harness = _growing(tmp_path)

    assert "scenario_so_far" in await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "connect", {"from_id": CLOISTER, "to_id": GROWN})
    landed = await call(harness, "finish_growth", {})

    assert GROWN in landed
    world = _saved(harness).world
    assert not world.require(GROWN).known
    assert world.require(CLOISTER).exit_to(GROWN) is not None
    assert harness.authoring is None


async def test_a_draft_under_the_bar_is_refused_and_the_run_stays_open(tmp_path: Path) -> None:
    harness = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})

    with pytest.raises(ModelRetry) as refused:
        _ = await call(harness, "finish_growth", {})

    assert "exit" in str(refused.value)
    assert harness.authoring is not None


async def test_authoring_needs_a_run_and_a_second_begin_discards_the_first(
    tmp_path: Path,
) -> None:
    harness = _growing(tmp_path)
    with pytest.raises(ModelRetry):
        _ = await call(harness, "scenario_so_far", {})

    _ = await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "begin_growth", {})

    assert GROWN not in await call(harness, "scenario_so_far", {})


async def test_opening_another_game_abandons_the_growth_run_of_the_first(tmp_path: Path) -> None:
    """Its patch is diffed against the game it began in, so it must not land in another."""
    harness = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})

    harness.open_game(f"{scenario_for(TWENTYFOURXX)}--kael")

    assert harness.authoring is None


async def test_a_turn_tool_commits_as_usual_while_a_growth_run_is_open(tmp_path: Path) -> None:
    """The patch is additions-only, so play and authorship need no exclusion between them."""
    harness = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})

    _ = await call(harness, "start_turn", {"text": "I look around."})
    _ = await call(harness, "change_world", change_args("reveal", entity_id=VAULT))
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "connect", {"from_id": CLOISTER, "to_id": GROWN})
    _ = await call(harness, "finish_growth", {})

    world = _saved(harness).world
    assert world.require(VAULT).known and not world.require(GROWN).known


async def test_an_id_the_game_took_meanwhile_reaches_the_author_at_finish(
    tmp_path: Path,
) -> None:
    """Builtin logs and drops the patch; here the driver is told, and can rename and re-finish."""
    harness = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "connect", {"from_id": CLOISTER, "to_id": GROWN})
    session = harness.opened()
    taken = Entity(id=GROWN, kind="location", name="the sub-crypt", brief="Taken first.")
    session.commit(with_entity(session.state, taken))

    with pytest.raises(ValueError):
        _ = await call(harness, "finish_growth", {})

    assert harness.authoring is not None


async def test_a_scenario_run_writes_a_scenario_that_loads(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS, scenarios)
    harness = _harness(_settings(tmp_path, scenarios_dir=scenarios))

    briefing = await call(
        harness,
        "begin_scenario",
        {
            "slug": "sunken-mill",
            "premise": "A flooded mill hides a drowned bell.",
            "engine": LONER3E,
            "grows": True,
            "packs": ["srd"],
        },
    )
    assert "finish_scenario" in briefing
    _ = await call(
        harness,
        "write",
        {
            "patch": {
                "meta": {
                    "title": "The Sunken Mill",
                    "premise": "A flooded mill hides a drowned bell.",
                },
                "player_parent_id": "millrace",
                "entities": [
                    {
                        "id": "millrace",
                        "kind": "location",
                        "name": "the millrace",
                        "brief": "Black water races under a broken sluice.",
                        "known": True,
                    },
                    {
                        "id": "wheelhouse",
                        "kind": "location",
                        "name": "the wheelhouse",
                        "brief": "The great wheel stands still and furred with weed.",
                    },
                    {
                        "id": "miller",
                        "kind": "actor",
                        "name": "the miller",
                        "brief": "He has not left the mill since the flood.",
                        "parent_id": "wheelhouse",
                    },
                ],
                "threads": [{"id": "the-bell", "title": "The drowned bell"}],
                "mechanics": {"sheets": {"miller": {"concept": "A Miller Who Stayed"}}},
            }
        },
    )
    _ = await call(harness, "connect", {"from_id": "millrace", "to_id": "wheelhouse"})

    written = await call(harness, "finish_scenario", {})

    assert "The Sunken Mill" in written
    landed = load_scenario(scenarios, "sunken-mill", ENGINES_BUILT[LONER3E])
    assert landed.meta.title == "The Sunken Mill"
    assert landed.packs == ("srd",)
    assert harness.authoring is None


async def test_a_resume_that_re_suspended_may_still_develop_what_the_answer_caused(
    tmp_path: Path,
) -> None:
    """The same gate the builtin Director runs: core commands land, engine mechanics do not."""
    harness = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)
    _ = await call(harness, "start_turn", {"text": "I climb the shaft."})
    _ = await call(
        harness,
        "stake_attempt",
        {"actor_id": PLAYER_ID, "goal": "climb the shaft", "hit": True, "risk": "a long fall"},
    )
    _ = await call(
        harness, "end_turn", {"lines": [{"speaker_id": None, "text": "The shaft yawns."}]}
    )
    _ = await call(harness, "start_turn", {"option_id": "proceed"})

    _ = await call(
        harness,
        "change_world",
        change_args("add_trait", entity_id="player", name="Winded", text="Breath short."),
    )
    assert "waiting on the player" in await call(
        harness,
        "roll_attempt",
        {"actor_id": PLAYER_ID, "goal": "swing again", "risk": "a longer fall", "hit": True},
    )


async def test_the_picture_shows_you_can_only_when_the_engine_offers_something(
    tmp_path: Path,
) -> None:
    harness = _opened(tmp_path, "loner3e")
    assert "YOU CAN" not in harness.scene()

    _offering(harness)

    assert (
        'YOU CAN:\n- Catch your breath: player_action(name=catch-breath, args={"deep": true})'
        in harness.scene()
    )


async def test_player_action_applies_the_offer_the_player_asked_for(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")
    _offering(harness)

    answered = await call(
        harness, "player_action", {"name": "catch-breath", "args": {"deep": True}}
    )

    assert "breathes deep" in answered
    assert _saved(harness).history[-1].prompt == "Catch your breath"


async def test_player_action_refuses_and_lists_offers_for_an_unknown_name(
    tmp_path: Path,
) -> None:
    harness = _opened(tmp_path, "loner3e")
    _offering(harness)

    with pytest.raises(ModelRetry, match="catch-breath"):
        _ = await call(harness, "player_action", {"name": "juggle-knives", "args": {}})


async def test_player_action_refuses_and_lists_offers_for_args_matching_none(
    tmp_path: Path,
) -> None:
    harness = _opened(tmp_path, "loner3e")
    _offering(harness)

    with pytest.raises(ModelRetry, match="catch-breath"):
        _ = await call(harness, "player_action", {"name": "catch-breath", "args": {"deep": False}})


async def test_player_action_still_refuses_while_a_turn_is_open(tmp_path: Path) -> None:
    harness = _opened(tmp_path, "loner3e")
    _offering(harness)
    _ = await call(harness, "start_turn", {"text": "I look around."})

    with pytest.raises(ModelRetry, match="a turn is open"):
        _ = await call(harness, "player_action", {"name": "catch-breath", "args": {"deep": True}})
