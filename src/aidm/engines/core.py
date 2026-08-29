import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Protocol

from pydantic import BaseModel, JsonValue, ValidationError

from aidm.content.io import ENCODING
from aidm.content.model import Character
from aidm.state.creation import CreationStep, Picks, picked
from aidm.state.entities import (
    Counter,
    EngineId,
    Entity,
    EntityId,
    Slug,
    require_unique,
)
from aidm.state.facts import DiceEvent, Fact, entity_fact, roll, told_traces
from aidm.state.model import Game, WorldState
from aidm.state.play import DecisionOption, Line, PendingDecision, PendingOption, ToolCall
from aidm.state.scene import Scene
from aidm.state.tools import DirectorTool, Validate, transact

type EntityRenderer = Callable[[Entity], str]


# The small vocabulary an engine's rules are written with.


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def counter_fact(
    state: Game,
    entity: Entity,
    key: str,
    counter: Counter,
    delta: int,
    why: str,
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    card = moved if entity.id == state.player_id else f"{entity.name}: {moved}"
    trace = f"{state.label(entity)} {key} {delta:+d} -> {pool(counter)}"
    return entity_fact(entity, "counter_changed", f"{trace} ({why})", card=card)


def adjust(
    state: Game,
    entity: Entity,
    key: str,
    counter: Counter,
    amount: int,
    why: str,
) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [counter_fact(state, entity, key, counter, landed, why)]


def spend(state: Game, entity: Entity, key: str, counter: Counter, amount: int) -> list[Fact]:
    if counter.current < amount:
        raise ValueError(
            f"{entity.name} holds {counter.current} {key}, so {amount} cannot be spent."
        )
    counter.current -= amount
    return [counter_fact(state, entity, key, counter, -amount, f"spent {key}")]


def keep_highest(
    faces: Sequence[int], reason: str, rng: Random, *, label: str
) -> tuple[int, DiceEvent, Fact]:
    """The one roll shape all three engines make."""
    rolled, fact = roll(faces, reason, rng)
    kept = max(rolled)
    event = DiceEvent(
        label=label,
        faces=tuple(faces),
        rolled=rolled,
        result=str(kept),
        highlight=(rolled.index(kept),),
    )
    return kept, event, fact


def stake_decision(risk: str, call: ToolCall) -> PendingDecision:
    """`proceed` is the only option; the player's own words revise the plan instead."""
    return PendingDecision(
        kind="stake",
        prompt=f"{risk}\n\nProceed, or change your plan.",
        options=(PendingOption(id="proceed", label="Proceed", call=call),),
        allows_text=True,
    )


type Mechanics = dict[str, JsonValue]


@contextmanager
def rules[M: BaseModel](world: WorldState, model: type[M]) -> Generator[M]:
    """Parsed once at tool entry, written back once at exit; never nested."""
    parsed = model.model_validate(world.mechanics)
    yield parsed
    world.mechanics = parsed.model_dump(mode="json")


def mechanics_of[M: BaseModel](world: WorldState, model: type[M]) -> M:
    """The blob as this engine reads it, with the error path a bad write is refused by."""
    try:
        return model.model_validate(world.mechanics)
    except ValidationError as broken:
        first = broken.errors()[0]
        place = ".".join(str(part) for part in ("mechanics", *first["loc"]))
        raise ValueError(f"{place}: {first['msg']}") from broken


def mechanics_merged[M: BaseModel](
    model: type[M], base: dict[str, JsonValue], added: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """One level deep, so sheet maps join instead of replacing each other; `added` wins."""
    merged: dict[str, JsonValue] = dict(base)
    for key, value in added.items():
        held = merged.get(key)
        if isinstance(value, dict) and isinstance(held, dict):
            merged[key] = held | value
        else:
            merged[key] = value
    return model.model_validate(merged).model_dump(mode="json")


def sheet_of[S](sheets: Mapping[EntityId, S], entity: Entity) -> S:
    sheet = sheets.get(entity.id)
    if sheet is None:
        raise ValueError(f"{entity.name} has no character sheet")
    return sheet


ADVANCE_SPENT = "Spend one advance a party member has earned, when the player asks for it. "


def party_member(draft: Game, subject_id: EntityId) -> Entity:
    """An advance is a party member's own: nobody else's sheet is an engine's to grow."""
    subject = draft.world.require(subject_id)
    if subject_id not in (draft.player_id, *draft.world.party):
        raise ValueError(f"{subject.name} is not in the party")
    return subject


def check_packs(installed: Mapping[str, BaseModel], state: Game) -> None:
    if missing := sorted(set(state.packs) - set(installed)):
        raise ValueError(f"the game names packs not installed: {missing}")


def describe_rows(rows: tuple[tuple[str, str], ...], meanings: tuple[tuple[str, str], ...]) -> str:
    lines: list[str] = []
    for label, value in rows:
        if not value:
            continue
        lines.append(f"{label.lower()}: {value}")
        listed = value.split(", ")
        lines.extend(f"- {tag}: {detail}" for tag, detail in meanings if tag in listed)
    return "\n".join(lines)


# The contract: what a new engine supplies.


class CharacterCreation(ABC):
    @abstractmethod
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> Character:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


def load_packs[P: BaseModel](directories: Sequence[Path], model: type[P]) -> dict[str, P]:
    """Later directories win; a broken file raises rather than being skipped."""
    packs: dict[str, P] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            packs[path.stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
    return packs


def find_entry[T: DecisionOption](entries: Sequence[T], chosen: str) -> T:
    return next(entry for entry in entries if entry.id == chosen)


class NamedPack(Protocol):
    name: str


class PackCreation[P: NamedPack](CharacterCreation):
    def __init__(self, packs: Mapping[str, P]) -> None:
        self.packs = packs

    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        options = tuple(
            DecisionOption(id=one, label=one_pack.name) for one, one_pack in self.packs.items()
        )
        first = CreationStep(id="pack", prompt="Choose a character table set", options=options)
        pack = self.packs.get(picked(picks, "pack"))
        return (first,) if pack is None else (first, *self.steps_for(pack, picks))

    @abstractmethod
    def steps_for(self, pack: P, picks: Picks) -> tuple[CreationStep, ...]: ...


@dataclass(frozen=True, slots=True)
class PlayerAction:
    name: Slug
    description: str
    apply: Callable[[Game, Mapping[str, JsonValue]], Sequence[Fact]]
    offers: Callable[[Game], Sequence[tuple[str, dict[str, JsonValue]]]]


def player_action[A: BaseModel](
    name: Slug,
    description: str,
    args: type[A],
    act: Callable[[Game, A], Sequence[Fact]],
    offers: Callable[[Game], Sequence[tuple[str, A]]],
) -> PlayerAction:
    """Erases `A`: one engine tuple holds actions of different arg types. `offers` lists what the
    player can do right now, so a UI needs no form and no judgement."""
    return PlayerAction(
        name,
        description,
        lambda draft, raw: act(draft, args.model_validate(raw)),
        lambda state: tuple((label, one.model_dump(mode="json")) for label, one in offers(state)),
    )


def check_tool_names(engine: "Engine") -> None:
    require_unique(
        f"tool names of the {engine.id!r} engine",
        (one.name for one in (*engine.tools, *engine.resolvers)),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine:
    id: EngineId
    title: str
    instructions: str
    packs: Mapping[str, BaseModel]
    # The complete list: each engine names the world tools it wants, so core stays import-free.
    tools: tuple[DirectorTool, ...]
    # Reached only by picking the open decision's option that names one, never by the Director.
    resolvers: tuple[DirectorTool, ...] = ()
    creation: CharacterCreation
    validate: Validate
    sheet_rows: Callable[[Game], tuple[tuple[str, str], ...]]
    mechanics_merge: Callable[[Mechanics, Mechanics], Mechanics]
    mechanics_without: Callable[[Mechanics, EntityId], Mechanics]
    # The character file as this engine's blob; 3.1 replaces it with `Character.mechanics`.
    character_mechanics: Callable[[Character], Mechanics]
    scene: Callable[[Game], Scene]
    # None while the game can still be played on; the text the player is shown when it cannot.
    over: Callable[[Game], str | None] = lambda state: None
    player_actions: tuple[PlayerAction, ...] = ()
    authoring_instructions: str = ""

    def __post_init__(self) -> None:
        check_tool_names(self)

    def authoring_context(self, pack_ids: tuple[Slug, ...]) -> str:
        # Defaults restate rules the guidance already carries; dropping them halves the prompt.
        packs = {
            pack_id: self.packs[pack_id].model_dump(mode="json", exclude_defaults=True)
            for pack_id in pack_ids
        }
        return f"{self.authoring_instructions}\n\nSELECTED PACK CONTENT\n{json.dumps(packs)}"

    def tool(self, name: str) -> DirectorTool | None:
        return next((one for one in (*self.tools, *self.resolvers) if one.name == name), None)

    def restored(self, raw: str) -> Game:
        state = Game.model_validate_json(raw)
        if state.engine != self.id:
            raise ValueError(f"the save plays {state.engine!r}, not {self.id!r}")
        if state.pending is not None:
            for option in state.pending.options:
                found = self.tool(option.call.name)
                if found is None:
                    raise ValueError(
                        f"the {self.id!r} engine has no tool {option.call.name!r} to play "
                        f"option {option.id!r}"
                    )
                _ = found.args.model_validate(option.call.args)
        self.validate(state)
        return state


def offered(
    engine: Engine, state: Game
) -> tuple[tuple[PlayerAction, str, dict[str, JsonValue]], ...]:
    return tuple(
        (one, label, args) for one in engine.player_actions for label, args in one.offers(state)
    )


def play_action(
    engine: Engine, state: Game, name: Slug, raw: Mapping[str, JsonValue], rng: Random
) -> tuple[Game, tuple[Fact, ...]]:
    """The exchange it records is how the chat, the journal and the next Director prompt see it."""
    if state.pending is not None:
        raise ValueError(f"the rules wait on the player's answer first: {state.pending.prompt}")
    match = next(
        (
            (one, label)
            for one, label, args in offered(engine, state)
            if one.name == name and args == dict(raw)
        ),
        None,
    )
    if match is None:
        raise ValueError(f"{name!r} with {json.dumps(dict(raw))} is not offered right now")
    found, offered_as = match

    def play(draft: Game, _rng: Random) -> tuple[Fact, ...]:
        facts = tuple(found.apply(draft, raw))
        # Only told facts reach the player: an untold trace may name hidden canon.
        told = Line(text="\n".join(told_traces(facts)) or "Nothing changed.")
        draft.record(engine.scene(draft).label, offered_as, (told,), facts)
        return facts

    return transact(engine.validate, state.draft(), play, rng)
