from random import Random

from core_test_support import LONER3E, game
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from aidm.engines.core import PlanContext, TurnLog
from aidm.state import actions
from aidm.state.model import PLAYER_ID, AdvanceThread, EntityId
from aidm.turn.run import core_toolset, possible

MARA = EntityId("mara")
CLOISTER = EntityId("cloister")
VAULT_SEAL = "vault-seal"


def test_possible_tracks_the_draft() -> None:
    _, state = game(LONER3E)
    assert possible("move", state) is True
    assert possible("leave_party", state) is False

    draft = state.draft()
    actions.join_party(draft, MARA)
    state = draft.committed()

    assert possible("leave_party", state) is True


def test_a_thread_put_dormant_can_still_be_moved() -> None:
    _, state = game(LONER3E)
    draft = state.draft()
    _ = actions.advance_thread(draft, AdvanceThread(thread_id=VAULT_SEAL, status="dormant"))

    assert possible("advance_thread", draft.committed()) is True


async def test_unlock_exit_narrows_to_id_to_the_locked_ways_out() -> None:
    engine, state = game(LONER3E)
    draft = state.draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)
    state = draft.committed()
    ctx = RunContext(
        deps=PlanContext(engine=engine, state=state, rng=Random(0), log=TurnLog()),
        model=TestModel(),
        usage=RunUsage(),
    )

    tools = await core_toolset().get_tools(ctx)
    schema = tools["unlock_exit"].tool_def.parameters_json_schema

    assert schema["properties"]["to_id"]["enum"] == ["vault"]
