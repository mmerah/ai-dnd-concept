"""Full pipeline runs with every role stubbed — no network."""

import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.agents import creator, director, maintainer, narrator
from aidm.agents.director import DirectorDeps, direct
from aidm.agents.history import exchanges_to_messages
from aidm.domain.models import Exchange, GameState
from aidm.pipeline import run_turn

Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]
ROLE_MODULES = (director, narrator, maintainer, creator)


def structured(**output: object) -> Stub:
    """Structured roles use NativeOutput, so the model replies with schema-shaped JSON text."""

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(output))])

    return stub


def text(body: str) -> Stub:
    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(body)])

    return stub


def stubs(stack: ExitStack, **roles: Stub) -> None:
    by_name = {m.__name__.rsplit(".", 1)[1]: m for m in ROLE_MODULES}
    for name, stub in roles.items():
        stack.enter_context(by_name[name].agent().override(model=FunctionModel(stub)))


async def test_search_applies_mechanics_and_creates_nothing(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Kael feels along the flagstone for the vault map.",
                tone="hushed",
                plan={
                    "check": {"ability": "wisdom", "dc": 12},
                    "on_success": [{"action": "gain_canon_item", "entity_id": "vault_map"}],
                },
            ),
            narrator=text("Your fingers find a creased chart beneath the flagstone."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "I search the study.", rng=Random(0))  # roll 13 + 2 >= 12

    # gaining a canon item reveals it: inventory and canon can never disagree
    kinds = [e.type for e in turn.events]
    assert kinds == ["check_rolled", "entity_discovered", "inventory_changed"]
    assert turn.state.character.inventory == ["a lantern", "the vault map"]
    assert {e.id for e in turn.state.world.entities if e.known} == {"mara", "vault_map"}
    assert turn.created == []
    assert turn.state.turn == 1
    assert turn.state.history[-1].prompt == "I search the study."


async def test_existing_canon_is_revealed_not_created(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Mara points Kael toward Elena.",
                tone="wary",
                speaker_id="mara",
                plan={"on_success": [{"action": "discover", "entity_id": "elena"}]},
            ),
            narrator=text("'Elena would know,' Mara says."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "@Mara who can I ask for help?")

    assert {e.id for e in turn.state.world.entities if e.known} == {"mara", "elena"}
    assert len(turn.state.world.entities) == 3


async def test_an_unbacked_name_is_grown_not_resolved(state: GameState) -> None:
    """The Director cannot reference an id it was never shown, so a name only the Narrator invents
    changes nothing mechanically and is grown into canon by the Maintainer instead."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Nobody in canon fits; Kael must look elsewhere.", tone="dry"
            ),
            narrator=text("'Try Elgin, the apothecary by the east gate,' he mutters."),
            maintainer=structured(
                requests=[{"kind": "npc", "name": "Elgin", "brief": "An apothecary."}]
            ),
            creator=structured(description="A stooped herbalist.", hook="He trades in rumours."),
        )
        turn = await run_turn(state, "@Tomas who can I ask for help?")

    assert turn.events == []  # an empty plan resolves to nothing
    (elgin,) = turn.created
    assert (elgin.id, elgin.known, elgin.authored) == ("elgin", True, False)
    assert turn.state.world.entities[-1] == elgin
    assert turn.state.world.entities[1].known is False  # authored canon untouched by growth


async def test_growth_is_capped(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(intent="A crowd presses in.", tone="busy"),
            narrator=text("Names fly past you."),
            maintainer=structured(
                requests=[{"kind": "npc", "name": f"N{i}", "brief": "b"} for i in range(6)]
            ),
            creator=structured(description="d", hook="h"),
        )
        turn = await run_turn(state, "Who is here?")

    assert len(turn.created) == 3


async def test_a_plan_with_an_unknown_id_is_rejected(state: GameState) -> None:
    """The Director's output validator relocates the Actor's per-tool ModelRetry to id selection."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="i",
                tone="t",
                plan={"on_success": [{"action": "discover", "entity_id": "ghost"}]},
            ),
        )
        with pytest.raises(UnexpectedModelBehavior):
            await direct("go", DirectorDeps(entities=state.world.entities))


def test_exchanges_become_alternating_messages() -> None:
    messages = exchanges_to_messages(
        [Exchange(prompt="I open the door.", narration="It creaks wide.")]
    )
    assert [type(m) for m in messages] == [ModelRequest, ModelResponse]


async def test_failing_role_leaves_state_untouched(state: GameState) -> None:
    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("narrator exploded")

    before = state.model_dump_json()
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="anything",
                tone="grim",
                plan={"unconditional": [{"action": "modify_hp", "delta": -3}]},
            ),
            narrator=boom,
        )
        with pytest.raises(RuntimeError):
            await run_turn(state, "I kick the door.")

    assert state.model_dump_json() == before
