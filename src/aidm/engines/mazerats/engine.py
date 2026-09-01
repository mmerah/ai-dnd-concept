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
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import NarratorView, PlayerView, Rows
from aidm.engines.core import Authoring, Engine, Transition, load_packs
from aidm.engines.mazerats.creation import (
    Pack,
    create_character,
    creation_steps,
    pack_options,
    preview_character,
)
from aidm.engines.mazerats.rules import (
    Attack,
    CastSpell,
    DangerRoll,
    LevelUp,
    Reaction,
    Rest,
    Stow,
    attack,
    cast_spell,
    check_carry,
    danger_roll,
    level_up,
    reaction,
    rest,
    stow,
)
from aidm.engines.mazerats.state import (
    ActorSheet,
    ItemSheet,
    MazeRatsCharacterFile,
    MazeRatsGame,
    MazeRatsScenario,
    MazeRatsScenarioFile,
    MazeRatsSheet,
    MazeRatsState,
    MazeRatsWorld,
)
from aidm.kits.entities import Entity, entity_known
from aidm.kits.rooms import boundary, render, verbs, worldsmith
from aidm.kits.rooms.render import SheetRows
from aidm.kits.rooms.state import RoomVisit, RoomWorld

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> MazeRatsState:
    if not isinstance(scenario, MazeRatsScenarioFile):
        raise ValueError("Maze Rats received an incompatible scenario")
    if not isinstance(character, MazeRatsCharacterFile):
        raise ValueError("Maze Rats received an incompatible character")
    canon = deepcopy(scenario.payload.world)
    if PLAYER_ID in canon.cast:
        raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
    start = canon.cast.get(canon.start)
    if start is None or start.kind != "place":
        raise ValueError(f"Maze Rats has no starting place {canon.start!r}")
    cast: dict[EntityId, Entity[MazeRatsSheet]] = dict(canon.cast)
    cast[PLAYER_ID] = Entity[MazeRatsSheet](
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        sheet=character.payload.sheet,
        carried_by=canon.start,
    )
    for item in character.payload.inventory:
        if item.id in cast:
            raise ValueError(f"starting item id {item.id!r} collides with the authored world")
        cast[item.id] = Entity[MazeRatsSheet](
            id=item.id,
            kind="item",
            name=item.name,
            brief="Starting equipment.",
            known=True,
            sheet=item.sheet,
            carried_by=PLAYER_ID,
        )
    world = RoomWorld[MazeRatsSheet](
        cast=cast,
        ways=canon.ways,
        player_id=PLAYER_ID,
        visits=[RoomVisit(place=canon.start)],
        threads=canon.threads,
        source=canon.source,
    )
    return MazeRatsState(world=world)


def build(user_packs: Path) -> Engine[MazeRatsGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    mechanics: tuple[MasterTool[MazeRatsGame], ...] = (
        master_tool(
            "danger_roll",
            "Roll 2d6 plus an ability against 10, or against a resisting actor, to see whether "
            "an actor avoids a danger. NPC morale is a will danger roll.",
            DangerRoll,
            danger_roll,
        ),
        master_tool(
            "reaction",
            "Roll 1d6 for the disposition of an encountered actor whose stance is unknown.",
            Reaction,
            reaction,
        ),
        master_tool(
            "attack",
            "Resolve one Maze Rats attack, opening combat on its first swing.",
            Attack,
            attack,
        ),
        master_tool(
            "stow",
            "Move one carried item between hands, worn, belt, and backpack; a weapon must be "
            "drawn into the hands before it can be attacked with.",
            Stow,
            stow,
        ),
        master_tool(
            "cast_spell",
            "Consume a generated spell and record the game master's fixed ruling.",
            CastSpell,
            cast_spell,
        ),
        master_tool(
            "rest",
            "Rest for a night or a safe day, take medicine, and refill empty spell slots.",
            Rest,
            lambda draft, one, rng: rest(draft, one, rng, packs),
        ),
        master_tool(
            "level_up",
            "Award one to three session XP and resolve the resulting level choice.",
            LevelUp,
            level_up,
        ),
    )
    return Engine(
        id=EngineId("mazerats"),
        title="MAZE RATS",
        instructions=engine_text(ENGINE_DIR / "rules.md"),
        packs=pack_options(packs),
        game=MazeRatsGame,
        scenario=MazeRatsScenarioFile,
        character=MazeRatsCharacterFile,
        guidance=guidance,
        world_tools=verbs.room_tools(_world_of, lambda: ItemSheet()),
        tools=mechanics,
        creation_steps=partial(creation_steps, packs),
        create_character=partial(create_character, packs),
        preview_character=preview_character,
        validate=partial(validate, packs),
        new_game=new_game,
        entity_known=_entity_known,
        record=_record,
        history=_history,
        master_sections=_master_sections,
        narrator_view=_narrator_view,
        player_view=_player_view,
        over=player_over,
        authoring=Authoring(
            answer=worldsmith.MapDraft[MazeRatsSheet],
            prompt=lambda source, rules: worldsmith.render_map(
                source, rules, worldsmith.MapDraft[MazeRatsSheet]
            ),
            refusal=_authoring_refusal,
            build=_build_scenario,
        ),
        crossing=None,
        extension=Transition(
            ready=lambda state: boundary.frontier(state.payload.world) == 0,
            write=_write_extension,
            install=_install_extension,
        ),
    )


def guidance(_selected_ids: Sequence[Slug]) -> str:
    return (
        "MAZE RATS AUTHORING\n"
        "Write a complete map of places connected by directed ways. Include an alternate route to "
        "somewhere, a locked way, something hidden, and a standing thread. Every actor and item "
        "needs its matching engine sheet. Clever plans should work without a roll; use "
        "danger_roll only when the fiction leaves a risky danger unresolved.\n"
        "Stat monsters and NPCs by category. Health: weak 1, typical 2, tough 3, hulking 4, "
        "colossal 6 (roll the dice yourself and record the number). Armour is the bonus over the "
        "base 6: unarmoured 0, light protection 1, moderate 2, heavy 3, nigh impervious 4. "
        "Attack bonus: untrained +0, trained +1, dangerous +2, masterful +3, lethal +4. "
        "STR, DEX, and WIL run +0 for weak, slow, or dimwitted through +4 for monstrous, "
        "blurred, or genius."
    )


async def _write_extension(
    state: MazeRatsGame,
    intent: str,
    rules: str,
    answer: WorldsmithAnswer,
) -> BaseModel:
    return await worldsmith.write_extension(
        state.payload.world,
        worldsmith.MapDraft[MazeRatsSheet],
        intent,
        rules,
        sheet_rows(state),
        answer,
    )


def _install_extension(state: MazeRatsGame, written: BaseModel) -> tuple[Fact, ...]:
    extension = cast(worldsmith.MapDraft[MazeRatsSheet], written)
    return worldsmith.install_extension(state.payload.world, extension)


def validate(packs: Mapping[str, Pack], state: MazeRatsGame) -> None:
    if not state.packs:
        raise ValueError("Maze Rats games require at least one selected table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    world = state.payload.world
    for actor in (one for one in world.cast.values() if one.kind == "actor"):
        check_carry(world, actor)
    for entity in world.cast.values():
        if entity.kind == "actor" and not isinstance(entity.sheet, ActorSheet):
            raise ValueError(f"{entity.id!r} has no actor sheet")
        if entity.kind == "item" and not isinstance(entity.sheet, ItemSheet):
            raise ValueError(f"{entity.id!r} has no item sheet")
        if entity.kind == "place" and entity.sheet is not None:
            raise ValueError(f"place {entity.id!r} cannot carry a Maze Rats sheet")


def player_over(state: MazeRatsGame) -> str | None:
    return "You died." if state.payload.world.player.trait(DEAD) is not None else None


def sheet_rows(state: MazeRatsGame) -> SheetRows:
    world = state.payload.world

    def rows(entity_id: EntityId) -> tuple[tuple[str, str], ...]:
        sheet = world.require(entity_id).sheet
        return () if sheet is None else sheet.rows()

    return rows


def _world_of(state: MazeRatsGame) -> MazeRatsWorld:
    return state.payload.world


def _entity_known(state: MazeRatsGame, entity_id: EntityId) -> bool | None:
    return entity_known(state.payload.world, entity_id)


def _record(
    state: MazeRatsGame,
    prompt: str,
    lines: tuple[SpokenLine, ...],
    facts: Sequence[Fact],
) -> tuple[str, ...]:
    return boundary.record(state, state.payload.world, prompt, lines, facts)


def _history(state: MazeRatsGame) -> tuple[Exchange, ...]:
    return boundary.history(state.payload.world)


def _master_sections(state: MazeRatsGame) -> Rows:
    return render.master_sections(state, state.payload.world, sheet_rows(state), lambda _state: ())


def _narrator_view(state: MazeRatsGame) -> NarratorView:
    return render.narrator_view(state.payload.world)


def _player_view(state: MazeRatsGame) -> PlayerView:
    return render.player_view(state, state.payload.world, sheet_rows(state), player_over(state))


def _authoring_refusal(written: BaseModel) -> str | None:
    return worldsmith.map_refusal(cast(worldsmith.MapDraft[MazeRatsSheet], written))


def _build_scenario(
    title: str,
    premise: str,
    packs: tuple[Slug, ...],
    written: BaseModel,
    source: str,
) -> AnyScenario:
    draft = cast(worldsmith.MapDraft[MazeRatsSheet], written)
    return MazeRatsScenarioFile(
        meta=ScenarioMeta(title=title, premise=premise or "An unexplored maze."),
        engine=EngineId("mazerats"),
        packs=packs,
        payload=MazeRatsScenario(world=worldsmith.opening_canon(draft, source)),
    )
