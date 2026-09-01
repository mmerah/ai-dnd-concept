from collections.abc import Mapping, Sequence
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from aidm.core.entities import DEAD, PLAYER_ID, EngineId, EntityId, Slug
from aidm.core.facts import Fact
from aidm.core.io import engine_text
from aidm.core.model import AnyCharacter, AnyScenario, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import Exchange, SpokenLine
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.core.views import NarratorView, PlayerView, Rows
from aidm.engines.core import Authoring, Engine, Transition, load_packs
from aidm.engines.loner3e.creation import (
    Pack,
    create_character,
    creation_steps,
    guidance,
    pack_options,
    preview_character,
)
from aidm.engines.loner3e.rules import (
    ADVANCE_SPENT,
    GROWTH,
    AdventureGrowth,
    Question,
    RestoreLuck,
    advance,
    advances_owed,
    apply_restore_luck,
    close_conflicts,
    complete_chapter,
    meanings,
    resolve_question,
    twists,
)
from aidm.engines.loner3e.state import (
    ActorSheet,
    Loner3eCharacterFile,
    Loner3eGame,
    Loner3eScenario,
    Loner3eScenarioFile,
    Loner3eState,
    LonerScene,
    LonerSheet,
)
from aidm.kits.entities import Entity, entity_known
from aidm.kits.scenes import boundary, render, worldsmith
from aidm.kits.scenes.render import SheetRows
from aidm.kits.scenes.state import SceneRun, SceneState
from aidm.kits.scenes.verbs import scene_tools

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> Loner3eState:
    """The player is added by code and never authored, so no scenario can claim their id."""
    if not isinstance(scenario, Loner3eScenarioFile):
        raise ValueError("Loner 3E received an incompatible scenario")
    if not isinstance(character, Loner3eCharacterFile):
        raise ValueError("Loner 3E received an incompatible character")
    canon = deepcopy(scenario.payload.world)
    if PLAYER_ID in canon.cast:
        raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
    cast: dict[EntityId, Entity[LonerSheet]] = dict(canon.cast)
    cast[PLAYER_ID] = Entity[LonerSheet](
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        sheet=character.payload.sheet,
    )
    world = SceneState[LonerSheet](
        cast=cast,
        runs=[
            SceneRun(
                scene=canon.opening,
                present=[PLAYER_ID, *canon.present],
                hidden=list(canon.hidden),
            )
        ],
        threads=canon.threads,
        player_id=PLAYER_ID,
        source=canon.source,
    )
    return Loner3eState(world=world, twist_pack=character.payload.twist_pack)


def sheet_rows(state: Loner3eGame) -> SheetRows:
    world = state.payload.world

    def rows(entity_id: EntityId) -> tuple[tuple[str, str], ...]:
        sheet = world.require(entity_id).sheet
        return () if sheet is None else sheet.rows()

    return rows


def engine_sections(packs: Mapping[str, Pack], state: Loner3eGame) -> tuple[tuple[str, str], ...]:
    """Tags in play, plus advances owed; the sheets themselves are already on the entity lines."""
    glossary: dict[str, str] = {}
    for one in state.payload.world.here():
        if isinstance(sheet := one.sheet, ActorSheet):
            glossary.update(meanings(packs, state.packs, sheet))
    lines = "\n".join(f"- {tag}: {detail}" for tag, detail in glossary.items())
    spelled = (("WHAT THE TAGS IN PLAY MEAN", lines),) if glossary else ()
    return *spelled, *advances_owed(state)


def player_over(state: Loner3eGame) -> str | None:
    return "You died." if state.payload.world.player.trait(DEAD) is not None else None


def build(user_packs: Path) -> Engine[Loner3eGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    mechanics: tuple[MasterTool[Loner3eGame], ...] = (
        master_tool(
            "roll_question",
            "Roll Chance against Risk for one closed dramatic question.",
            Question,
            lambda draft, one, rng: resolve_question(draft, one, rng, twists(packs, draft)),
        ),
        master_tool(
            "restore_luck",
            "Restore an actor's luck after a conflict ends.",
            RestoreLuck,
            lambda draft, one, _rng: apply_restore_luck(draft, one.actor_id),
        ),
        master_tool(
            "complete_chapter",
            "Record that the current adventure has ended.",
            NoArgs,
            lambda draft, _args, _rng: complete_chapter(draft),
        ),
        master_tool(
            "advance",
            ADVANCE_SPENT + GROWTH,
            AdventureGrowth,
            lambda draft, one, rng: advance(draft, one, rng),
        ),
    )
    return Engine(
        id=EngineId("loner3e"),
        title="LONER 3E",
        instructions=engine_text(ENGINE_DIR / "rules.md"),
        packs=pack_options(packs),
        game=Loner3eGame,
        scenario=Loner3eScenarioFile,
        character=Loner3eCharacterFile,
        guidance=partial(guidance, packs),
        world_tools=scene_tools(_world_of),
        tools=mechanics,
        creation_steps=partial(creation_steps, packs),
        create_character=partial(create_character, packs),
        preview_character=preview_character,
        validate=partial(_validate, packs),
        new_game=new_game,
        entity_known=_entity_known,
        record=_record,
        history=_history,
        master_sections=partial(_master_sections, packs),
        narrator_view=_narrator_view,
        player_view=_player_view,
        over=player_over,
        authoring=Authoring(
            answer=LonerScene,
            prompt=lambda source, rules: worldsmith.render_opening(source, rules, LonerScene),
            refusal=_authoring_refusal,
            build=_build_scenario,
        ),
        crossing=Transition(
            ready=lambda state: state.payload.world.run.settled,
            write=_write_next,
            install=_install_scene,
            arrival_brief=worldsmith.CROSSING,
        ),
        extension=None,
    )


def check_packs(packs: Mapping[str, Pack], state: Loner3eGame) -> None:
    if not state.packs:
        raise ValueError("a Loner 3E game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")


def _validate(packs: Mapping[str, Pack], state: Loner3eGame) -> None:
    check_packs(packs, state)
    world = state.payload.world
    for one in world.cast.values():
        if one.kind == "actor" and not isinstance(one.sheet, ActorSheet):
            raise ValueError(f"{one.id!r} has no sheet; a Loner actor needs one")
    if (twist_pack := state.payload.twist_pack) not in state.packs:
        raise ValueError(f"twists roll from {twist_pack!r}, which is unselected")


def _world_of(state: Loner3eGame) -> SceneState[LonerSheet]:
    return state.payload.world


def _entity_known(state: Loner3eGame, entity_id: EntityId) -> bool | None:
    return entity_known(state.payload.world, entity_id)


def _record(
    state: Loner3eGame,
    prompt: str,
    lines: tuple[SpokenLine, ...],
    facts: Sequence[Fact],
) -> tuple[str, ...]:
    return boundary.record(state, state.payload.world, prompt, lines, facts)


def _history(state: Loner3eGame) -> tuple[Exchange, ...]:
    return boundary.history(state.payload.world)


def _master_sections(packs: Mapping[str, Pack], state: Loner3eGame) -> Rows:
    return render.master_sections(
        state,
        state.payload.world,
        sheet_rows(state),
        partial(engine_sections, packs),
    )


def _narrator_view(state: Loner3eGame) -> NarratorView:
    return render.narrator_view(state.payload.world)


def _player_view(state: Loner3eGame) -> PlayerView:
    return render.player_view(state, state.payload.world, sheet_rows(state), player_over(state))


def _authoring_refusal(written: BaseModel) -> str | None:
    return worldsmith.scene_refusal(cast(LonerScene, written))


def _build_scenario(
    title: str,
    premise: str,
    packs: tuple[Slug, ...],
    written: BaseModel,
    source: str,
) -> AnyScenario:
    scene = cast(LonerScene, written)
    return Loner3eScenarioFile(
        meta=ScenarioMeta(title=title, premise=premise or scene.situation),
        engine=EngineId("loner3e"),
        packs=packs,
        payload=Loner3eScenario(world=worldsmith.opening_canon(scene, source)),
    )


async def _write_next(
    state: Loner3eGame,
    intent: str,
    rules: str,
    answer: WorldsmithAnswer,
) -> BaseModel:
    return await worldsmith.write_next(
        state.payload.world, LonerScene, intent, rules, sheet_rows(state), answer
    )


def _install_scene(state: Loner3eGame, written: BaseModel) -> tuple[Fact, ...]:
    scene = cast(LonerScene, written)
    return worldsmith.install_scene(state.payload.world, scene, close_conflicts(state))
