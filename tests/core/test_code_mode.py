import asyncio
import json
import shutil
from pathlib import Path
from random import Random
from typing import cast

import pytest
from claude_agent_sdk import McpSdkServerConfig
from core_test_support import (
    CHARACTERS,
    LONER3E,
    SCENARIOS,
    TWENTYFOURXX,
    EnvFileFreeSettings,
    at_boundary,
    scenario_for,
    updated,
    with_entity,
)
from pydantic import JsonValue
from pydantic_ai import ModelRetry

from aidm.app.launch import LaunchTarget
from aidm.app.runtime import Runtime
from aidm.config import AuthoringConfig, Settings
from aidm.content.io import FileStore, SavedGame, load_scenario
from aidm.engines.loner3e.rules import AdventureGrowth, Change, Mechanics
from aidm.harness.claude import ClaudeDriver
from aidm.harness.codemode import Harness
from aidm.harness.exec import ExecDriver
from aidm.harness.mcp import SERVER_NAME, call, offered
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId

VAULT = EntityId("vault")
CLOISTER = EntityId("cloister")
GROWN = EntityId("sub-crypt")

LEGAL = AdventureGrowth(
    changes=(Change(kind="gear", tag="Waxed Rope"),), why="he never climbs without it now"
)
ILLEGAL = AdventureGrowth(
    changes=(Change(kind="rewrite", tag="Never Held a Blade", into="Holds It Well"),),
    why="a tag the sheet does not carry",
)
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
    driver = ClaudeDriver(
        runtime=Runtime(_settings(tmp_path)), slug="whispering-vault--kael--loner3e"
    )
    options = driver.options()
    assert isinstance(options.mcp_servers, dict)
    served = cast(McpSdkServerConfig, options.mcp_servers[SERVER_NAME])
    assert served["instance"] is not None
    # A second aidm from `.mcp.json` would be a second writer on the same save.
    assert options.strict_mcp_config


async def test_the_agent_s_first_listing_already_carries_the_engine_commands(
    tmp_path: Path,
) -> None:
    driver = ClaudeDriver(
        runtime=Runtime(_settings(tmp_path)), slug="whispering-vault--kael--loner3e"
    )
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


def _opened(
    tmp_path: Path, engine: str, growth_frontier: int = 1
) -> tuple[Harness, FileStore, str]:
    harness = _harness(_settings(tmp_path, growth_frontier))
    slug = f"{scenario_for(EngineId(engine))}--kael--{engine}"
    harness.open_game(slug)
    return harness, FileStore(tmp_path), slug


def _growing(tmp_path: Path) -> tuple[Harness, FileStore, str]:
    harness, store, slug = _opened(tmp_path, "loner3e", growth_frontier=9)
    session = harness.opened()
    session.scenario = updated(session.scenario, grows=True)
    return harness, store, slug


def _saved(store: FileStore, slug: str) -> SavedGame:
    saved = store.load(slug)
    assert saved is not None
    return saved


async def test_a_director_tool_call_lands_on_disk(tmp_path: Path) -> None:
    harness, store, slug = _opened(tmp_path, "loner3e")

    assert "reveal" in {tool.name for tool in await offered(harness)}
    _ = await call(harness, "start_turn", {"prompt": "I look around."})
    answered = await call(harness, "reveal", {"entity_id": VAULT})

    assert "vault" in answered
    assert _saved(store, slug).world.require(VAULT).known


async def test_the_save_carries_the_turn_s_cards_as_they_land_and_files_them_at_the_end(
    tmp_path: Path,
) -> None:
    """The page streams mechanics off the save, so a harness in another process shows them too."""
    harness, store, slug = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"prompt": "I listen at the door."})
    assert _saved(store, slug).turn_events == ()
    _ = await call(harness, "reveal", {"entity_id": VAULT})
    assert len(_saved(store, slug).turn_events) == 1
    _ = await call(harness, "roll_question", A_QUESTION)
    assert len(_saved(store, slug).turn_events) == 2

    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "Dust hangs."}]})
    saved = _saved(store, slug)
    assert saved.turn_events == ()
    assert len(saved.history[-1].events) == 2


async def test_end_turn_records_the_exchange_and_bumps_the_turn(tmp_path: Path) -> None:
    harness, store, slug = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"prompt": "I look around."})
    _ = await call(
        harness,
        "end_turn",
        {"lines": [{"speaker_id": None, "text": "Dust hangs."}]},
    )

    saved = _saved(store, slug)
    assert saved.turn == 1
    assert saved.history[-1].prompt == "I look around."
    assert saved.history[-1].narration == "Dust hangs."


async def test_a_turn_with_neither_prose_nor_a_decision_is_refused(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")

    _ = await call(harness, "start_turn", {"prompt": "I wait."})
    with pytest.raises(ModelRetry):
        _ = await call(harness, "end_turn", {"lines": []})


async def test_no_tool_runs_a_turn_before_start_turn_opens_one(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")

    with pytest.raises(ModelRetry):
        _ = await call(harness, "reveal", {"entity_id": VAULT})
    with pytest.raises(ModelRetry):
        _ = await call(harness, "end_turn", {"lines": []})


async def test_an_open_decision_blocks_every_other_tool_until_it_is_answered(
    tmp_path: Path,
) -> None:
    """The whole suspension chain: a stake, its failed roll, and the hit settled in free text."""
    harness, store, slug = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)

    _ = await call(harness, "start_turn", {"prompt": "I climb the shaft."})
    _ = await call(
        harness,
        "stake_attempt",
        {"actor_id": PLAYER_ID, "goal": "climb the shaft", "hit": True, "risk": "a long fall"},
    )
    assert _saved(store, slug).pending is not None
    with pytest.raises(ValueError, match="waiting on the player"):
        _ = await call(harness, "reveal", {"entity_id": VAULT})
    _ = await call(
        harness, "end_turn", {"lines": [{"speaker_id": None, "text": "The shaft yawns."}]}
    )

    _ = await call(harness, "start_turn", {"prompt": "I go on.", "option_id": "proceed"})
    pending = _saved(store, slug).pending
    assert pending is not None and pending.kind == "defence"
    # A free-text answer is the only way this decision closes.
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You slip."}]})

    _ = await call(harness, "start_turn", {"prompt": "I take it on the shoulder"})
    _ = await call(harness, "settle_defence", {"item_id": None})
    assert _saved(store, slug).pending is None


async def test_a_viewer_in_another_process_picks_up_what_the_server_committed(
    tmp_path: Path,
) -> None:
    harness, _, slug = _opened(tmp_path, "loner3e")
    viewer = Runtime(harness.settings).session(
        LaunchTarget(slug=slug, scenario_id="whispering-vault", character_id="kael", engine=LONER3E)
    )
    assert viewer.state.turn == 0

    _ = await call(harness, "start_turn", {"prompt": "I listen."})
    _ = await call(
        harness,
        "end_turn",
        {"lines": [{"speaker_id": None, "text": "Water drips."}]},
    )

    assert viewer.reload()
    assert viewer.state.turn == 1
    assert not viewer.reload()


async def test_opening_a_new_game_writes_the_save_the_viewer_reads(tmp_path: Path) -> None:
    _, store, slug = _opened(tmp_path, "loner3e")

    saved = _saved(store, slug)
    assert saved.turn == 0
    assert saved.history == ()


async def test_an_answers_note_is_shown_now_and_spent_rather_than_leaking_a_turn_late(
    tmp_path: Path,
) -> None:
    """`start_turn` takes the note `consume_answer` wrote; `scene()` still shows it mid-turn."""
    harness, _, _ = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)
    _ = await call(harness, "start_turn", {"prompt": "I climb the shaft."})
    _ = await call(
        harness,
        "stake_attempt",
        {"actor_id": PLAYER_ID, "goal": "climb the shaft", "hit": True, "risk": "a long fall"},
    )
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "It yawns."}]})
    _ = await call(harness, "start_turn", {"prompt": "I go on.", "option_id": "proceed"})
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You slip."}]})

    opened = await call(harness, "start_turn", {"prompt": "I take it on the shoulder"})

    assert "paused play" in opened
    assert "paused play" in harness.scene()
    _ = await call(harness, "settle_defence", {"item_id": None})
    _ = await call(harness, "end_turn", {"lines": [{"speaker_id": None, "text": "You hold."}]})
    assert "paused play" not in harness.scene()


async def test_end_turn_says_growth_is_due_only_when_it_is(tmp_path: Path) -> None:
    """The server states it off committed state; the model never judges whether it is time."""
    harness, _, _ = _opened(tmp_path, "loner3e", growth_frontier=9)
    rested: dict[str, JsonValue] = {
        "lines": [{"speaker_id": None, "text": "Quiet settles."}],
    }

    _ = await call(harness, "start_turn", {"prompt": "I rest."})
    assert "WORLD GROWTH DUE" not in await call(harness, "end_turn", rested)

    session = harness.opened()
    session.scenario = updated(session.scenario, grows=True)
    _ = await call(harness, "start_turn", {"prompt": "I rest."})
    assert "WORLD GROWTH DUE" in await call(harness, "end_turn", rested)
    assert "WORLD GROWTH DUE" in harness.scene()


async def test_a_growth_run_lands_canon_the_player_has_still_to_find(tmp_path: Path) -> None:
    harness, store, slug = _growing(tmp_path)

    assert "scenario_so_far" in await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "connect", {"from_id": CLOISTER, "to_id": GROWN})
    landed = await call(harness, "finish_growth", {"summary": "A crypt below the cloister."})

    assert GROWN in landed
    world = _saved(store, slug).world
    assert not world.require(GROWN).known
    assert world.require(CLOISTER).exit_to(GROWN) is not None
    assert harness.authoring is None


async def test_a_draft_under_the_bar_is_refused_and_the_run_stays_open(tmp_path: Path) -> None:
    harness, _, _ = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})

    with pytest.raises(ModelRetry) as refused:
        _ = await call(harness, "finish_growth", {"summary": "nowhere to reach it from"})

    assert "exit" in str(refused.value)
    assert harness.authoring is not None


async def test_authoring_needs_a_run_and_a_second_begin_discards_the_first(
    tmp_path: Path,
) -> None:
    harness, _, _ = _growing(tmp_path)
    with pytest.raises(ModelRetry):
        _ = await call(harness, "scenario_so_far", {})

    _ = await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "begin_growth", {})

    assert GROWN not in await call(harness, "scenario_so_far", {})


async def test_opening_another_game_abandons_the_growth_run_of_the_first(tmp_path: Path) -> None:
    """Its patch is diffed against the game it began in, so it must not land in another."""
    harness, _, _ = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})

    harness.open_game(f"{scenario_for(TWENTYFOURXX)}--kael--twentyfourxx")

    assert harness.authoring is None


async def test_a_turn_tool_commits_as_usual_while_a_growth_run_is_open(tmp_path: Path) -> None:
    """The patch is additions-only, so play and authorship need no exclusion between them."""
    harness, store, slug = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})

    _ = await call(harness, "start_turn", {"prompt": "I look around."})
    _ = await call(harness, "reveal", {"entity_id": VAULT})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "connect", {"from_id": CLOISTER, "to_id": GROWN})
    _ = await call(harness, "finish_growth", {"summary": "A crypt below the cloister."})

    world = _saved(store, slug).world
    assert world.require(VAULT).known and not world.require(GROWN).known


async def test_an_id_the_game_took_meanwhile_reaches_the_author_at_finish(
    tmp_path: Path,
) -> None:
    """Builtin logs and drops the patch; here the driver is told, and can rename and re-finish."""
    harness, _, _ = _growing(tmp_path)
    _ = await call(harness, "begin_growth", {})
    _ = await call(harness, "write", {"patch": A_NEW_PLACE})
    _ = await call(harness, "connect", {"from_id": CLOISTER, "to_id": GROWN})
    session = harness.opened()
    taken = Entity(id=GROWN, kind="location", name="the sub-crypt", brief="Taken first.")
    session.commit(with_entity(session.state, taken))

    with pytest.raises(ValueError):
        _ = await call(harness, "finish_growth", {"summary": "A crypt below the cloister."})

    assert harness.authoring is not None


async def test_propose_advance_publishes_the_engines_own_proposal_schema(
    tmp_path: Path,
) -> None:
    harness = _harness(_settings(tmp_path))
    assert "propose_advance" not in {tool.name for tool in await offered(harness)}

    _ = harness.open_game("whispering-vault--kael--loner3e")

    published = next(one for one in await offered(harness) if one.name == "propose_advance")
    assert AdventureGrowth.__name__ in json.dumps(published.input_schema)


async def test_a_proposal_previews_and_only_apply_advance_commits_it(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")
    session = harness.opened()
    session.commit(at_boundary(session.state))
    asked: dict[str, JsonValue] = {
        "subject_id": PLAYER_ID,
        "proposal": LEGAL.model_dump(mode="json"),
    }

    previewed = await call(harness, "propose_advance", asked)

    assert "Waxed Rope" in previewed
    assert "Waxed Rope" not in Mechanics.of_game(session.state).sheets[PLAYER_ID].gear
    _ = await call(harness, "apply_advance", {})
    assert "Waxed Rope" in Mechanics.of_game(session.state).sheets[PLAYER_ID].gear


async def test_an_illegal_proposal_comes_back_with_the_engines_reason(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")
    session = harness.opened()
    session.commit(at_boundary(session.state))

    with pytest.raises(ModelRetry) as refused:
        _ = await call(
            harness,
            "propose_advance",
            {"subject_id": PLAYER_ID, "proposal": ILLEGAL.model_dump(mode="json")},
        )

    assert "Never Held a Blade" in str(refused.value)
    assert session.drafted is None


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
                "starting_location_id": "millrace",
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
                        "rules": {"concept": "A Miller Who Stayed"},
                    },
                ],
                "threads": [{"id": "the-bell", "title": "The drowned bell"}],
            }
        },
    )
    _ = await call(harness, "connect", {"from_id": "millrace", "to_id": "wheelhouse"})

    written = await call(harness, "finish_scenario", {"summary": "A mill and its wheelhouse."})

    assert "The Sunken Mill" in written
    landed = load_scenario(scenarios, "sunken-mill")
    assert landed.meta.title == "The Sunken Mill"
    assert landed.packs == ("srd",)
    assert harness.authoring is None


async def test_a_resume_that_re_suspended_may_still_develop_what_the_answer_caused(
    tmp_path: Path,
) -> None:
    """The same gate the builtin Director runs: core commands land, engine mechanics do not."""
    harness, _, _ = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)
    _ = await call(harness, "start_turn", {"prompt": "I climb the shaft."})
    _ = await call(
        harness,
        "stake_attempt",
        {"actor_id": PLAYER_ID, "goal": "climb the shaft", "hit": True, "risk": "a long fall"},
    )
    _ = await call(
        harness, "end_turn", {"lines": [{"speaker_id": None, "text": "The shaft yawns."}]}
    )
    _ = await call(harness, "start_turn", {"prompt": "I go on.", "option_id": "proceed"})

    _ = await call(
        harness, "add_trait", {"entity_id": "player", "trait_id": "winded", "text": "Breath short."}
    )
    with pytest.raises(ValueError, match="waiting on the player"):
        _ = await call(
            harness,
            "roll_attempt",
            {"actor_id": PLAYER_ID, "goal": "swing again", "hit": True},
        )
