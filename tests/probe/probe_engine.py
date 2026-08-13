from random import Random
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.base import Entity, EntityId, Frozen, Mutable, Slug
from aidm.state.dice import roll
from aidm.state.facts import Fact

SOURCE = "probe"
MOMENTUM_FLOOR = -6
MOMENTUM_CEILING = 10
TRACK_TICKS = 40
# What one strong strike marks on a track of each rank; a weak one marks half.
MARKS: dict[str, int] = {"troublesome": 12, "dangerous": 8, "formidable": 4}

type Outcome = Literal["strong", "weak", "miss"]


class Track(Mutable):
    name: str
    rank: Literal["troublesome", "dangerous", "formidable"]
    ticks: int = Field(default=0, ge=0, le=TRACK_TICKS)
    resolved: bool = False

    @property
    def boxes(self) -> int:
        return self.ticks // 4

    @model_validator(mode="after")
    def _a_resolved_track_is_full(self) -> Self:
        if self.resolved and self.ticks < TRACK_TICKS:
            raise ValueError(f"track {self.name!r} is resolved at only {self.boxes}/10 boxes")
        return self


class Fighter(Mutable):
    edge: int = Field(ge=0, le=4)
    heart: int = Field(ge=0, le=4)
    iron: int = Field(ge=0, le=4)
    debilities: tuple[Slug, ...] = ()
    momentum: int = Field(default=2, ge=MOMENTUM_FLOOR, le=MOMENTUM_CEILING)
    tracks: dict[Slug, Track] = Field(default_factory=dict)

    @property
    def ceiling(self) -> int:
        return MOMENTUM_CEILING - len(self.debilities)

    @model_validator(mode="after")
    def _momentum_sits_under_its_own_ceiling(self) -> Self:
        if self.momentum > self.ceiling:
            raise ValueError(f"momentum {self.momentum} exceeds this fighter's {self.ceiling}")
        return self


class Mechanics(Mutable):
    """Everything this engine owns: core persists it as opaque JSON and reads no field of it."""

    fighters: dict[EntityId, Fighter] = Field(default_factory=dict)


class Strike(Frozen):
    """The one action this engine resolves: an armed attempt against a progress track."""

    act: Literal["strike"] = "strike"
    actor_id: EntityId
    stat: Literal["edge", "heart", "iron"]
    track_id: Slug


def create(payload: JsonValue) -> Mechanics:
    """The engine is the only validator of its own persisted half."""
    return Mechanics.model_validate(payload)


def commit(mechanics: Mechanics) -> Mechanics:
    """One engine-owned commit path: the whole payload revalidates, or the turn is refused."""
    return Mechanics.model_validate(mechanics.model_dump())


def initialize(mechanics: Mechanics, entity: Entity) -> None:
    """An entity created during play gets its mechanics from the engine that commits them."""
    if entity.kind == "actor" and entity.id not in mechanics.fighters:
        mechanics.fighters[entity.id] = Fighter(edge=1, heart=1, iron=1)


def render(mechanics: Mechanics, entity: Entity) -> str:
    fighter = mechanics.fighters.get(entity.id)
    if fighter is None:
        return entity.brief
    tracks = ", ".join(f"{t.name} {t.boxes}/10" for t in fighter.tracks.values()) or "no tracks"
    return (
        f"{entity.name}: edge {fighter.edge}, heart {fighter.heart}, iron {fighter.iron}; "
        f"momentum {fighter.momentum}/{fighter.ceiling}; {tracks}"
    )


def resolve(mechanics: Mechanics, action: Strike, rng: Random) -> list[Fact]:
    fighter = mechanics.fighters[action.actor_id]
    track = fighter.tracks[action.track_id]
    stat = {"edge": fighter.edge, "heart": fighter.heart, "iron": fighter.iron}[action.stat]
    rolled, action_fact = roll("1d6", f"{action.stat} strike", rng)
    scored = rolled.total + stat
    first, first_fact = roll("1d10", "challenge", rng)
    second, second_fact = roll("1d10", "challenge", rng)
    outcome = _outcome(scored, first.total, second.total)
    marked = _mark(track, outcome)
    fighter.momentum = _momentum(fighter, outcome)
    return [
        action_fact,
        first_fact,
        second_fact,
        Fact(
            source=SOURCE,
            kind="strike_resolved",
            trace=f"{action.actor_id} strikes {track.name}: {outcome}, +{marked} ticks",
            narrator=f"the attempt lands {outcome}",
            data={"outcome": outcome, "ticks": marked, "momentum": fighter.momentum},
        ),
    ]


def _outcome(scored: int, first: int, second: int) -> Outcome:
    match (scored > first) + (scored > second):
        case 2:
            return "strong"
        case 1:
            return "weak"
        case _:
            return "miss"


def _mark(track: Track, outcome: Outcome) -> int:
    full = MARKS[track.rank]
    marked = {"strong": full, "weak": full // 2, "miss": 0}[outcome]
    track.ticks = min(TRACK_TICKS, track.ticks + marked)
    return marked


def _momentum(fighter: Fighter, outcome: Outcome) -> int:
    moved = fighter.momentum + {"strong": 1, "weak": 0, "miss": -1}[outcome]
    return max(MOMENTUM_FLOOR, min(fighter.ceiling, moved))
