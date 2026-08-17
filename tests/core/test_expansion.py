import json

from core_test_support import (
    Stub,
    call,
    initialized,
    plan,
    played,
    scripted,
    settings,
    shown,
    structured,
    text,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.content.sources import PremiseSource
from aidm.state.base import EntityId
from aidm.turn.roles import build_stages

FRONTIER = PremiseSource(
    text="Below the abbey cloister the undercroft runs on into galleries nobody has walked."
)
GALLERY = {
    "id": "sunken_gallery",
    "kind": "location",
    "name": "The Sunken Gallery",
    "brief": "A flooded arcade of drowned pillars beneath the cloister.",
}
WATCHER = {
    "id": "gallery_watcher",
    "kind": "actor",
    "name": "Sister Verrin",
    "brief": "A drowned sister who never left her post.",
    "parent_id": "sunken_gallery",
}
WAY = {"kind": "connected", "source": "cloister", "target": "sunken_gallery", "directed": False}
DOWNWARD = "I follow the stair down past the cloister."


def _tool_call(name: str, **args: object) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=name, args=json.dumps(args))])


def _always(response: ModelResponse) -> Stub:
    """The Expander's own retries are what this drives, so the answer never runs out."""

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return response

    return stub


async def test_travel_beyond_the_frontier_expands_the_world_inside_one_turn() -> None:
    """The vertical slice: canon materializes mid-plan, the Director walks the player into it, and
    what it did not reveal never reaches the Narrator."""
    engine, state = initialized()
    director = FunctionModel(
        scripted(
            _tool_call(
                "expand_world",
                kind="location",
                anchor_id="cloister",
                need="the place the stair below the cloister descends to",
            ),
            plan(
                effects=[
                    call("move", to_id="cloister"),
                    call(
                        "relation-change",
                        mode="reveal",
                        kind="connected",
                        source="cloister",
                        target="sunken_gallery",
                    ),
                    call("move", to_id="sunken_gallery"),
                ]
            ),
        )
    )
    result = await played(
        engine,
        state,
        DOWNWARD,
        director=director,
        expander=FunctionModel(scripted(structured(entities=[GALLERY, WATCHER], relations=[WAY]))),
        source=FRONTIER,
        narrator=FunctionModel(scripted(text("Water closes over your boots."))),
    )

    world = result.state.world
    assert result.state.player.parent_id == "sunken_gallery"
    assert world.require(EntityId("sunken_gallery")).known
    assert [step.name for step in result.turn.steps] == [
        "director",
        "expander-1",
        "resolve",
        "hooks",
        "narrator",
        "worldkeeper",
    ]
    # Materializing private canon is not a fictional event, and the Director revealed only the way.
    assert not world.require(EntityId("gallery_watcher")).known
    assert "Verrin" not in shown(result.turn, "narrator")
    materialized = [fact for fact in result.turn.facts if fact.kind == "canon_materialized"]
    assert materialized and all(fact.narrator is None for fact in materialized)


async def test_an_expander_that_cannot_write_costs_only_its_own_tool_call() -> None:
    engine, state = initialized()
    director = FunctionModel(
        scripted(
            _tool_call("expand_world", kind="location", anchor_id="cloister", need="a way down"),
            plan(effects=[call("move", to_id="cloister")]),
        )
    )
    result = await played(
        engine,
        state,
        DOWNWARD,
        director=director,
        # An id the world already holds: refused every round, so the Expander exhausts its retries.
        expander=FunctionModel(_always(structured(entities=[{**GALLERY, "id": "vault"}]))),
        source=FRONTIER,
    )

    assert result.state.player.parent_id == "cloister"
    assert not [fact for fact in result.turn.facts if fact.kind == "canon_materialized"]
    assert result.state.world.require(EntityId("vault")).name == "the sealed vault"


def test_a_closed_adventure_leaves_the_director_the_agent_it_ships_with() -> None:
    engine, _ = initialized()

    closed = build_stages(engine, settings())
    opened = build_stages(engine, settings(), FRONTIER)

    assert (closed.expander, tuple(closed.director.toolsets)) == (None, ())
    assert opened.expander is not None and len(opened.director.toolsets) == 1
