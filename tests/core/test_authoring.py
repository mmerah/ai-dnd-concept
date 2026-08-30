from collections.abc import Sequence

import pytest
from core_test_support import (
    ENGINE_IDS,
    ENGINES_BUILT,
    LONER3E,
    SCENARIOS,
    offline_settings,
    recorded,
    scenario,
    scenario_for,
    scripted,
    updated,
)
from pydantic import JsonValue
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from aidm.authoring.draft import (
    Draft,
    ScenarioPatch,
    patch_refusal,
    playtest_check,
    scenario_refusal,
)
from aidm.authoring.run import scenario_agent, scenario_run
from aidm.content.io import load_scenario, read_scenarios
from aidm.content.model import AuthoringBrief
from aidm.state.entities import Entity, EntityId, Exit
from aidm.state.model import ScenarioMeta, Thread, WorldState
from aidm.world.authoring import Connect, connect

ENGINE = ENGINES_BUILT[LONER3E]
SRD = ("srd",)


def _brief(base: WorldState | None = None, opening: bool = False) -> AuthoringBrief:
    return ENGINE.authoring_brief(SRD, base, opening)


async def test_every_shipped_scenario_passes_the_engine_it_is_authored_for() -> None:
    for _, shipped in read_scenarios(SCENARIOS, ENGINE_IDS):
        playtest_check(offline_settings(), ENGINES_BUILT[shipped.engine], shipped.packs).check(
            shipped
        )


def test_a_world_colliding_with_the_character_is_refused() -> None:
    for engine_id in ENGINE_IDS:
        playing = playtest_check(offline_settings(), ENGINES_BUILT[engine_id])
        shipped = load_scenario(SCENARIOS, scenario_for(engine_id))
        held = playing.character.items[0]
        extra = Entity(
            id=held.id,
            kind="item",
            name=f"a second {held.name}",
            brief="An identical one, left behind by whoever came before.",
            known=True,
            parent_id=shipped.player_parent_id,
        )
        colliding = updated(
            shipped,
            world=updated(shipped.world, entities={**shipped.world.entities, extra.id: extra}),
        )
        with pytest.raises(ValueError, match="appears twice"):
            playing.check(colliding)


def test_authoring_refuses_an_uninstalled_pack() -> None:
    with pytest.raises(ValueError, match="not installed"):
        _ = scenario_run(
            offline_settings(),
            ENGINE,
            "authored",
            "a vault",
            False,
            None,
            packs=("srd", "missing"),
        )


def _as_patch() -> dict[str, JsonValue]:
    return Draft.from_scenario(scenario()).as_patch().model_dump(mode="json")


def _location(name: str) -> Entity:
    return Entity(id=EntityId(name), kind="location", name=name, brief=f"The {name}.", known=True)


def _finish(summary: str) -> ModelResponse:
    # `response` is the argument name pydantic-ai generates for `ToolOutput(str)`.
    return ModelResponse(parts=[ToolCallPart(tool_name="finish", args={"response": summary})])


def test_write_upserts_elements_by_id() -> None:
    draft = Draft()
    confirmation = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            player_parent_id=EntityId("cell"),
            entities=(
                _location("cell").model_copy(update={"exits": [Exit(to=EntityId("hall"))]}),
                _location("hall"),
            ),
        ),
        ENGINE,
    )
    assert "set meta" in confirmation
    assert "created location cell[cell]" in confirmation
    assert "created location hall[hall]" in confirmation

    renamed = _location("cell").model_copy(
        update={"name": "the deep cell", "exits": [Exit(to=EntityId("hall"), locked=True)]}
    )
    modification = draft.apply(ScenarioPatch(entities=(renamed,)), ENGINE)
    assert modification == "modified location the deep cell[cell]"

    cell = draft.world.entities[EntityId("cell")]
    assert cell.name == "the deep cell"
    assert cell.exits == [Exit(to=EntityId("hall"), locked=True)]


def test_connect_writes_the_way_on_both_ends() -> None:
    draft = Draft()
    _ = draft.apply(ScenarioPatch(entities=(_location("cell"), _location("hall"))), ENGINE)

    assert connect(
        draft.world, Connect(from_id=EntityId("cell"), to_id=EntityId("hall"), known=True)
    ) == ("joined cell to hall both ways")
    cell, hall = draft.world.entities.values()
    assert [(way.to, way.known) for way in cell.exits] == [("hall", True)]
    assert [(way.to, way.known) for way in hall.exits] == [("cell", True)]

    with pytest.raises(ValueError, match="already leads"):
        _ = connect(
            draft.world,
            Connect(from_id=EntityId("hall"), to_id=EntityId("cell"), one_way=True),
        )
    with pytest.raises(ValueError, match="no location 'ghost'"):
        _ = connect(draft.world, Connect(from_id=EntityId("cell"), to_id=EntityId("ghost")))
    with pytest.raises(ValueError, match="somewhere other than"):
        _ = connect(draft.world, Connect(from_id=EntityId("cell"), to_id=EntityId("cell")))


def test_connect_refuses_a_known_way_to_a_place_the_player_has_not_met() -> None:
    draft = Draft()
    unmet = _location("crypt").model_copy(update={"known": False})
    _ = draft.apply(ScenarioPatch(entities=(_location("cell"), unmet)), ENGINE)

    with pytest.raises(ValueError, match="has not met"):
        _ = connect(
            draft.world,
            Connect(from_id=EntityId("cell"), to_id=EntityId("crypt"), known=True),
        )
    assert not any(entity.exits for entity in draft.world.entities.values())


def _write(patch: dict[str, JsonValue]) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": patch})])


def _answers(history: Sequence[ModelMessage]) -> list[str]:
    return [
        str(part.content)
        for message in history
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


async def test_every_change_answers_with_what_the_draft_still_needs() -> None:
    session = scenario_run(
        offline_settings(), ENGINE, "authored", "a vault", False, None, packs=SRD
    )
    thin: dict[str, JsonValue] = {
        "meta": {"title": "The Cell", "premise": "Get out."},
        "player_parent_id": "study",
        "entities": [_location("study").model_dump(mode="json")],
    }
    author = scripted(_write(thin), _write(_as_patch()), _finish("Authored the vault."))
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)

    thin_answer, whole_answer = _answers(session.history)[:2]
    assert "created location study[study]" in thin_answer
    assert "four or more locations" in thin_answer
    assert "it plays." in whole_answer


def _connect(**args: JsonValue) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="connect", args=args)])


async def test_an_extension_pass_only_adds_to_the_world_it_stands_on() -> None:
    settings, shipped = offline_settings(), scenario()
    playing = playtest_check(settings, ENGINE, SRD)
    agent = scenario_agent(playing, settings, _brief(shipped.world))
    draft = Draft.from_scenario(shipped)
    author = recorded(
        _write(_as_patch()),
        _write({"entities": [_location("study").model_dump(mode="json")]}),
        _connect(from_id="study", to_id="cloister"),
        _write({"entities": [_location("sub-crypt").model_dump(mode="json")]}),
        _connect(from_id="cloister", to_id="sub-crypt"),
        _finish("Extended the vault."),
    )
    with agent.override(model=FunctionModel(author.stub)):
        _ = await agent.run("Extend the world.", deps=draft)

    scalars, canon, both_settled = author.reasons()
    assert "keeps its meta" in scalars
    assert "already holds ['study']" in canon
    assert "Join one of them to a location this pass wrote" in both_settled

    added = set(draft.world.entities) - set(shipped.world.entities)
    assert added == {EntityId("sub-crypt")}
    assert draft.world.require(EntityId("cloister")).exit_to(EntityId("sub-crypt")) is not None


def test_growth_never_writes_over_the_live_games_mechanics() -> None:
    settled = frozenset({"mara"})

    over_a_sheet = patch_refusal(
        ScenarioPatch(mechanics={"sheets": {"mara": {"concept": "Someone Else"}}}), settled
    )
    assert over_a_sheet is not None and "already holds ['mara']" in over_a_sheet

    scenario_wide = patch_refusal(
        ScenarioPatch(mechanics={"twist_pack": "srd", "twist": "a fresh one"}), settled
    )
    assert scenario_wide == "a scenario already in play keeps its twist, twist_pack"

    assert patch_refusal(ScenarioPatch(mechanics={"sheets": {"ghost": {}}}), settled) is None


def test_a_patched_art_style_reaches_the_scenario() -> None:
    draft = Draft()
    _ = draft.apply(
        ScenarioPatch.model_validate(_as_patch() | {"art_style": "ink-wash noir"}), ENGINE
    )
    assert draft.scenario(LONER3E, SRD).art_style == "ink-wash noir"


def test_remove_drops_by_id_and_refuses_an_unknown_one() -> None:
    draft = Draft()
    _ = draft.apply(ScenarioPatch(entities=(_location("cell"),)), ENGINE)
    deletion = draft.apply(ScenarioPatch(remove=(EntityId("cell"),)), ENGINE)
    assert deletion == "deleted location cell[cell]"
    assert not draft.world.entities
    with pytest.raises(ValueError, match="nothing in the draft"):
        _ = draft.apply(ScenarioPatch(remove=("ghost",)), ENGINE)


def test_validation_names_what_the_draft_is_missing() -> None:
    playing = playtest_check(offline_settings(), ENGINE, SRD)
    empty = scenario_refusal(Draft(), playing, _brief())
    assert empty is not None and "meta" in empty

    draft = Draft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            player_parent_id=EntityId("nowhere"),
            entities=(_location("cell"),),
        ),
        ENGINE,
    )
    dangling = scenario_refusal(draft, playing, _brief())
    assert dangling is not None and "nowhere" in dangling

    unplayable = Draft()
    _ = unplayable.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            player_parent_id=EntityId("cell"),
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
            ),
        ),
        ENGINE,
    )
    broken = scenario_refusal(unplayable, playing, _brief())
    assert broken is not None and "'gaoler' has no sheet" in broken


def test_the_shipped_world_written_as_one_patch_is_playable() -> None:
    draft = Draft()
    patch = ScenarioPatch.model_validate(_as_patch())
    _ = draft.apply(patch, ENGINE)
    assert (
        scenario_refusal(draft, playtest_check(offline_settings(), ENGINE, SRD), _brief()) is None
    )


async def test_the_agent_authors_through_the_write_tool() -> None:
    settings = offline_settings()
    session = scenario_run(settings, ENGINE, "authored", "a vault", False, None, packs=SRD)
    author = scripted(
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
    assert session.draft.scenario(LONER3E, SRD).meta.title == scenario().meta.title


async def test_finishing_an_unplayable_draft_is_refused_and_asked_again() -> None:
    settings = offline_settings()
    session = scenario_run(settings, ENGINE, "authored", "a vault", False, None, packs=SRD)
    author = scripted(
        _finish("all done, and it is great"),
        ModelResponse(parts=[ToolCallPart(tool_name="write", args={"patch": _as_patch()})]),
        _finish("Authored the vault."),
    )
    with session.agent.override(model=FunctionModel(author)):
        _ = await session.send(session.opening_prompt)
    assert session.draft.scenario(LONER3E, SRD).meta.title == scenario().meta.title


async def test_a_session_goes_on_authoring_after_it_finishes() -> None:
    settings = offline_settings()
    session = scenario_run(settings, ENGINE, "authored", "a vault", False, None, packs=SRD)
    study = scenario().world.require(EntityId("study"))
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
    assert EntityId("belfry") in session.draft.world.entities
    assert len(session.history) > before


async def test_an_unplayable_draft_is_never_written() -> None:
    session = scenario_run(
        offline_settings(), ENGINE, "authored", "a vault", False, None, packs=SRD
    )
    with pytest.raises(ValueError, match="does not play"):
        _ = session.write()


def test_a_thin_draft_hears_every_unmet_bar_item_at_once() -> None:
    draft = Draft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            player_parent_id=EntityId("cell"),
            entities=(_location("cell"), _location("vault")),
        ),
        ENGINE,
    )
    reason = scenario_refusal(draft, playtest_check(offline_settings(), ENGINE, SRD), _brief())
    assert reason is not None
    for wanted in ("locations", "locked", "actors", "item", "thread", "when_reached"):
        assert wanted in reason
    assert "no walk of exits reaches from 'cell': ['vault']" in reason


def test_an_opening_slice_passes_a_bar_the_whole_scenario_would_fail() -> None:
    draft = Draft()
    _ = draft.apply(
        ScenarioPatch(
            meta=ScenarioMeta(title="The Cell", premise="Get out."),
            player_parent_id=EntityId("cell"),
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
                    id=EntityId("loose-stone"),
                    kind="item",
                    name="a loose stone",
                    brief="It grinds when the wall is leaned on.",
                    parent_id=EntityId("cell"),
                ),
            ),
            threads=(Thread(id="the-way-out", title="The way out", note="The door is barred."),),
            mechanics={"sheets": {"gaoler": {"concept": "A Bored Gaoler"}}},
        ),
        ENGINE,
    )
    playing = playtest_check(offline_settings(), ENGINE, SRD)

    assert scenario_refusal(draft, playing, _brief(opening=True)) is None
    assert scenario_refusal(draft, playing, _brief()) is not None
    assert draft.scenario(LONER3E, SRD, grows=True).grows
