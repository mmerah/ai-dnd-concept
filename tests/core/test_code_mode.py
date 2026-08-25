import json
import shutil
from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    CHARACTERS,
    LONER3E,
    SCENARIOS,
    EnvFileFreeSettings,
    at_boundary,
    updated,
    with_entity,
)
from pydantic import JsonValue
from pydantic_ai import ModelRetry

from aidm.app.launch import LaunchTarget
from aidm.app.mcp import Harness
from aidm.app.runtime import Runtime
from aidm.config import AuthoringConfig, Settings
from aidm.content.io import FileStore, SavedGame, load_scenario
from aidm.engines.loner3e.rules import AdventureGrowth, Change, Mechanics
from aidm.state.entities import PLAYER_ID, Entity, EntityId

VAULT = EntityId("vault")
CLOISTER = EntityId("cloister")
GROWN = EntityId("sub_crypt")

LEGAL = AdventureGrowth(
    changes=(Change(kind="gear", tag="Waxed Rope"),), why="he never climbs without it now"
)
ILLEGAL = AdventureGrowth(
    changes=(Change(kind="rewrite", tag="Never Held a Blade", into="Holds It Well"),),
    why="a tag the sheet does not carry",
)
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
        harness="code",
    )


def _harness(settings: Settings) -> Harness:
    return Harness(settings=settings, runtime=Runtime(settings))


def _opened(
    tmp_path: Path, engine: str, growth_frontier: int = 1
) -> tuple[Harness, FileStore, str]:
    harness = _harness(_settings(tmp_path, growth_frontier))
    slug = f"whispering-vault--kael--{engine}"
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

    assert "reveal" in {tool.name for tool in await harness.offered()}
    _ = await harness.call("start_turn", {"prompt": "I look around."})
    answered = await harness.call("reveal", {"entity_id": VAULT})

    assert "vault" in answered
    assert _saved(store, slug).world.require(VAULT).known


async def test_end_turn_records_the_exchange_and_bumps_the_turn(tmp_path: Path) -> None:
    harness, store, slug = _opened(tmp_path, "loner3e")

    _ = await harness.call("start_turn", {"prompt": "I look around."})
    _ = await harness.call(
        "end_turn",
        {"lines": [{"speaker_id": None, "text": "Dust hangs."}]},
    )

    saved = _saved(store, slug)
    assert saved.turn == 1
    assert saved.history[-1].prompt == "I look around."
    assert saved.history[-1].narration == "Dust hangs."


async def test_a_turn_with_neither_prose_nor_a_decision_is_refused(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")

    _ = await harness.call("start_turn", {"prompt": "I wait."})
    with pytest.raises(ModelRetry):
        _ = await harness.call("end_turn", {"lines": []})


async def test_no_tool_runs_a_turn_before_start_turn_opens_one(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")

    with pytest.raises(ModelRetry):
        _ = await harness.call("reveal", {"entity_id": VAULT})
    with pytest.raises(ModelRetry):
        _ = await harness.call("end_turn", {"lines": []})


async def test_an_open_decision_blocks_every_other_tool_until_it_is_answered(
    tmp_path: Path,
) -> None:
    """The whole suspension chain: a stake, its failed roll, and the hit settled in free text."""
    harness, store, slug = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)

    _ = await harness.call("start_turn", {"prompt": "I climb the shaft."})
    _ = await harness.call(
        "stake_attempt",
        {"attempt": {"actor_id": "player", "goal": "climb the shaft"}, "risk": "a long fall"},
    )
    assert _saved(store, slug).pending is not None
    with pytest.raises(ModelRetry):
        _ = await harness.call("reveal", {"entity_id": VAULT})
    _ = await harness.call(
        "end_turn", {"lines": [{"speaker_id": None, "text": "The shaft yawns."}]}
    )

    _ = await harness.call("start_turn", {"prompt": "I go on.", "option_id": "proceed"})
    pending = _saved(store, slug).pending
    assert pending is not None and pending.kind == "defence"
    # A free-text answer is the only way this decision closes, and it opens `settle_defence`.
    assert "settle_defence" not in {tool.name for tool in await harness.offered()}
    _ = await harness.call("end_turn", {"lines": [{"speaker_id": None, "text": "You slip."}]})

    _ = await harness.call("start_turn", {"prompt": "I take it on the shoulder"})
    assert "settle_defence" in {tool.name for tool in await harness.offered()}

    _ = await harness.call("settle_defence", {"item_id": None})
    assert _saved(store, slug).pending is None


async def test_a_viewer_in_another_process_picks_up_what_the_server_committed(
    tmp_path: Path,
) -> None:
    harness, _, slug = _opened(tmp_path, "loner3e")
    viewer = Runtime(harness.settings).session(
        LaunchTarget(slug=slug, scenario_id="whispering-vault", character_id="kael", engine=LONER3E)
    )
    assert viewer.state.turn == 0

    _ = await harness.call("start_turn", {"prompt": "I listen."})
    _ = await harness.call(
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
    _ = await harness.call("start_turn", {"prompt": "I climb the shaft."})
    _ = await harness.call(
        "stake_attempt",
        {"attempt": {"actor_id": "player", "goal": "climb the shaft"}, "risk": "a long fall"},
    )
    _ = await harness.call("end_turn", {"lines": [{"speaker_id": None, "text": "It yawns."}]})
    _ = await harness.call("start_turn", {"prompt": "I go on.", "option_id": "proceed"})
    _ = await harness.call("end_turn", {"lines": [{"speaker_id": None, "text": "You slip."}]})

    opened = await harness.call("start_turn", {"prompt": "I take it on the shoulder"})

    assert "paused play" in opened
    assert "paused play" in harness.scene()
    _ = await harness.call("settle_defence", {"item_id": None})
    _ = await harness.call("end_turn", {"lines": [{"speaker_id": None, "text": "You hold."}]})
    assert "paused play" not in harness.scene()


async def test_end_turn_says_growth_is_due_only_when_it_is(tmp_path: Path) -> None:
    """The server states it off committed state; the model never judges whether it is time."""
    harness, _, _ = _opened(tmp_path, "loner3e", growth_frontier=9)
    rested: dict[str, JsonValue] = {
        "lines": [{"speaker_id": None, "text": "Quiet settles."}],
    }

    _ = await harness.call("start_turn", {"prompt": "I rest."})
    assert "WORLD GROWTH DUE" not in await harness.call("end_turn", rested)

    session = harness.opened()
    session.scenario = updated(session.scenario, grows=True)
    _ = await harness.call("start_turn", {"prompt": "I rest."})
    assert "WORLD GROWTH DUE" in await harness.call("end_turn", rested)
    assert "WORLD GROWTH DUE" in harness.scene()


async def test_a_growth_run_lands_canon_the_player_has_still_to_find(tmp_path: Path) -> None:
    harness, store, slug = _growing(tmp_path)

    assert "scenario_so_far" in await harness.call("begin_growth", {})
    _ = await harness.call("write", {"patch": A_NEW_PLACE})
    _ = await harness.call("connect", {"from_id": CLOISTER, "to_id": GROWN})
    landed = await harness.call("finish_growth", {"summary": "A crypt below the cloister."})

    assert GROWN in landed
    world = _saved(store, slug).world
    assert not world.require(GROWN).known
    assert world.require(CLOISTER).exit_to(GROWN) is not None
    assert harness.authoring is None


async def test_a_draft_under_the_bar_is_refused_and_the_run_stays_open(tmp_path: Path) -> None:
    harness, _, _ = _growing(tmp_path)
    _ = await harness.call("begin_growth", {})
    _ = await harness.call("write", {"patch": A_NEW_PLACE})

    with pytest.raises(ModelRetry) as refused:
        _ = await harness.call("finish_growth", {"summary": "nowhere to reach it from"})

    assert "exit" in str(refused.value)
    assert harness.authoring is not None


async def test_authoring_needs_a_run_and_a_second_begin_discards_the_first(
    tmp_path: Path,
) -> None:
    harness, _, _ = _growing(tmp_path)
    with pytest.raises(ModelRetry):
        _ = await harness.call("scenario_so_far", {})

    _ = await harness.call("begin_growth", {})
    _ = await harness.call("write", {"patch": A_NEW_PLACE})
    _ = await harness.call("begin_growth", {})

    assert GROWN not in await harness.call("scenario_so_far", {})


async def test_opening_another_game_abandons_the_growth_run_of_the_first(tmp_path: Path) -> None:
    """Its patch is diffed against the game it began in, so it must not land in another."""
    harness, _, _ = _growing(tmp_path)
    _ = await harness.call("begin_growth", {})

    harness.open_game("whispering-vault--kael--twentyfourxx")

    assert harness.authoring is None


async def test_a_turn_tool_commits_as_usual_while_a_growth_run_is_open(tmp_path: Path) -> None:
    """The patch is additions-only, so play and authorship need no exclusion between them."""
    harness, store, slug = _growing(tmp_path)
    _ = await harness.call("begin_growth", {})

    _ = await harness.call("start_turn", {"prompt": "I look around."})
    _ = await harness.call("reveal", {"entity_id": VAULT})
    _ = await harness.call("write", {"patch": A_NEW_PLACE})
    _ = await harness.call("connect", {"from_id": CLOISTER, "to_id": GROWN})
    _ = await harness.call("finish_growth", {"summary": "A crypt below the cloister."})

    world = _saved(store, slug).world
    assert world.require(VAULT).known and not world.require(GROWN).known


async def test_an_id_the_game_took_meanwhile_reaches_the_author_at_finish(
    tmp_path: Path,
) -> None:
    """Builtin logs and drops the patch; here the driver is told, and can rename and re-finish."""
    harness, _, _ = _growing(tmp_path)
    _ = await harness.call("begin_growth", {})
    _ = await harness.call("write", {"patch": A_NEW_PLACE})
    _ = await harness.call("connect", {"from_id": CLOISTER, "to_id": GROWN})
    session = harness.opened()
    taken = Entity(id=GROWN, kind="location", name="the sub-crypt", brief="Taken first.")
    session.commit(with_entity(session.state, taken))

    with pytest.raises(ValueError):
        _ = await harness.call("finish_growth", {"summary": "A crypt below the cloister."})

    assert harness.authoring is not None


async def test_propose_advance_publishes_the_engines_own_proposal_schema(
    tmp_path: Path,
) -> None:
    harness = _harness(_settings(tmp_path))
    assert "propose_advance" not in {tool.name for tool in await harness.offered()}

    _ = harness.open_game("whispering-vault--kael--loner3e")

    published = next(one for one in await harness.offered() if one.name == "propose_advance")
    assert AdventureGrowth.__name__ in json.dumps(published.input_schema)


async def test_a_proposal_previews_and_only_apply_advance_commits_it(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")
    session = harness.opened()
    session.commit(at_boundary(session.state))
    asked: dict[str, JsonValue] = {
        "subject_id": PLAYER_ID,
        "proposal": LEGAL.model_dump(mode="json"),
    }

    previewed = await harness.call("propose_advance", asked)

    assert "Waxed Rope" in previewed
    assert "Waxed Rope" not in Mechanics.of_game(session.state).sheets[PLAYER_ID].gear
    _ = await harness.call("apply_advance", {})
    assert "Waxed Rope" in Mechanics.of_game(session.state).sheets[PLAYER_ID].gear


async def test_an_illegal_proposal_comes_back_with_the_engines_reason(tmp_path: Path) -> None:
    harness, _, _ = _opened(tmp_path, "loner3e")
    session = harness.opened()
    session.commit(at_boundary(session.state))

    with pytest.raises(ModelRetry) as refused:
        _ = await harness.call(
            "propose_advance",
            {"subject_id": PLAYER_ID, "proposal": ILLEGAL.model_dump(mode="json")},
        )

    assert "Never Held a Blade" in str(refused.value)
    assert session.drafted is None


async def test_a_scenario_run_writes_a_scenario_that_loads(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS, scenarios)
    harness = _harness(_settings(tmp_path, scenarios_dir=scenarios))

    briefing = await harness.call(
        "begin_scenario",
        {
            "slug": "sunken-mill",
            "premise": "A flooded mill hides a drowned bell.",
            "engines": [LONER3E],
            "grows": True,
        },
    )
    assert "finish_scenario" in briefing
    _ = await harness.call(
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
                    },
                ],
                "threads": [{"id": "the-bell", "title": "The drowned bell"}],
            }
        },
    )
    _ = await harness.call("connect", {"from_id": "millrace", "to_id": "wheelhouse"})

    written = await harness.call("finish_scenario", {"summary": "A mill and its wheelhouse."})

    assert "The Sunken Mill" in written
    assert load_scenario(scenarios, "sunken-mill").meta.title == "The Sunken Mill"
    assert harness.authoring is None


async def test_a_resume_that_re_suspended_may_still_develop_what_the_answer_caused(
    tmp_path: Path,
) -> None:
    """The same gate the builtin Director runs: core tools stay, engine tools do not."""
    harness, _, _ = _opened(tmp_path, "twentyfourxx")
    harness.opened().rng = Random(0)
    _ = await harness.call("start_turn", {"prompt": "I climb the shaft."})
    _ = await harness.call(
        "stake_attempt",
        {"attempt": {"actor_id": "player", "goal": "climb the shaft"}, "risk": "a long fall"},
    )
    _ = await harness.call(
        "end_turn", {"lines": [{"speaker_id": None, "text": "The shaft yawns."}]}
    )
    _ = await harness.call("start_turn", {"prompt": "I go on.", "option_id": "proceed"})

    offered = {tool.name for tool in await harness.offered()}
    assert "add_trait" in offered
    assert "roll_attempt" not in offered

    _ = await harness.call(
        "add_trait", {"entity_id": "player", "trait_id": "winded", "text": "Breath short."}
    )
    with pytest.raises(ModelRetry):
        _ = await harness.call(
            "roll_attempt", {"attempt": {"actor_id": "player", "goal": "swing again"}}
        )
