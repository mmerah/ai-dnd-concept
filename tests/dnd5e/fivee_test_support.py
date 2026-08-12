from pathlib import Path
from random import Random

from core_test_support import CHARACTERS, DND5E, SCENARIOS, game, settings

from aidm.app.session import Advancer, GameSession, LaunchTarget, begin_game, build_engine
from aidm.content.authored import Character, Scenario
from aidm.content.store import (
    FileSaves,
    FileTraces,
    load_character,
    load_scenario,
    write_character,
)
from aidm.engines.counters import Counter
from aidm.engines.dnd5e.advance import ADVANCEMENT_READY
from aidm.engines.dnd5e.content import ENGINE_DIR
from aidm.engines.dnd5e.mechanics import Sheet, read, write
from aidm.engines.loader import Creation, Engine
from aidm.state.base import PLAYER_ID, Entity, EntityId, Slug, Trait
from aidm.state.creation import Amounts, CreationStep, Picks
from aidm.state.packs import ContentRef
from aidm.state.world import GameState
from aidm.turn.roles import build_stages

PACK_DIR = ENGINE_DIR / "packs" / "srd-2014"
RAT = EntityId("cloister_rat")
CLOISTER = EntityId("cloister")
SWORD = EntityId("longsword")
BOW = EntityId("shortbow")
TARGET = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael", engine=DND5E)


# A class that leads on a physical score takes the array one way round, a caster the other.
_MIGHTY = ("barbarian", "fighter", "monk", "paladin", "ranger", "rogue")
# The two spreads phase 12 shipped as authored options, now assigned by hand: the standard array
# is exactly 27 points, so the same six numbers are legal under either method.
MIGHT: Amounts = {
    "strength": 15,
    "constitution": 14,
    "dexterity": 13,
    "wisdom": 12,
    "intelligence": 10,
    "charisma": 8,
}
FOCUS: Amounts = {
    "intelligence": 15,
    "constitution": 14,
    "dexterity": 13,
    "wisdom": 12,
    "charisma": 10,
    "strength": 8,
}


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", DND5E)


def creation_of(engine: Engine) -> Creation:
    found = engine.creation
    assert found is not None
    return found


def filled_picks(made: Creation, picks: Picks) -> Picks:
    """Every option step not already answered takes its first legal picks, as the page would:
    a round at a time, because answering one step is what offers the next, and preferring an
    option no other step has taken, because one record picked twice is refused."""
    filled: dict[Slug, tuple[Slug, ...] | Amounts] = dict(picks)
    taken = {pick for held in filled.values() if isinstance(held, tuple) for pick in held}
    while pending := [
        step
        for step in made.steps(filled)
        if isinstance(step, CreationStep) and step.id not in filled
    ]:
        for step in pending:
            offered = [option.id for option in step.options]
            ordered = [name for name in offered if name not in taken]
            ordered += [name for name in offered if name in taken]
            chosen = tuple(ordered[: step.choose])
            filled[step.id] = chosen
            taken.update(chosen)
    return filled


def created_game(directory: Path, class_index: str) -> tuple[Engine, GameState]:
    """A human of the class, every choice taken as it comes, through the authored write and load
    path into a started game: the state advancement has to be able to play."""
    engine = build_engine(DND5E, settings())
    picks: Picks = filled_picks(
        creation_of(engine),
        {
            "race": ("human",),
            "class": (class_index,),
            "background": ("acolyte",),
            "ability-method": ("standard-array",),
            "abilities-standard-array": MIGHT if class_index in _MIGHTY else FOCUS,
        },
    )
    brief = "A hand the vault has not read."
    made = creation_of(engine).create(class_index.capitalize(), brief, picks)
    write_character(directory, class_index, DND5E, made)
    return engine, begin_game(engine, scenario(), load_character(directory, class_index, DND5E))


def character() -> Character:
    return load_character(CHARACTERS, "kael", DND5E)


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
        stages=build_stages(engine, config),
        advancer=Advancer.of(engine, config),
        saves=FileSaves(directory),
        traces=FileTraces(directory),
        history_window=6,
        max_growth=3,
        max_memories=2,
        rng=Random(1),
    )


def ready(state: GameState) -> GameState:
    """The state the Director leaves when the story earns a level."""
    draft = state.draft()
    draft.player.traits.append(Trait(id=ADVANCEMENT_READY, name="Ready to advance"))
    return draft.committed()


def armed(state: GameState) -> GameState:
    """Kael in the cloister with the rat, a longsword and a shortbow, and a fighter's scores:
    the shipped character carries neither weapon, and every 5e attack needs one."""
    draft = state.draft()
    _ = draft.move(draft.player, draft.world.require(CLOISTER))
    _ = draft.reveal(draft.world.require(RAT))
    mechanics = read(draft)
    for item_id, index in ((SWORD, "longsword"), (BOW, "shortbow")):
        entity = Entity(
            id=item_id, kind="item", name=index, brief="", known=True, parent_id=PLAYER_ID
        )
        _ = draft.add(entity)
        mechanics.sheets[item_id] = Sheet(
            refs=(ContentRef(pack="srd-2014", collection="weapons", index=index),)
        )
    player = mechanics.sheets[PLAYER_ID]
    player.numbers["strength"] = 17
    player.numbers["dexterity"] = 15
    write(draft, mechanics)
    return draft.committed()


def paladinly(state: GameState) -> GameState:
    """The same character as a paladin, whose level-2 row is the one shape that both grants and
    offers: Spellcasting and Divine Smite handed over, one fighting style picked."""
    draft = state.draft()
    mechanics = read(draft)
    sheet = mechanics.sheets[PLAYER_ID]
    sheet.refs = tuple(ref for ref in sheet.refs if ref.collection != "classes") + (
        ContentRef(pack="srd-2014", collection="classes", index="paladin"),
    )
    write(draft, mechanics)
    return ready(draft.committed())


def wizardly(state: GameState) -> GameState:
    """The same character as a wizard: the 5e spellcasting ability is read off the class record,
    and a cast is refused unless the spell is a ref on the caster's own sheet."""
    draft = state.draft()
    mechanics = read(draft)
    sheet = mechanics.sheets[PLAYER_ID]
    sheet.refs = tuple(ref for ref in sheet.refs if ref.collection != "classes") + (
        ContentRef(pack="srd-2014", collection="classes", index="wizard"),
        *(
            ContentRef(pack="srd-2014", collection="spells", index=index)
            for index in ("burning-hands", "cure-wounds", "magic-missile")
        ),
    )
    sheet.numbers["intelligence"] = 15
    # `build` projected the fighter's d10; a swapped class ref does not move it, and a level-up
    # sizes its hit points from this number.
    sheet.numbers["hit-die"] = 6
    sheet.counters["slot-1"] = Counter(current=2, maximum=2, recharge="long-rest")
    sheet.counters["slot-2"] = Counter(current=2, maximum=2, recharge="long-rest")
    write(draft, mechanics)
    return draft.committed()
