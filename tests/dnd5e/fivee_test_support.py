from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from random import Random

import pytest
from core_test_support import tool_context, turn_context, updated
from pydantic_ai import RunContext

from aidm.core.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity, EntityId
from aidm.core.content import ScenarioMeta, authored_world
from aidm.core.engine import Engine
from aidm.core.facts import Fact
from aidm.core.store import load_character, load_scenario
from aidm.core.tools import TurnContext
from aidm.core.world import GameState, Record, WorldState
from aidm.engines.dnd5e.access import read_actor, read_item
from aidm.engines.dnd5e.content.library import Content, loaded, read_pack
from aidm.engines.dnd5e.content.models import Pack
from aidm.engines.dnd5e.content.pack_ruleset import compile_ruleset
from aidm.engines.dnd5e.content.records.base import Collection, ContentRef
from aidm.engines.dnd5e.content.records.base import Record as ContentRecord
from aidm.engines.dnd5e.engine import dnd5e_engine
from aidm.engines.dnd5e.ruleset import Ruleset
from aidm.engines.dnd5e.state import (
    Dnd5eActor,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItem,
    Dnd5eItemState,
    StatBlock,
)
from aidm.engines.dnd5e.tools import Dnd5eTools
from aidm.engines.dnd5e.values import Attributes, ContentSlug

REPOSITORY_ROOT = Path(__file__).parents[2]
PACK_DIR = REPOSITORY_ROOT / "src" / "aidm" / "engines" / "dnd5e" / "packs" / "srd-2014"


def content_ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def actor_of(state: GameState, actor_id: EntityId) -> Dnd5eActor:
    return read_actor(state, actor_id)


def item_of(state: GameState, item_id: EntityId) -> Dnd5eItem:
    return read_item(state, item_id)


def carried_by(state: GameState, actor_id: EntityId) -> tuple[Dnd5eItem, ...]:
    return tuple(read_item(state, entity.id) for entity in state.world.children(actor_id, "item"))


def player_of(state: GameState) -> Dnd5eActor:
    return actor_of(state, PLAYER_ID)


def summary(fact: Fact) -> str:
    return fact.trace


def with_actor(state: GameState, entity: Entity, actor: Dnd5eActorState) -> GameState:
    world = state.world.model_copy(deep=True)
    world.records[entity.id] = Record(entity=entity, rules=actor.model_dump(mode="json"))
    return updated(state, world=world)


def with_item(state: GameState, entity: Entity, item: Dnd5eItemState) -> GameState:
    world = state.world.model_copy(deep=True)
    world.records[entity.id] = Record(entity=entity, rules=item.model_dump(mode="json"))
    return updated(state, world=world)


def _actor(entity: Entity, stats: StatBlock) -> Record:
    return Record(entity=entity, rules=Dnd5eActorState(stats=stats).model_dump(mode="json"))


def _item(entity: Entity) -> Record:
    return Record(entity=entity, rules=Dnd5eItemState().model_dump(mode="json"))


def blank_game() -> GameState:
    locations = [
        Entity(
            id=EntityId("study"), kind="location", name="the study", brief="A room.", known=True
        ),
        Entity(id=EntityId("vault"), kind="location", name="the vault", brief="A crypt."),
    ]
    actors = [
        _actor(
            Entity(
                id=PLAYER_ID,
                kind="actor",
                name="Kael",
                brief="A relic-hunter.",
                known=True,
                parent_id=EntityId("study"),
            ),
            StatBlock(attributes=Attributes(wisdom=14), max_hp=10, hp=10),
        ),
        _actor(
            Entity(
                id=EntityId("mara"),
                kind="actor",
                name="Mara",
                brief="A scribe.",
                known=True,
                parent_id=EntityId("study"),
            ),
            StatBlock(),
        ),
        _actor(
            Entity(
                id=EntityId("elena"),
                kind="actor",
                name="Elena",
                brief="An archivist.",
                parent_id=EntityId("study"),
            ),
            StatBlock(),
        ),
    ]
    items = [
        _item(
            Entity(
                id=EntityId("vault_map"),
                kind="item",
                name="the vault map",
                brief="A chart.",
                parent_id=EntityId("study"),
            )
        ),
        _item(
            Entity(
                id=EntityId("lantern"),
                kind="item",
                name="a lantern",
                brief="A tin lantern.",
                known=True,
                parent_id=PLAYER_ID,
            )
        ),
    ]
    return GameState(
        save_version=SAVE_VERSION,
        scenario_id="whispering-vault",
        character_id="kael",
        scenario=ScenarioMeta(title="Test", premise="A test."),
        engine=EngineId("dnd5e"),
        world=WorldState(
            records={
                record.entity.id: record
                for record in (*actors, *items, *(Record(entity=e) for e in locations))
            }
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


def all_of[R: ContentRecord](
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
    data = load_character(
        REPOSITORY_ROOT / "characters", character, EngineId("dnd5e")
    ).overlay.character
    return Dnd5eCharacterData.model_validate(data)


def initial_5e_game(
    name: str = "whispering-vault",
    character: str = "kael",
) -> tuple[Engine, GameState]:
    scenario = load_scenario(REPOSITORY_ROOT / "scenarios", name, EngineId("dnd5e"))
    played = load_character(REPOSITORY_ROOT / "characters", character, EngineId("dnd5e"))
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


@dataclass(frozen=True, slots=True)
class Turn:
    """One turn's draft, plus the tools that act on it, as the Director's loop would."""

    context: TurnContext
    run: RunContext[TurnContext]
    tools: Dnd5eTools

    @property
    def draft(self) -> GameState:
        return self.context.draft

    def call(self, tool: Callable[..., str], **arguments: object) -> list[Fact]:
        """Only the facts this call appended, so a test reads one action at a time."""
        before = len(self.context.facts)
        _ = tool(self.run, **arguments)
        return self.context.facts[before:]

    def committed(self) -> GameState:
        return self.context.draft.committed()


def turn_of(state: GameState, rng: Random | None = None) -> Turn:
    context = turn_context(dnd5e_engine(ruleset()), state, rng)
    return Turn(context=context, run=tool_context(context), tools=Dnd5eTools(ruleset()))
