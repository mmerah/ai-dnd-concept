from pydantic import Field, JsonValue

from aidm.state.entities import EngineId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.model import ScenarioMeta
from aidm.state.play import Exchange, PendingDecision

type Payload = dict[str, JsonValue]


class SaveEnvelope(Frozen):
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    turn: int = Field(ge=0)
    history: tuple[Exchange, ...] = ()
    turn_facts: tuple[Fact, ...] = ()
    pending: PendingDecision | None = None
    notes: tuple[str, ...] = ()
    payload: Payload


class ScenarioEnvelope(Frozen):
    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    grows: bool = False
    art_style: str = ""
    payload: Payload


class CharacterEnvelope(Frozen):
    id: Slug
    engine: EngineId
    name: str
    brief: str
    payload: Payload
