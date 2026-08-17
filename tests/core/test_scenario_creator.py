from types import NoneType

import pytest
from core_test_support import SCENARIOS, scenario, scripted, settings, text, updated
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from aidm.app.scenario_creator import (
    ScenarioPatch,
    WorldDraft,
    ask_until_playable,
    authored_world,
    playability,
    playtests,
    world_stage,
)
from aidm.content.store import load_scenario
from aidm.state.base import Entity, EntityId
from aidm.state.world import Relation, ScenarioMeta
from aidm.turn.roles import Stage


async def test_the_shipped_scenario_passes_every_engine() -> None:
    for playtest in playtests(settings()):
        shipped = load_scenario(SCENARIOS, "whispering-vault", playtest.engine.binding())
        playtest.check("whispering-vault", shipped.world, shipped.overlay)


def test_a_world_colliding_with_the_character_is_refused() -> None:
    for playtest in playtests(settings()):
        shipped = load_scenario(SCENARIOS, "whispering-vault", playtest.engine.binding())
        world = shipped.world
        # "lantern" is the id of the item the shipped character kael starts holding.
        extra = Entity(
            id=EntityId("lantern"),
            kind="item",
            name="a second lantern",
            brief="An identical lantern, left behind by whoever came before.",
            known=True,
            parent_id=world.starting_location_id,
        )
        colliding = updated(world, entities=(*world.entities, extra))
        with pytest.raises(ValueError, match="appears twice"):
            playtest.check("whispering-vault", colliding, shipped.overlay)


def _location(name: str) -> Entity:
    return Entity(id=EntityId(name), kind="location", name=name, brief=f"The {name}.", known=True)


def _finish(summary: str) -> ModelResponse:
    # `response` is the argument name pydantic-ai generates for `ToolOutput(str)`.
    return ModelResponse(parts=[ToolCallPart(tool_name="finish", args={"response": summary})])


def test_write_upserts_elements_by_id() -> None:
    draft = WorldDraft()
    confirmation = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            starting_location_id=EntityId("cell"),
            entities=(_location("cell"), _location("hall")),
            relations=(
                Relation(
                    kind="connected",
                    source=EntityId("cell"),
                    target=EntityId("hall"),
                    directed=False,
                ),
            ),
        )
    )
    assert "meta" in confirmation and "2 entities" in confirmation

    renamed = _location("cell").model_copy(update={"name": "the deep cell"})
    relocked = Relation(
        kind="connected",
        source=EntityId("hall"),
        target=EntityId("cell"),
        directed=False,
        tags=["locked"],
    )
    _ = draft.apply(ScenarioPatch(entities=(renamed,), relations=(relocked,)))

    assert draft.entities[EntityId("cell")].name == "the deep cell"
    # An undirected relation sorts its endpoints, so the rewrite hit the same id.
    assert [relation.tags for relation in draft.relations.values()] == [["locked"]]


def test_remove_drops_by_id_and_refuses_an_unknown_one() -> None:
    draft = WorldDraft()
    _ = draft.apply(ScenarioPatch(entities=(_location("cell"),)))
    assert draft.apply(ScenarioPatch(remove=(EntityId("cell"),))) == "wrote: removed 1"
    assert not draft.entities
    with pytest.raises(ValueError, match="nothing in the draft"):
        _ = draft.apply(ScenarioPatch(remove=("ghost",)))


def test_validation_names_what_the_draft_is_missing() -> None:
    empty = playability(WorldDraft(), "authored", ())
    assert empty is not None and "meta" in empty

    draft = WorldDraft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            starting_location_id=EntityId("nowhere"),
            entities=(_location("cell"),),
        )
    )
    dangling = playability(draft, "authored", ())
    assert dangling is not None and "nowhere" in dangling


def test_the_shipped_world_written_as_one_patch_is_playable() -> None:
    draft = WorldDraft()
    patch = ScenarioPatch.model_validate(scenario().world.model_dump(mode="json"))
    _ = draft.apply(patch)
    assert playability(draft, "authored", playtests(settings())) is None


async def test_the_agent_authors_through_the_write_tool() -> None:
    config = settings()
    playing = playtests(config)
    stage = world_stage("authored", playing, config)
    patch_args = {"patch": scenario().world.model_dump(mode="json")}
    author = scripted(
        ModelResponse(parts=[ToolCallPart(tool_name="write", args=patch_args)]),
        _finish("Authored the vault."),
    )
    with stage.agent.override(model=FunctionModel(author)):
        world = await authored_world(stage, "authored", "a vault", playing)
    assert world.meta.title == scenario().world.meta.title


async def test_finishing_an_unplayable_draft_is_refused_and_asked_again() -> None:
    """Were the first `finish` accepted, `authored_world`'s own post-run check would raise on the
    empty draft — so this passing pins both the refusal and the retry that authors for real."""
    config = settings()
    playing = playtests(config)
    stage = world_stage("authored", playing, config)
    patch_args = {"patch": scenario().world.model_dump(mode="json")}
    author = scripted(
        _finish("all done, and it is great"),
        ModelResponse(parts=[ToolCallPart(tool_name="write", args=patch_args)]),
        _finish("Authored the vault."),
    )
    with stage.agent.override(model=FunctionModel(author)):
        world = await authored_world(stage, "authored", "a vault", playing)
    assert world.meta.title == scenario().world.meta.title


def test_a_thin_draft_hears_every_unmet_bar_item_at_once() -> None:
    draft = WorldDraft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            starting_location_id=EntityId("cell"),
            entities=(_location("cell"),),
        )
    )
    reason = playability(draft, "authored", ())
    assert reason is not None
    for wanted in ("locations", "locked", "actors", "item", "thread", "hook"):
        assert wanted in reason


async def test_the_author_is_asked_again_with_the_reason() -> None:
    stage = Stage.of(
        "scenario_creator", settings(), instructions="", output_type=str, deps_type=NoneType
    )

    def check(answer: str) -> None:
        if answer != "yes":
            raise ValueError("wrong")

    with stage.agent.override(model=FunctionModel(scripted(text("no"), text("yes")))):
        result = await ask_until_playable(stage, "write it", check)

    assert result == "yes"


async def test_the_author_gives_up_after_every_round_is_refused() -> None:
    stage = Stage.of(
        "scenario_creator", settings(), instructions="", output_type=str, deps_type=NoneType
    )

    def check(answer: str) -> None:
        raise ValueError("wrong")

    scripted_model = FunctionModel(scripted(text("no"), text("no"), text("no")))
    with stage.agent.override(model=scripted_model):
        with pytest.raises(ValueError, match="wrong"):
            _ = await ask_until_playable(stage, "write it", check)
