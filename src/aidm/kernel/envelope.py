from pydantic import Field, JsonValue

from aidm.state.entities import EngineId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.model import ScenarioMeta
from aidm.state.play import Exchange, PendingDecision

# The envelope reads a save whole; the engine's own state is the discriminated payload.
type RawPayload = dict[str, JsonValue]


class SaveEnvelope(Frozen):
    """Read to list saves on the home page, where no engine is built yet."""

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
    payload: RawPayload


class ScenarioEnvelope(Frozen):
    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    art_style: str = ""
    payload: RawPayload


class CharacterEnvelope(Frozen):
    id: Slug
    engine: EngineId
    name: str
    brief: str
    payload: RawPayload
