from pathlib import Path
from random import Random

from core_test_support import CHARACTERS, DND5E, SCENARIOS, game, settings

from aidm.app.session import GameSession, LaunchTarget, build_engine
from aidm.content.authored import Character, Scenario
from aidm.content.store import FileSaves, FileTraces, load_character, load_scenario
from aidm.engines.dnd5e.advance import ADVANCEMENT_READY
from aidm.engines.dnd5e.rules import PLUGIN
from aidm.engines.loader import Engine, EngineSpec
from aidm.state.base import PLAYER_ID, Entity, EntityId
from aidm.state.packs import ENCODING, ContentRef, PackFormat
from aidm.state.sheet import Counter, SheetDefinition, SheetTag, SheetTemplate
from aidm.state.world import GameState, Record, player_sheet
from aidm.turn.advancement import advisor
from aidm.turn.pipeline import TurnOptions, default_cast

ENGINE_DIR = PLUGIN.engine_dir
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
    return PLUGIN.pack_format(spec)


def dnd5e_game() -> tuple[Engine, GameState]:
    return game(DND5E)


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


def ready(state: GameState) -> GameState:
    """The state the Director leaves when the story earns a level."""
    draft = state.draft()
    player_sheet(draft).tags.append(SheetTag(id=ADVANCEMENT_READY, name="Ready to advance"))
    return draft.committed()


def armed(state: GameState) -> GameState:
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


def wizardly(state: GameState) -> GameState:
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
