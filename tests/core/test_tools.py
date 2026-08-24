from random import Random

from core_test_support import LONER3E, game
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import ToolsetTool
from pydantic_ai.usage import RunUsage

from aidm.engines.core import Engine, PlanContext, TurnLog
from aidm.state import actions
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.model import AdvanceThread, Game
from aidm.turn.run import core_toolset

MARA = EntityId("mara")
CLOISTER = EntityId("cloister")
VAULT_SEAL = "vault-seal"


async def _offered(engine: Engine, state: Game) -> dict[str, ToolsetTool[PlanContext]]:
    ctx = RunContext(
        deps=PlanContext(engine=engine, state=state, rng=Random(0), log=TurnLog()),
        model=TestModel(),
        usage=RunUsage(),
    )
    return await core_toolset().get_tools(ctx)


async def test_applicability_tracks_the_draft() -> None:
    engine, state = game(LONER3E)
    offered = await _offered(engine, state)
    assert "move" in offered
    assert "leave_party" not in offered

    draft = state.draft()
    actions.join_party(draft, MARA)

    assert "leave_party" in await _offered(engine, draft.committed())


async def test_a_thread_put_dormant_can_still_be_moved() -> None:
    engine, state = game(LONER3E)
    draft = state.draft()
    _ = actions.advance_thread(draft, AdvanceThread(thread_id=VAULT_SEAL, status="dormant"))

    assert "advance_thread" in await _offered(engine, draft.committed())


async def test_unlock_exit_narrows_to_id_to_the_locked_ways_out() -> None:
    engine, state = game(LONER3E)
    draft = state.draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)

    tools = await _offered(engine, draft.committed())
    schema = tools["unlock_exit"].tool_def.parameters_json_schema

    assert schema["properties"]["to_id"]["enum"] == ["vault"]
