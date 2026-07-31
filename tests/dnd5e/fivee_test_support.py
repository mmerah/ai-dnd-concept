from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from aidm.domain.base import SAVE_VERSION
from aidm.domain.state import GameState as CoreGameState
from aidm.domain.state import attach_initial_rules, world_from_definitions
from aidm.store import read_character, read_scenario
from aidm_5e.codecs import CHARACTER_CODEC, ITEM_DEFINITION_CODEC
from aidm_5e.content.library import Content, loaded, read_pack
from aidm_5e.content.models import Pack
from aidm_5e.content.records.base import Collection, Record
from aidm_5e.conversion import to_legacy_state
from aidm_5e.domain.models.base import PLAYER_ID, EntityId
from aidm_5e.domain.models.entities import ActorEntity, ItemEntity, LocationEntity
from aidm_5e.domain.models.state import (
    CharacterSheet,
    GameState,
    ScenarioMeta,
    StartingItem,
    WorldState,
)
from aidm_5e.domain.models.stats import StatBlock
from aidm_5e.engine.pack_ruleset import compile_ruleset
from aidm_5e.engine.ruleset import Ruleset
from aidm_5e.factory import Dnd5eEngine, dnd5e_engine
from aidm_5e.utils.models import Attributes, Slug

REPOSITORY_ROOT = Path(__file__).parents[2]
PACK_DIR = REPOSITORY_ROOT / "src" / "aidm_5e" / "data" / "srd-2014"


@pytest.fixture
def state() -> GameState:
    return GameState(
        scenario=ScenarioMeta(title="Test", premise="A test."),
        world=WorldState(
            entities={
                entity.id: entity
                for entity in [
                    LocationEntity(
                        id=EntityId("study"),
                        name="the study",
                        brief="A room.",
                        known=True,
                    ),
                    LocationEntity(
                        id=EntityId("vault"),
                        name="the vault",
                        brief="A crypt.",
                    ),
                    ActorEntity(
                        id=PLAYER_ID,
                        name="Kael",
                        brief="A relic-hunter.",
                        known=True,
                        location_id=EntityId("study"),
                        stats=StatBlock(
                            attributes=Attributes(wisdom=14),
                            max_hp=10,
                            hp=10,
                        ),
                    ),
                    ActorEntity(
                        id=EntityId("mara"),
                        name="Mara",
                        brief="A scribe.",
                        known=True,
                        location_id=EntityId("study"),
                    ),
                    ActorEntity(
                        id=EntityId("elena"),
                        name="Elena",
                        brief="An archivist.",
                        location_id=EntityId("study"),
                    ),
                    ItemEntity(
                        id=EntityId("vault_map"),
                        name="the vault map",
                        brief="A chart.",
                        container_id=EntityId("study"),
                    ),
                    ItemEntity(
                        id=EntityId("lantern"),
                        name="a lantern",
                        brief="A tin lantern.",
                        known=True,
                        container_id=PLAYER_ID,
                    ),
                ]
            }
        ),
    )


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
) -> Mapping[Slug, R]:
    found = held.records.get(name, {})
    wrong = sorted(index for index, record in found.items() if not isinstance(record, kind))
    if wrong:
        raise ValueError(f"{name} holds records that are no {kind.__name__}: {wrong}")
    return {index: record for index, record in found.items() if isinstance(record, kind)}


@cache
def ruleset() -> Ruleset:
    return compile_ruleset(content())


@cache
def sheet(character: str = "kael_5e") -> CharacterSheet:
    definition = read_character(REPOSITORY_ROOT / "characters" / f"{character}.json")
    mechanical = CHARACTER_CODEC.decode(definition.engine_data)
    items = tuple(
        StartingItem(
            name=item.name,
            brief=item.brief,
            ref=(
                None
                if item.engine_data is None
                else ITEM_DEFINITION_CODEC.decode(item.engine_data).ref
            ),
        )
        for item in definition.starting_items
    )
    return CharacterSheet(
        name=definition.name,
        brief=definition.brief,
        origin=mechanical.origin,
        starting_attributes=mechanical.starting_attributes,
        decisions=mechanical.decisions,
        starting_items=items,
    )


def initial_5e_game(
    name: str = "whispering_vault_5e",
    character: str = "kael_5e",
) -> tuple[Dnd5eEngine, CoreGameState]:
    scenario = read_scenario(REPOSITORY_ROOT / "scenarios" / f"{name}.json")
    character_definition = read_character(REPOSITORY_ROOT / "characters" / f"{character}.json")
    engine = dnd5e_engine(ruleset())
    world = world_from_definitions(scenario, character_definition)
    initialized = engine.lifecycle.initialise(world, scenario, character_definition)
    core = CoreGameState(
        save_version=SAVE_VERSION,
        engine=engine.id,
        scenario=scenario.meta,
        world=attach_initial_rules(world, initialized.entity_rules, engine.id),
        rules=initialized.game_rules,
    )
    return engine, core


@cache
def new_game(
    name: str = "whispering_vault_5e",
    character: str = "kael_5e",
) -> GameState:
    _, core = initial_5e_game(name, character)
    return to_legacy_state(core)
