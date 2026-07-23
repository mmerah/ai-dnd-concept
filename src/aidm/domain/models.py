"""Every authoritative type. All frozen and JSON-serializable: state is data, not objects."""

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Ability = Literal["strength", "dexterity", "intellect", "wisdom"]
Kind = Literal["npc", "location", "item"]
Role = Literal["director", "actor", "narrator", "maintainer", "creator"]

ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 1


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def updated[T: Frozen](obj: T, **changes: object) -> T:
    """Copy with changes, revalidated — `model_copy(update=)` would skip `extra="forbid"`."""
    return type(obj).model_validate(obj.model_dump() | changes)


class Attributes(Frozen):
    strength: int = 10
    dexterity: int = 10
    intellect: int = 10
    wisdom: int = 10


class Character(Frozen):
    name: str
    attributes: Attributes = Attributes()
    hp: int = 10
    max_hp: int = 10
    inventory: list[str] = Field(default_factory=list)
    location: str


class EntityDetail(Frozen):
    """What a Creator adds on top of a growth request."""

    description: str
    hook: str


class Entity(Frozen):
    id: str
    kind: Kind
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False  # revealed to the player; unknown entities are Director-only canon
    authored: bool = True  # False once a Creator invented it mid-play


class Scenario(Frozen):
    title: str
    premise: str
    entities: list[Entity] = Field(default_factory=list)


class Exchange(Frozen):
    prompt: str
    narration: str


class GameState(Frozen):
    version: int = SAVE_VERSION
    character: Character
    scenario: Scenario
    history: list[Exchange] = Field(default_factory=list)
    turn: int = 0


class Direction(Frozen):
    """Director output. `guidance` is private to the Actor; only `tone` reaches the Narrator."""

    guidance: str
    tone: str
    speaker_id: str | None = None


class GrowthRequest(Frozen):
    kind: Kind
    name: str
    brief: str


class Growth(Frozen):
    requests: list[GrowthRequest] = Field(default_factory=list)


def known(scenario: Scenario) -> list[Entity]:
    return [e for e in scenario.entities if e.known]


def hidden(scenario: Scenario) -> list[Entity]:
    return [e for e in scenario.entities if not e.known]


def find(scenario: Scenario, entity_id: str) -> Entity | None:
    return next((e for e in scenario.entities if e.id == entity_id), None)


def find_by_name(scenario: Scenario, name: str) -> Entity | None:
    return next((e for e in scenario.entities if e.name.lower() == name.lower()), None)
