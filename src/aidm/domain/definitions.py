from typing import Self

from pydantic import model_validator

from ..utils.models import Frozen
from .base import PLAYER_ID, EntityId
from .engine import EngineData, EngineRef, EngineStamp, require_envelope
from .entities import EntityDefinition, StartingItemDefinition


class ScenarioMeta(Frozen):
    title: str
    premise: str


class CharacterDefinition(Frozen):
    name: str
    brief: str
    engine: EngineRef
    engine_data: EngineData
    starting_items: tuple[StartingItemDefinition, ...] = ()


class ScenarioDefinition(Frozen):
    meta: ScenarioMeta
    engine: EngineRef
    engine_data: EngineData | None = None
    starting_location_id: EntityId
    entities: tuple[EntityDefinition, ...] = ()

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


def validate_definition_engines(
    scenario: ScenarioDefinition,
    character: CharacterDefinition,
    stamp: EngineStamp,
) -> None:
    if scenario.engine != character.engine:
        raise ValueError(
            f"scenario engine is {scenario.engine.model_dump()}, "
            f"character engine is {character.engine.model_dump()}"
        )
    selected = EngineRef(id=stamp.id, rules_version=stamp.rules_version)
    if scenario.engine != selected:
        raise ValueError(
            f"definition engine is {scenario.engine.model_dump()}, "
            f"installed engine is {selected.model_dump()}"
        )
    envelopes = [
        ("character engine_data", character.engine_data),
        *([] if scenario.engine_data is None else [("scenario engine_data", scenario.engine_data)]),
        *[
            (f"scenario entity {entity.id!r} engine_data", entity.engine_data)
            for entity in scenario.entities
            if entity.engine_data is not None
        ],
        *[
            (f"starting item {item.name!r} engine_data", item.engine_data)
            for item in character.starting_items
            if item.engine_data is not None
        ],
    ]
    for purpose, envelope in envelopes:
        require_envelope(envelope, stamp, purpose)
