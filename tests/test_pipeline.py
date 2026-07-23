"""Full pipeline runs with every role stubbed — no network."""

import json
from collections.abc import Callable
from contextlib import ExitStack

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.agents import actor, creator, director, maintainer, narrator
from aidm.domain.models import GameState
from aidm.pipeline import run_turn

Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]
ROLE_MODULES = (director, actor, narrator, maintainer, creator)
DIRECTION = {"guidance": "wisdom DC 12; on success they find the vault map", "tone": "hushed"}


def structured(**output: object) -> Stub:
    """Structured roles use NativeOutput, so the model replies with schema-shaped JSON text."""

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(output))])

    return stub


def text(body: str) -> Stub:
    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(body)])

    return stub


def tools(*calls: tuple[str, dict[str, object]], report: str = "done") -> Stub:
    """Issue `calls` one at a time; a rejected call counts as answered, so retries advance."""

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        answered = sum(
            isinstance(part, ToolReturnPart | RetryPromptPart)
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
        )
        if answered < len(calls):
            name, args = calls[answered]
            return ModelResponse(parts=[ToolCallPart(name, args)])
        return ModelResponse(parts=[TextPart(report)])

    return stub


def stubs(stack: ExitStack, **roles: Stub) -> None:
    by_name = {m.__name__.rsplit(".", 1)[1]: m for m in ROLE_MODULES}
    for name, stub in roles.items():
        stack.enter_context(by_name[name].agent().override(model=FunctionModel(stub)))


async def test_search_applies_mechanics_and_creates_nothing(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(**DIRECTION),
            actor=tools(
                ("ability_check", {"ability": "wisdom", "dc": 12}),
                ("modify_inventory", {"item": "vault_map", "delta": 1}),  # an id, not the name
            ),
            narrator=text("Your fingers find a creased chart beneath the flagstone."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "I search the study.")

    # gaining a canon item reveals it: inventory and canon can never disagree
    kinds = [e.type for e in turn.events]
    assert kinds == ["check_rolled", "entity_discovered", "inventory_changed"]
    assert turn.state.character.inventory == ["a lantern", "the vault map"]
    assert {e.id for e in turn.state.scenario.entities if e.known} == {"mara", "vault_map"}
    assert turn.created == []
    assert turn.state.turn == 1
    assert turn.state.history[-1].prompt == "I search the study."


async def test_existing_canon_is_revealed_not_created(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(guidance="Mara points to Elena.", tone="wary", speaker_id="mara"),
            actor=tools(("discover_entity", {"name": "Elena"})),
            narrator=text("'Elena would know,' Mara says."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "@Mara who can I ask for help?")

    assert {e.id for e in turn.state.scenario.entities if e.known} == {"mara", "elena"}
    assert len(turn.state.scenario.entities) == 3


async def test_an_invented_name_is_rejected_then_grown(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(guidance="Nobody in canon fits.", tone="dry"),
            actor=tools(("discover_entity", {"name": "Elgin"})),  # not in canon: must be refused
            narrator=text("'Try Elgin, the apothecary by the east gate,' he mutters."),
            maintainer=structured(
                requests=[{"kind": "npc", "name": "Elgin", "brief": "An apothecary."}]
            ),
            creator=structured(description="A stooped herbalist.", hook="He trades in rumours."),
        )
        turn = await run_turn(state, "@Tomas who can I ask for help?")

    assert turn.events == []  # the Actor invented a name and the tool refused it
    (elgin,) = turn.created
    assert (elgin.id, elgin.known, elgin.authored) == ("elgin", True, False)
    assert turn.state.scenario.entities[-1] == elgin
    assert turn.state.scenario.entities[1].known is False  # authored canon untouched by growth


async def test_growth_is_capped(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(guidance="A crowd.", tone="busy"),
            actor=tools(),
            narrator=text("Names fly past you."),
            maintainer=structured(
                requests=[{"kind": "npc", "name": f"N{i}", "brief": "b"} for i in range(6)]
            ),
            creator=structured(description="d", hook="h"),
        )
        turn = await run_turn(state, "Who is here?")

    assert len(turn.created) == 3


async def test_failing_role_leaves_state_untouched(state: GameState) -> None:
    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("narrator exploded")

    before = state.model_dump_json()
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(guidance="anything", tone="grim"),
            actor=tools(("modify_hp", {"delta": -3})),
            narrator=boom,
        )
        with pytest.raises(RuntimeError):
            await run_turn(state, "I kick the door.")

    assert state.model_dump_json() == before
