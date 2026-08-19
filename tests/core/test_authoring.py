from types import NoneType

import pytest
from core_test_support import SCENARIOS, scenario, scripted, settings, text, updated
from pydantic import JsonValue
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from aidm.app.authoring.agents import ask_until_playable
from aidm.app.authoring.draft import ScenarioPatch, WorldDraft
from aidm.app.authoring.playability import OPENING, playability, playtests
from aidm.app.authoring.session import AuthoringSession
from aidm.content.store import load_scenario
from aidm.llm import build_agent
from aidm.state.base import Entity, EntityId
from aidm.state.world import Relation, ScenarioMeta, Thread


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


def _as_patch() -> dict[str, JsonValue]:
    """The shipped world as one write: `expansion` is the session's to set, never the author's,
    so no patch carries it."""
    body = scenario().world.model_dump(mode="json")
    del body["expansion"]
    return body


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
        locked=True,
    )
    _ = draft.apply(ScenarioPatch(entities=(renamed,), relations=(relocked,)))

    assert draft.entities[EntityId("cell")].name == "the deep cell"
    # An undirected relation sorts its endpoints, so the rewrite hit the same id.
    assert [relation.locked for relation in draft.relations.values()] == [True]


def test_a_patched_art_style_reaches_the_world() -> None:
    draft = WorldDraft()
    _ = draft.apply(ScenarioPatch.model_validate(_as_patch() | {"art_style": "ink-wash noir"}))
    assert draft.world().art_style == "ink-wash noir"


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
    patch = ScenarioPatch.model_validate(_as_patch())
    _ = draft.apply(patch)
    assert playability(draft, "authored", playtests(settings())) is None


async def test_the_agent_authors_through_the_write_tool() -> None:
    config = settings()
    session = AuthoringSession(
        slug="authored", premise="a vault", config=config, expansion="closed"
    )
    author = scripted(
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
    assert session.draft.world().meta.title == scenario().world.meta.title


async def test_finishing_an_unplayable_draft_is_refused_and_asked_again() -> None:
    """This pins the output validator's own retry: an empty draft's `finish` is refused and the
    author is asked again in the same run. Post-run revalidation lives in `write()`, not here."""
    config = settings()
    session = AuthoringSession(
        slug="authored", premise="a vault", config=config, expansion="closed"
    )
    author = scripted(
        _finish("all done, and it is great"),
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
    assert session.draft.world().meta.title == scenario().world.meta.title


async def test_a_session_goes_on_authoring_after_it_finishes() -> None:
    config = settings()
    session = AuthoringSession(
        slug="authored", premise="a vault", config=config, expansion="closed"
    )
    addition = ScenarioPatch(
        entities=(_location("belfry"),),
        relations=(
            Relation(
                kind="connected",
                source=EntityId("study"),
                target=EntityId("belfry"),
                known=True,
            ),
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
    assert EntityId("belfry") in session.draft.entities
    assert len(session.history) > before


async def test_an_unplayable_draft_is_never_written() -> None:
    session = AuthoringSession(
        slug="authored", premise="a vault", config=settings(), expansion="closed"
    )
    with pytest.raises(ValueError, match="does not play"):
        _ = await session.write()


def test_a_cited_session_needs_a_document() -> None:
    with pytest.raises(ValueError, match="document"):
        AuthoringSession(slug="authored", premise="a vault", config=settings(), expansion="cited")


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


def test_an_opening_slice_passes_a_bar_the_whole_scenario_would_fail() -> None:
    """Premise-start authors the first scene and nothing else: the rest is written during play."""
    draft = WorldDraft(expansion="invented")
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
    playing = playtests(settings())

    assert playability(draft, "authored", playing, OPENING) is None
    assert playability(draft, "authored", playing) is not None
    assert draft.world().expansion == "invented"


async def test_the_author_is_asked_again_with_the_reason() -> None:
    agent = build_agent(
        "scenario_creator", settings(), instructions="", output_type=str, deps_type=NoneType
    )

    def check(answer: str) -> None:
        if answer != "yes":
            raise ValueError("wrong")

    with agent.override(model=FunctionModel(scripted(text("no"), text("yes")))):
        result = await ask_until_playable(agent, "write it", check)

    assert result == "yes"


async def test_the_author_gives_up_after_every_round_is_refused() -> None:
    agent = build_agent(
        "scenario_creator", settings(), instructions="", output_type=str, deps_type=NoneType
    )

    def check(answer: str) -> None:
        raise ValueError("wrong")

    scripted_model = FunctionModel(scripted(text("no"), text("no"), text("no")))
    with agent.override(model=scripted_model):
        with pytest.raises(ValueError, match="wrong"):
            _ = await ask_until_playable(agent, "write it", check)
