import pytest
from core_test_support import SCENARIOS, scenario, scripted, settings, updated
from pydantic import JsonValue
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from aidm.app.authoring.draft import ScenarioPatch, WorldDraft
from aidm.app.authoring.playability import OPENING, playability, playtests
from aidm.app.authoring.session import AuthoringSession
from aidm.app.registry import engine_ids
from aidm.content.store import load_scenario
from aidm.state.model import Entity, EntityId, Exit, ScenarioMeta, Thread


async def test_the_shipped_scenario_passes_every_engine() -> None:
    shipped = load_scenario(SCENARIOS, "whispering-vault")
    for playtest in playtests(settings(), engine_ids()):
        playtest.check(shipped)


def test_a_world_colliding_with_the_character_is_refused() -> None:
    shipped = load_scenario(SCENARIOS, "whispering-vault")
    # "lantern" is the id of the item the shipped character kael starts holding.
    extra = Entity(
        id=EntityId("lantern"),
        kind="item",
        name="a second lantern",
        brief="An identical lantern, left behind by whoever came before.",
        known=True,
        parent_id=shipped.starting_location_id,
    )
    colliding = updated(
        shipped, world=updated(shipped.world, entities=(*shipped.world.entities, extra))
    )
    for playtest in playtests(settings(), engine_ids()):
        with pytest.raises(ValueError, match="appears twice"):
            playtest.check(colliding)


def _as_patch() -> dict[str, JsonValue]:
    """The shipped scenario as `worked_example` teaches it, without the session's `grows`."""
    return WorldDraft.of(scenario()).model_dump(mode="json", exclude={"grows"})


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
            entities=(
                _location("cell").model_copy(update={"exits": [Exit(to=EntityId("hall"))]}),
                _location("hall"),
            ),
        )
    )
    assert "set meta" in confirmation
    assert "created location cell[cell]" in confirmation
    assert "created location hall[hall]" in confirmation

    renamed = _location("cell").model_copy(
        update={"name": "the deep cell", "exits": [Exit(to=EntityId("hall"), locked=True)]}
    )
    modification = draft.apply(ScenarioPatch(entities=(renamed,)))
    assert modification == "modified location the deep cell[cell]"

    cell = next(entity for entity in draft.entities if entity.id == EntityId("cell"))
    assert cell.name == "the deep cell"
    assert cell.exits == [Exit(to=EntityId("hall"), locked=True)]


def test_a_patched_art_style_reaches_the_scenario() -> None:
    draft = WorldDraft()
    _ = draft.apply(ScenarioPatch.model_validate(_as_patch() | {"art_style": "ink-wash noir"}))
    assert draft.scenario(engine_ids()).art_style == "ink-wash noir"


def test_remove_drops_by_id_and_refuses_an_unknown_one() -> None:
    draft = WorldDraft()
    _ = draft.apply(ScenarioPatch(entities=(_location("cell"),)))
    deletion = draft.apply(ScenarioPatch(remove=(EntityId("cell"),)))
    assert deletion == "deleted location cell[cell]"
    assert not draft.entities
    with pytest.raises(ValueError, match="nothing in the draft"):
        _ = draft.apply(ScenarioPatch(remove=("ghost",)))


def test_validation_names_what_the_draft_is_missing() -> None:
    playing = playtests(settings(), engine_ids())
    empty = playability(WorldDraft(), playing)
    assert empty is not None and "meta" in empty

    draft = WorldDraft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            starting_location_id=EntityId("nowhere"),
            entities=(_location("cell"),),
        )
    )
    dangling = playability(draft, playing)
    assert dangling is not None and "nowhere" in dangling


def test_the_shipped_world_written_as_one_patch_is_playable() -> None:
    draft = WorldDraft()
    patch = ScenarioPatch.model_validate(_as_patch())
    _ = draft.apply(patch)
    assert playability(draft, playtests(settings(), engine_ids())) is None


async def test_the_agent_authors_through_the_write_tool() -> None:
    config = settings()
    session = AuthoringSession(
        slug="authored", premise="a vault", config=config, grows=False, engines=engine_ids()
    )
    author = scripted(
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
    assert session.draft.scenario(engine_ids()).meta.title == scenario().meta.title


async def test_finishing_an_unplayable_draft_is_refused_and_asked_again() -> None:
    """This pins the output validator's own retry: an empty draft's `finish` is refused and the
    author is asked again in the same run. Post-run revalidation lives in `write()`, not here."""
    config = settings()
    session = AuthoringSession(
        slug="authored", premise="a vault", config=config, grows=False, engines=engine_ids()
    )
    author = scripted(
        _finish("all done, and it is great"),
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
    assert session.draft.scenario(engine_ids()).meta.title == scenario().meta.title


async def test_a_session_goes_on_authoring_after_it_finishes() -> None:
    config = settings()
    session = AuthoringSession(
        slug="authored", premise="a vault", config=config, grows=False, engines=engine_ids()
    )
    study = next(entity for entity in scenario().world.entities if entity.id == EntityId("study"))
    addition = ScenarioPatch(
        entities=(
            _location("belfry"),
            study.model_copy(update={"exits": [*study.exits, Exit(to=EntityId("belfry"))]}),
        ),
    )
    author = scripted(
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="write", args={"patch": addition.model_dump(mode="json")})
            ]
        ),
        _finish("Added the bell tower."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
        assert session.refusal() is None
        before = len(session.history)
        _ = await session.send("add a bell tower")
    assert EntityId("belfry") in {entity.id for entity in session.draft.entities}
    assert len(session.history) > before


async def test_an_unplayable_draft_is_never_written() -> None:
    session = AuthoringSession(
        slug="authored",
        premise="a vault",
        config=settings(),
        grows=False,
        engines=engine_ids(),
    )
    with pytest.raises(ValueError, match="does not play"):
        _ = await session.write()


def test_a_thin_draft_hears_every_unmet_bar_item_at_once() -> None:
    draft = WorldDraft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            starting_location_id=EntityId("cell"),
            entities=(_location("cell"),),
        )
    )
    reason = playability(draft, playtests(settings(), engine_ids()))
    assert reason is not None
    for wanted in ("locations", "locked", "actors", "item", "thread", "when_reached"):
        assert wanted in reason


def test_an_opening_slice_passes_a_bar_the_whole_scenario_would_fail() -> None:
    """Premise-start authors the first scene and nothing else: the rest is written during play."""
    draft = WorldDraft(grows=True)
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            starting_location_id=EntityId("cell"),
            entities=(
                _location("cell"),
                Entity(
                    id=EntityId("gaoler"),
                    kind="actor",
                    name="the gaoler",
                    brief="He keeps the only key.",
                    known=True,
                    parent_id=EntityId("cell"),
                ),
                Entity(
                    id=EntityId("loose_stone"),
                    kind="item",
                    name="a loose stone",
                    brief="It grinds when the wall is leaned on.",
                    parent_id=EntityId("cell"),
                ),
            ),
            threads=(Thread(id="the-way-out", title="The way out", stage="barred"),),
        )
    )
    playing = playtests(settings(), engine_ids())

    assert playability(draft, playing, OPENING) is None
    assert playability(draft, playing) is not None
    assert draft.scenario(engine_ids()).grows
