from collections.abc import Mapping
from copy import deepcopy
from functools import partial
from pathlib import Path

from aidm.core.entities import DEAD, PLAYER_ID, EngineId, EntityId
from aidm.core.io import engine_text
from aidm.core.model import Character, Game, Scenario
from aidm.core.tools import NoArgs, master_tool
from aidm.engines.core import Engine, load_packs
from aidm.engines.loner3e.creation import Loner3eCreation, Pack, guidance, pack_options
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
from aidm.engines.loner3e.state import ActorSheet, Loner3eState, LonerSheet
from aidm.kits.scenes.render import SheetRows
from aidm.kits.scenes.state import Entity, SceneState
from aidm.kits.scenes.verbs import scene_tools

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: Scenario, character: Character) -> Loner3eState:
    """The player is added by code and never authored, so no scenario can claim their id."""
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
    opening = canon.opening.model_copy(update={"present": (PLAYER_ID, *canon.opening.present)})
    world = SceneState[LonerSheet](
        cast=cast,
        current=opening,
        threads=canon.threads,
        player_id=PLAYER_ID,
        source=canon.source,
    )
    return Loner3eState(world=world, twist_pack=character.payload.twist_pack)


def sheet_rows(state: Game) -> SheetRows:
    def rows(entity_id: EntityId) -> tuple[tuple[str, str], ...]:
        sheet = state.world.require(entity_id).sheet
        return () if sheet is None else sheet.rows()

    return rows


def engine_sections(packs: Mapping[str, Pack], state: Game) -> tuple[tuple[str, str], ...]:
    """Tags in play, plus advances owed; the sheets themselves are already on the entity lines."""
    glossary: dict[str, str] = {}
    for one in state.world.here():
        if isinstance(sheet := one.sheet, ActorSheet):
            glossary.update(meanings(packs, state.packs, sheet))
    lines = "\n".join(f"- {tag}: {detail}" for tag, detail in glossary.items())
    spelled = (("WHAT THE TAGS IN PLAY MEAN", lines),) if glossary else ()
    return (*spelled, *advances_owed(state))


def player_over(state: Game) -> str | None:
    return "You died." if state.world.player.trait(DEAD) is not None else None


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("loner3e"),
        title="LONER 3E",
        instructions=engine_text(ENGINE_DIR / "rules.md"),
        packs=pack_options(packs),
        guidance=partial(guidance, packs),
        creation=Loner3eCreation(packs),
        validate=partial(_validate, packs),
        new_game=new_game,
        sheet_rows=sheet_rows,
        sections=partial(engine_sections, packs),
        over=player_over,
        scene_closed=close_conflicts,
        tools=scene_tools(
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
            master_tool("advance", ADVANCE_SPENT + GROWTH, AdventureGrowth, advance),
        ),
    )


def check_packs(packs: Mapping[str, Pack], state: Game) -> None:
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")


def _validate(packs: Mapping[str, Pack], state: Game) -> None:
    check_packs(packs, state)
    world = state.world
    # Every actor rolls by a sheet: one nobody wrote is refused, not given a blank one.
    for one in world.cast.values():
        if one.kind == "actor" and not isinstance(one.sheet, ActorSheet):
            raise ValueError(f"{one.id!r} has no sheet; a Loner actor needs one")
    twist_pack = state.payload.twist_pack
    if twist_pack is not None and twist_pack not in state.packs:
        raise ValueError(f"twists roll from {twist_pack!r}, which is unselected")
