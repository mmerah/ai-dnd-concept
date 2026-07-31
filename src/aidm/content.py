from collections.abc import Mapping
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm.engines.dnd5e.state import Dnd5eActorDefinition, Dnd5eCharacterData, Dnd5eItemDefinition
from aidm.engines.story.state import StoryActorDefinition, StoryCharacterData, StoryItemDefinition

from .base import (
    PLAYER_ID,
    ActorEntity,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    ItemEntity,
    Kind,
    Slug,
)
from .world import ScenarioMeta, WorldState

type ActorEngineData = Annotated[
    StoryActorDefinition | Dnd5eActorDefinition,
    Field(discriminator="engine"),
]
type ItemEngineData = Annotated[
    StoryItemDefinition | Dnd5eItemDefinition,
    Field(discriminator="engine"),
]
type CharacterEngineData = Annotated[
    StoryCharacterData | Dnd5eCharacterData,
    Field(discriminator="engine"),
]
type EntityEngineData = ActorEngineData | ItemEngineData
type EngineData = EntityEngineData | CharacterEngineData


def for_engine[T: EngineData](data: EngineData, expected: type[T]) -> T:
    """Tags are checked once at load, so a mismatch here means the wrong engine is resolving."""
    if not isinstance(data, expected):
        raise ValueError(f"authored data is {data.engine!r}, not {expected.__name__}")
    return data


def for_engine_or_none[T: EngineData](data: EngineData | None, expected: type[T]) -> T | None:
    return None if data is None else for_engine(data, expected)


class ScenarioWorld(Frozen):
    """`world.json`: the narrative canon, authored once for every ruleset."""

    meta: ScenarioMeta
    starting_location_id: EntityId
    entities: tuple[Entity, ...] = ()

    @model_validator(mode="after")
    def _valid_topology(self) -> Self:
        by_id = {entity.id: entity for entity in self.entities}
        if len(by_id) != len(self.entities):
            ids = [entity.id for entity in self.entities]
            duplicates = sorted({entity_id for entity_id in ids if ids.count(entity_id) > 1})
            raise ValueError(f"scenario has duplicate entity ids: {duplicates}")
        if PLAYER_ID in by_id:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        starting_location = by_id.get(self.starting_location_id)
        if starting_location is None or starting_location.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        for entity in self.entities:
            if entity.kind == "actor":
                container = by_id.get(entity.location_id)
                if container is None or container.kind != "location":
                    raise ValueError(f"actor {entity.id!r} is not in a scenario location")
            elif entity.kind == "item":
                container = by_id.get(entity.container_id)
                if container is None or container.kind not in ("actor", "location"):
                    raise ValueError(f"item {entity.id!r} has no valid scenario container")
        return self


class ScenarioOverlay(Frozen):
    """`<engine>.json`: what one ruleset adds to the entities that need it."""

    actors: dict[EntityId, ActorEngineData] = Field(default_factory=dict)
    items: dict[EntityId, ItemEngineData] = Field(default_factory=dict)


class CharacterProfile(Frozen):
    """`base.json`: who the character is, and the gear they start holding."""

    name: str
    brief: str
    items: tuple[ItemEntity, ...] = ()

    @model_validator(mode="after")
    def _held_and_known(self) -> Self:
        """Own gear is known gear: an unknown carried item would be hidden canon inside the
        inventory the Narrator is shown, so the two prompts would contradict each other."""
        elsewhere = sorted(item.id for item in self.items if item.container_id != PLAYER_ID)
        if elsewhere:
            raise ValueError(f"a character's items start in their own hands: {elsewhere}")
        unknown = sorted(item.id for item in self.items if not item.known)
        if unknown:
            raise ValueError(f"a character knows the gear they start with: {unknown}")
        return self


class CharacterOverlay(Frozen):
    character: CharacterEngineData
    items: dict[EntityId, ItemEngineData] = Field(default_factory=dict)


class Scenario(Frozen):
    """One authored world under the one engine this game selected."""

    id: Slug
    engine: EngineId
    world: ScenarioWorld
    overlay: ScenarioOverlay

    @property
    def meta(self) -> ScenarioMeta:
        return self.world.meta

    @model_validator(mode="after")
    def _overlay_fits_the_world(self) -> Self:
        kinds: dict[EntityId, Kind] = {entity.id: entity.kind for entity in self.world.entities}
        _require_overlay(self.engine, self.overlay.actors, "actor", kinds)
        _require_overlay(self.engine, self.overlay.items, "item", kinds)
        return self


class Character(Frozen):
    id: Slug
    engine: EngineId
    profile: CharacterProfile
    overlay: CharacterOverlay

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def brief(self) -> str:
        return self.profile.brief

    @model_validator(mode="after")
    def _overlay_fits_the_character(self) -> Self:
        _require_engine(self.engine, "the character sheet", self.overlay.character)
        kinds: dict[EntityId, Kind] = {item.id: item.kind for item in self.profile.items}
        _require_overlay(self.engine, self.overlay.items, "item", kinds)
        return self


def _require_engine(engine: EngineId, purpose: str, data: EngineData) -> None:
    if data.engine != engine:
        raise ValueError(f"{purpose} holds {data.engine!r} data in the {engine!r} overlay")


def _require_overlay(
    engine: EngineId,
    overlay: Mapping[EntityId, EntityEngineData],
    kind: Kind,
    kinds: Mapping[EntityId, Kind],
) -> None:
    """An overlay keys off the authored ids, so a typo must fail at load, not go unread."""
    for entity_id, data in overlay.items():
        if kinds.get(entity_id) != kind:
            raise ValueError(f"the {engine!r} overlay names {entity_id!r}, no authored {kind}")
        _require_engine(engine, f"entity {entity_id!r}", data)


class AuthoredWorld(Frozen):
    """A composed world with engine data keyed by authored entity id."""

    world: WorldState
    engine_data: dict[EntityId, EntityEngineData] = Field(default_factory=dict)


def authored_world(scenario: Scenario, character: Character) -> AuthoredWorld:
    player = ActorEntity(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        location_id=scenario.world.starting_location_id,
    )
    entities: dict[EntityId, Entity] = {}
    for entity in (*scenario.world.entities, *character.profile.items, player):
        if entity.id in entities:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        # Loaded content outlives the mutable game state.
        entities[entity.id] = entity.model_copy(deep=True)
    return AuthoredWorld(
        world=WorldState(entities=entities),
        engine_data={
            **scenario.overlay.actors,
            **scenario.overlay.items,
            **character.overlay.items,
        },
    )
