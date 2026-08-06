from collections.abc import Callable, Mapping
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.base import PLAYER_ID, EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.sheet import Sheet
from aidm.state.world import ScenarioMeta, WorldState, check_placement

type Rules = dict[str, JsonValue]


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
            holder = None if entity.parent_id is None else by_id.get(entity.parent_id)
            check_placement(entity, holder)
        return self


class ScenarioOverlay(Frozen):
    """`<engine>.json`: what one ruleset adds to the entities that need it."""

    entities: dict[EntityId, Rules] = Field(default_factory=dict)


class CharacterProfile(Frozen):
    """`base.json`: who the character is, and the gear they start holding."""

    name: str
    brief: str
    items: tuple[Entity, ...] = ()

    @model_validator(mode="after")
    def _held_and_known(self) -> Self:
        """Own gear is known gear: an unknown carried item would be hidden canon inside the
        inventory the Narrator is shown, so the two prompts would contradict each other."""
        wrong_kind = sorted(item.id for item in self.items if item.kind != "item")
        if wrong_kind:
            raise ValueError(f"a character's profile holds items only: {wrong_kind}")
        misplaced = sorted(item.id for item in self.items if item.parent_id != PLAYER_ID)
        if misplaced:
            raise ValueError(f"a character's items start in their own hands: {misplaced}")
        unknown = sorted(item.id for item in self.items if not item.known)
        if unknown:
            raise ValueError(f"a character knows the gear they start with: {unknown}")
        return self


class CharacterOverlay(Frozen):
    character: Rules
    entities: dict[EntityId, Rules] = Field(default_factory=dict)


class Scenario(Frozen):
    id: Slug
    engine: EngineId
    world: ScenarioWorld
    overlay: ScenarioOverlay

    @property
    def meta(self) -> ScenarioMeta:
        return self.world.meta

    @model_validator(mode="after")
    def _overlay_fits_the_world(self) -> Self:
        _require_authored(self.engine, self.overlay.entities, self.world.entities)
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
        _require_authored(self.engine, self.overlay.entities, self.profile.items)
        return self


def _require_authored(
    engine: EngineId,
    overlay: Mapping[EntityId, Rules],
    authored: tuple[Entity, ...],
) -> None:
    """An overlay keys off the authored ids, so a typo must fail at load, not go unread."""
    ids = {entity.id for entity in authored}
    unknown = sorted(entity_id for entity_id in overlay if entity_id not in ids)
    if unknown:
        raise ValueError(f"the {engine!r} overlay names unauthored ids: {unknown}")


class AuthoredEntity(Frozen):
    entity: Entity
    rules: Rules = Field(default_factory=dict)


class AuthoredWorld(Frozen):
    entities: dict[EntityId, AuthoredEntity] = Field(default_factory=dict)


def authored_world(scenario: Scenario, character: Character) -> AuthoredWorld:
    player = Entity(
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        parent_id=scenario.world.starting_location_id,
    )
    overlay = {**scenario.overlay.entities, **character.overlay.entities}
    entities: dict[EntityId, AuthoredEntity] = {}
    for authored in (*scenario.world.entities, *character.profile.items, player):
        if authored.id in entities:
            raise ValueError(f"authored entity id {authored.id!r} appears twice")
        # Loaded content outlives the mutable game state.
        entities[authored.id] = AuthoredEntity(
            entity=authored.model_copy(deep=True),
            rules=dict(overlay.get(authored.id, {})),
        )
    return AuthoredWorld(entities=entities)


def compose_world(
    authored: AuthoredWorld,
    player: Sheet,
    rules: Callable[[AuthoredEntity], Sheet],
) -> WorldState:
    records = {
        entity_id: {
            "entity": record.entity,
            "rules": player if entity_id == PLAYER_ID else rules(record),
        }
        for entity_id, record in authored.entities.items()
    }
    return WorldState.model_validate({"records": records})
