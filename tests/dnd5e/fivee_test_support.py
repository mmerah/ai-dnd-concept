from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest
from core_test_support import updated

from aidm.base import (
    PLAYER_ID,
    SAVE_VERSION,
    ActorEntity,
    EntityId,
    ItemEntity,
    LocationEntity,
)
from aidm.content import ScenarioMeta, authored_world
from aidm.engines.dnd5e.access import actor_of
from aidm.engines.dnd5e.content.library import Content, loaded, read_pack
from aidm.engines.dnd5e.content.models import Pack
from aidm.engines.dnd5e.content.pack_ruleset import compile_ruleset
from aidm.engines.dnd5e.content.records.base import Collection, ContentRef, Record
from aidm.engines.dnd5e.engine import Dnd5eEngine, dnd5e_engine
from aidm.engines.dnd5e.facts import Emitted
from aidm.engines.dnd5e.ruleset import Ruleset
from aidm.engines.dnd5e.state import (
    Dnd5eActor,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItemState,
    StatBlock,
)
from aidm.engines.dnd5e.values import Attributes, ContentSlug
from aidm.store import load_character, load_scenario
from aidm.world import ActorRecord, GameState, ItemRecord, WorldState

REPOSITORY_ROOT = Path(__file__).parents[2]
PACK_DIR = REPOSITORY_ROOT / "src" / "aidm" / "engines" / "dnd5e" / "data" / "srd-2014"


def content_ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def player_of(state: GameState) -> Dnd5eActor:
    return actor_of(state, PLAYER_ID)


def summary(fact: Emitted) -> str:
    return fact.trace_summary


def with_actor(state: GameState, entity: ActorEntity, actor: Dnd5eActorState) -> GameState:
    world = state.world.model_copy(deep=True)
    world.actors[entity.id] = ActorRecord(entity=entity, rules=actor)
    return updated(state, world=world)


def with_item(state: GameState, entity: ItemEntity, item: Dnd5eItemState) -> GameState:
    world = state.world.model_copy(deep=True)
    world.items[entity.id] = ItemRecord(entity=entity, rules=item)
    return updated(state, world=world)


def _actor(entity: ActorEntity, stats: StatBlock) -> ActorRecord:
    return ActorRecord(entity=entity, rules=Dnd5eActorState(stats=stats))


def _item(entity: ItemEntity) -> ItemRecord:
    return ItemRecord(entity=entity, rules=Dnd5eItemState())


def blank_game() -> GameState:
    locations = [
        LocationEntity(id=EntityId("study"), name="the study", brief="A room.", known=True),
        LocationEntity(id=EntityId("vault"), name="the vault", brief="A crypt."),
    ]
    actors = [
        _actor(
            ActorEntity(
                id=PLAYER_ID,
                name="Kael",
                brief="A relic-hunter.",
                known=True,
                location_id=EntityId("study"),
            ),
            StatBlock(attributes=Attributes(wisdom=14), max_hp=10, hp=10),
        ),
        _actor(
            ActorEntity(
                id=EntityId("mara"),
                name="Mara",
                brief="A scribe.",
                known=True,
                location_id=EntityId("study"),
            ),
            StatBlock(),
        ),
        _actor(
            ActorEntity(
                id=EntityId("elena"),
                name="Elena",
                brief="An archivist.",
                location_id=EntityId("study"),
            ),
            StatBlock(),
        ),
    ]
    items = [
        _item(
            ItemEntity(
                id=EntityId("vault_map"),
                name="the vault map",
                brief="A chart.",
                container_id=EntityId("study"),
            )
        ),
        _item(
            ItemEntity(
                id=EntityId("lantern"),
                name="a lantern",
                brief="A tin lantern.",
                known=True,
                container_id=PLAYER_ID,
            )
        ),
    ]
    return GameState(
        save_version=SAVE_VERSION,
        scenario_id="whispering-vault",
        character_id="kael",
        scenario=ScenarioMeta(title="Test", premise="A test."),
        engine="dnd5e",
        world=WorldState(
            actors={record.entity.id: record for record in actors},
            items={record.entity.id: record for record in items},
            locations={entity.id: entity for entity in locations},
        ),
    )


@pytest.fixture
def state() -> GameState:
    return blank_game()


@cache
def pack(directory: Path = PACK_DIR) -> Pack:
    return read_pack(directory)


@cache
def content() -> Content:
    return loaded([pack()])


def all_of[R: Record](
    held: Pack,
    name: Collection,
    kind: type[R],
) -> Mapping[ContentSlug, R]:
    found = held.records.get(name, {})
    wrong = sorted(index for index, record in found.items() if not isinstance(record, kind))
    if wrong:
        raise ValueError(f"{name} holds records that are no {kind.__name__}: {wrong}")
    return {index: record for index, record in found.items() if isinstance(record, kind)}


@cache
def ruleset() -> Ruleset:
    return compile_ruleset(content())


@cache
def sheet(character: str = "kael") -> Dnd5eCharacterData:
    data = load_character(REPOSITORY_ROOT / "characters", character, "dnd5e").overlay.character
    if not isinstance(data, Dnd5eCharacterData):
        raise ValueError(f"character {character!r} is not a 5e character")
    return data


def initial_5e_game(
    name: str = "whispering-vault",
    character: str = "kael",
) -> tuple[Dnd5eEngine, GameState]:
    scenario = load_scenario(REPOSITORY_ROOT / "scenarios", name, "dnd5e")
    played = load_character(REPOSITORY_ROOT / "characters", character, "dnd5e")
    engine = dnd5e_engine(ruleset())
    authored = authored_world(scenario, played)
    return engine, GameState(
        save_version=SAVE_VERSION,
        scenario_id=scenario.id,
        character_id=played.id,
        scenario=scenario.meta,
        engine=engine.id,
        world=engine.initial_world(authored, played.overlay.character),
    )


@cache
def _opened(name: str, character: str) -> GameState:
    return initial_5e_game(name, character)[1]


def new_game(
    name: str = "whispering-vault",
    character: str = "kael",
) -> GameState:
    """A fresh copy every call: mechanics mutate the draft they are handed."""
    return _opened(name, character).model_copy(deep=True)
