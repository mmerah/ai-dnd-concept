from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, Counter
from aidm.engines.rooms.world import Item, Place, Visit, Way
from aidm.engines.tunnelgoons.world import Goon, Npc, TunnelGoonsGame, TunnelGoonsWorld

START = EntityId("start")
HALL = EntityId("hall")
VAULT = EntityId("vault")
CRYPT = EntityId("crypt")
MIRA = EntityId("mira")
MANTIS = EntityId("mantis")
ROPE = EntityId("rope")
TORCH = EntityId("torch")
KEY = EntityId("key")
LANTERN = EntityId("lantern")


def _map_pieces() -> tuple[
    dict[EntityId, Place],
    dict[EntityId, list[Way]],
    dict[EntityId, Npc],
    dict[EntityId, Item],
]:
    """A line of four places, a start->vault shortcut, and hall->vault locked."""
    places = {
        START: Place(
            id=START,
            name="Start",
            brief="Where you begin",
            known=True,
            description="Light seeps under a heavy door.",
        ),
        HALL: Place(
            id=HALL,
            name="Hall",
            brief="A long hall",
            known=True,
            description="Cracked flagstones run its length.",
        ),
        VAULT: Place(
            id=VAULT,
            name="Vault",
            brief="A sealed vault",
            known=False,
            description="Iron bands hold an old door shut.",
        ),
        CRYPT: Place(
            id=CRYPT,
            name="Crypt",
            brief="A quiet crypt",
            known=False,
            description="Dust-choked shelves of bone.",
        ),
    }
    ways = {
        START: [Way(to=HALL, known=True), Way(to=VAULT, known=False)],
        HALL: [Way(to=START, known=True), Way(to=VAULT, known=True, locked=True)],
        VAULT: [Way(to=HALL, known=False), Way(to=CRYPT, known=False), Way(to=START, known=False)],
        CRYPT: [Way(to=VAULT, known=False)],
    }
    mira = Npc(
        id=MIRA,
        name="Mira",
        brief="A cautious guide",
        known=True,
        place=START,
        hp=Counter(current=8, maximum=8),
    )
    mantis = Npc(
        id=MANTIS,
        name="Robo Mantis",
        brief="A clicking husk of gears",
        known=False,
        place=HALL,
        hp=Counter(current=4, maximum=4),
    )
    items = {
        ROPE: Item(id=ROPE, name="Rope", brief="A coil of rope", known=True, on=PLAYER_ID),
        TORCH: Item(id=TORCH, name="Torch", brief="An unlit torch", known=True, on=PLAYER_ID),
        KEY: Item(id=KEY, name="Key", brief="A tarnished key", known=False, on=HALL),
        LANTERN: Item(id=LANTERN, name="Lantern", brief="A dented lantern", known=True, on=START),
    }
    return places, ways, {mira.id: mira, mantis.id: mantis}, items


def _kael() -> Goon:
    return Goon(
        id=PLAYER_ID,
        name="Kael",
        brief="A wiry scavenger",
        known=True,
        abilities={"brute": 1, "skulker": 1, "erudite": 1},
        kit=("Rope", "Torch", "Lantern"),
    )


def small_world() -> TunnelGoonsGame:
    places, ways, npcs, items = _map_pieces()
    world = TunnelGoonsWorld(
        places=places,
        ways=ways,
        npcs=npcs,
        items=items,
        player=_kael(),
        visits=[Visit(place=START)],
    )
    return TunnelGoonsGame(
        scenario_id="test",
        character_id="kael",
        scenario=ScenarioMeta(
            title="Test", premise="A test dungeon.", scope="One dungeon, played to its end."
        ),
        engine=EngineId("tunnelgoons"),
        payload=world,
    )
