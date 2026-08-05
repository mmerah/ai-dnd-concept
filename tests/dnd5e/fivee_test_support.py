from pathlib import Path
from random import Random

from core_test_support import CHARACTERS, DND5E, SCENARIOS, settings

from aidm.core.base import PLAYER_ID, SAVE_VERSION, Entity, EntityId
from aidm.core.content import Character, Scenario, authored_world
from aidm.core.engine import Engine
from aidm.core.enginepack import EngineSpec
from aidm.core.packs import ENCODING, ContentRef, PackFormat, lenient_format
from aidm.core.registry import build_engine
from aidm.core.sheet import Counter, Sheet, SheetDefinition, SheetTag, SheetTemplate, player_sheet
from aidm.core.store import FileSaves, FileTraces, load_character, load_scenario
from aidm.core.world import EngineRules, GameState, Record
from aidm.engines.dnd5e.advance import ADVANCEMENT_READY
from aidm.engines.dnd5e.engine import ENGINE_DIR, build_dnd5e_engine
from aidm.workflow.pipeline import TurnOptions, default_cast
from aidm.workflow.proposals import advisor
from aidm.workflow.session import GameSession, LaunchTarget

PACK_DIR = ENGINE_DIR / "packs" / "srd-2014"
RAT = EntityId("cloister_rat")
CLOISTER = EntityId("cloister")
SWORD = EntityId("longsword")
BOW = EntityId("shortbow")
TARGET = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael", engine=DND5E)
OPTIONS = TurnOptions(history_window=6, max_growth=3)


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", DND5E)


def character() -> Character:
    return load_character(CHARACTERS, "kael", DND5E)


def pack_format() -> PackFormat:
    spec = EngineSpec.model_validate_json((ENGINE_DIR / "spec.json").read_text(encoding=ENCODING))
    return lenient_format(spec.collections)


def dnd5e_game() -> tuple[Engine[Sheet], GameState[Sheet]]:
    engine = build_dnd5e_engine()
    selected_scenario, selected_character = scenario(), character()
    state = engine.state_type(
        save_version=SAVE_VERSION,
        scenario_id=selected_scenario.id,
        character_id=selected_character.id,
        scenario=selected_scenario.meta,
        engine=engine.id,
        world=engine.initial_world(
            authored_world(selected_scenario, selected_character),
            selected_character.overlay.character,
        ),
    )
    engine.validate_state(state)
    return engine, state


def dnd5e_session(directory: Path) -> GameSession:
    config = settings()
    engine = build_engine(DND5E, config)
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        script=default_cast(engine, config).script(engine, OPTIONS),
        advisor=advisor(engine, config),
        saves=FileSaves(directory),
        traces=FileTraces(directory),
        options=OPTIONS,
        rng=Random(1),
    )


def ready[R: EngineRules](state: GameState[R]) -> GameState[R]:
    """The state the Director leaves when the story earns a level."""
    draft = state.draft()
    player_sheet(draft).tags.append(SheetTag(id=ADVANCEMENT_READY, name="Ready to advance"))
    return draft.committed()


def armed(state: GameState[Sheet]) -> GameState[Sheet]:
    """Kael in the cloister with the rat, a longsword and a shortbow, and a fighter's scores:
    the shipped character carries neither weapon, and every 5e attack needs one."""
    draft = state.draft()
    _ = draft.move(draft.player, draft.world.require(CLOISTER))
    _ = draft.reveal(draft.world.require(RAT))
    for item_id, index in ((SWORD, "longsword"), (BOW, "shortbow")):
        entity = Entity(
            id=item_id, kind="item", name=index, brief="", known=True, parent_id=PLAYER_ID
        )
        rules = SheetDefinition(
            refs=(ContentRef(pack="srd-2014", collection="weapons", index=index),)
        ).runtime("item", SheetTemplate())
        draft.world.records[item_id] = Record(entity=entity, rules=rules)
    sheet = player_sheet(draft)
    sheet.numbers["strength"] = 17
    sheet.numbers["dexterity"] = 15
    return draft.committed()


def wizardly(state: GameState[Sheet]) -> GameState[Sheet]:
    """The same character as a wizard: the 5e spellcasting ability is read off the class record."""
    draft = state.draft()
    sheet = player_sheet(draft)
    sheet.refs = tuple(ref for ref in sheet.refs if ref.collection != "classes") + (
        ContentRef(pack="srd-2014", collection="classes", index="wizard"),
    )
    sheet.numbers["intelligence"] = 15
    sheet.counters["slot-1"] = Counter(current=2, maximum=2, recharge="long-rest")
    sheet.counters["slot-2"] = Counter(current=2, maximum=2, recharge="long-rest")
    return draft.committed()
