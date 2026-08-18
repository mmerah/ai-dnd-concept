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

from aidm.content.sources import (
    SILENT,
    ExtendedSource,
    PremiseSource,
    RecordSource,
    SourceRecord,
)
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
DOCUMENT = RecordSource(
    records=(
        SourceRecord(
            id="p1-1",
            text=(
                "Below the cloister the undercroft runs on into flooded galleries nobody "
                "has walked."
            ),
        ),
        SourceRecord(id="p2-1", text="Marsh light bewilders anyone crossing at dusk."),
    )
)
# Nothing in it shares a word with the anchor or the need below, so every search of it misses.
UNHELPFUL = RecordSource(records=DOCUMENT.records[1:])
# No `directed`: `connected` is walked both ways, and the resolver settles that from the kind.
WAY = {"kind": "connected", "source": "cloister", "target": "sunken_gallery"}
DOWNWARD = "I follow the stair down past the cloister."


def _tool_call(name: str, **args: object) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=name, args=json.dumps(args))])


def _unreachable(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del messages, info
    raise AssertionError("the Expander was called for a need the source holds nothing on")


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
    # A premise holds no records to search, so it reaches the Expander whole, as it always did.
    assert "galleries nobody has walked" in shown(result.turn, "expander-1")


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
    # The turn wrote no canon, so its trace is the only record of what was asked and why it failed.
    refusal = next(step for step in result.turn.steps if step.name == "expander-1")
    assert "a way down" in (refusal.prompt or "")
    assert isinstance(refusal.output, str) and "no canon written" in refusal.output


async def test_a_grounded_expansion_is_shown_the_passages_the_director_asked_for() -> None:
    """The source is searched by resolver code, so the Expander answers once, from the records the
    Director's own terms retrieved and nothing else."""
    engine, state = initialized()
    director = FunctionModel(
        scripted(
            _tool_call(
                "expand_world",
                kind="location",
                anchor_id="cloister",
                need="the place the stair below the cloister descends to",
                queries=["undercroft", "flooded galleries"],
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
        # One answer: nothing about the source can refuse a patch, so nothing costs a retry.
        expander=FunctionModel(scripted(structured(entities=[GALLERY], relations=[WAY]))),
        source=DOCUMENT,
        narrator=FunctionModel(scripted(text("Water closes over your boots."))),
    )

    world = result.state.world
    assert world.require(EntityId("sunken_gallery")).known
    assert result.state.player.parent_id == "sunken_gallery"
    asked = shown(result.turn, "expander-1")
    assert "[p1-1]" in asked and "undercroft" in asked
    assert "bewilders" not in asked
    assert "undercroft" not in shown(result.turn, "narrator")


async def test_a_grounded_miss_refuses_the_director_and_never_calls_the_expander() -> None:
    """Strict grounding has nothing to write from on a retrieval miss, so it says so instead of
    handing the Expander passages that bear on nothing."""
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
        expander=FunctionModel(_unreachable),
        source=UNHELPFUL,
    )

    assert not [step for step in result.turn.steps if step.name.startswith("expander")]
    assert result.state.player.parent_id == "cloister"


async def test_an_extended_source_falls_back_to_the_premise_and_says_it_is_doing_so() -> None:
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
        expander=FunctionModel(scripted(structured(entities=[GALLERY], relations=[WAY]))),
        source=ExtendedSource(document=UNHELPFUL, premise=FRONTIER.text),
    )

    asked = shown(result.turn, "expander-1")
    assert SILENT in asked
    assert "galleries nobody has walked" in asked
    assert result.state.world.find(EntityId("sunken_gallery")) is not None


def test_a_closed_adventure_leaves_the_director_the_agent_it_ships_with() -> None:
    engine, _ = initialized()

    closed = build_stages(engine, settings())
    opened = build_stages(engine, settings(), FRONTIER)

    assert (closed.expander, tuple(closed.director.toolsets)) == (None, ())
    assert opened.expander is not None and len(opened.director.toolsets) == 1
