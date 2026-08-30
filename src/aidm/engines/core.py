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
from aidm.content.model import AuthoringBrief, Character, CharacterPayload, ScenarioPayload
from aidm.kernel.envelope import CharacterEnvelope, SaveEnvelope
from aidm.kernel.views import (
    ArtSubject,
    CreationPreview,
    DirectorView,
    NarratorView,
    PlayerPrompt,
    PlayerView,
    Views,
)
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
from aidm.state.model import Game, Mechanics, MechanicsPatch, WorldPayload, WorldState
from aidm.state.play import DecisionOption, PendingDecision, PendingOption, SpokenLine
from aidm.state.scene import Scene, VisibleScene
from aidm.state.tools import DirectorTool, Validate, transact

type EntityRenderer = Callable[[Entity], str]


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
    rolled, fact = roll(faces, reason, rng)
    kept = max(rolled)
    event = DiceEvent(
        label=label,
        faces=tuple(faces),
        rolled=rolled,
        highlight=(rolled.index(kept),),
    )
    return kept, event, fact


def stake_decision(risk: str, name: str, args: dict[str, JsonValue]) -> PendingDecision:
    """`proceed` is the only option; the player's own words revise the plan instead."""
    return PendingDecision(
        kind="stake",
        prompt=f"{risk}\n\nProceed, or change your plan.",
        options=(PendingOption(id="proceed", label="Proceed", name=name, args=args),),
        allows_text=True,
    )


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


def mechanics_patched[M: BaseModel](
    model: type[M],
    blob: Mechanics,
    added: Mechanics,
    removed_ids: Sequence[EntityId],
    *,
    entity_maps: tuple[str, ...],
) -> Mechanics:
    """Merges one level deep so sheet maps join instead of replacing each other; `added` wins.
    Validated before ids drop, so a patch cannot hide a bad sheet by adding and removing it."""
    merged: Mechanics = dict(blob)
    for key, value in added.items():
        held = merged.get(key)
        merged[key] = held | value if isinstance(value, dict) and isinstance(held, dict) else value
    patched = model.model_validate(merged).model_dump(mode="json")
    dropped = set(removed_ids)
    for key in entity_maps:
        held: JsonValue = patched.get(key)
        if isinstance(held, dict):
            patched[key] = {one: sheet for one, sheet in held.items() if one not in dropped}
    return patched


def mechanics_delta(base: Mechanics, added: Mechanics) -> Mechanics:
    """One level deep, matching `mechanics_patched`: a new NPC's sheet sits inside `sheets`."""
    delta: Mechanics = {}
    for key, value in added.items():
        held = base.get(key)
        if held == value:
            continue
        if isinstance(value, dict) and isinstance(held, dict):
            if inner := {name: one for name, one in value.items() if held.get(name) != one}:
                delta[key] = inner
        else:
            delta[key] = value
    return delta


def sheet_of[S](sheets: Mapping[EntityId, S], entity: Entity) -> S:
    sheet = sheets.get(entity.id)
    if sheet is None:
        raise ValueError(f"{entity.name} has no character sheet")
    return sheet


ADVANCE_SPENT = "Spend one advance a party member has earned, when the player asks for it. "


def owed_notes[S](
    state: Game, sheets: Mapping[EntityId, S], is_owed: Callable[[S], bool]
) -> tuple[tuple[str, str], ...]:
    """Chapters played standing above the ledger of advances taken, one note each."""
    # An advance mid-suspension could invalidate the frozen call an open decision holds.
    if state.pending is not None:
        return ()
    owed = [
        f"- {state.world.require(one).name} has an advance owed; call advance only when the "
        "player asks for it."
        for one in (state.player_id, *state.world.party)
        if (sheet := sheets.get(one)) is not None and is_owed(sheet)
    ]
    return (("ADVANCES OWED", "\n".join(owed)),) if owed else ()


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


class CharacterCreation(ABC):
    @abstractmethod
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> Character:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""

    def created(
        self, name: str, brief: str, picks: Picks
    ) -> tuple[CharacterEnvelope, CreationPreview]:
        character = self.create(name, brief, picks)
        payload = character.payload.model_dump(mode="json")
        envelope = CharacterEnvelope(
            id=character.id,
            engine=character.engine,
            name=character.name,
            brief=character.brief,
            payload=payload,
        )
        rows = (
            *((trait.name, trait.text) for trait in character.traits),
            *(("carrying", item.name) for item in character.items),
        )
        return envelope, CreationPreview(rows=rows)


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


def authoring_guidance(text: str, packs: Mapping[str, BaseModel], chosen: tuple[Slug, ...]) -> str:
    # Defaults restate rules the guidance already carries; dropping them halves the prompt.
    selected = {
        pack_id: packs[pack_id].model_dump(mode="json", exclude_defaults=True) for pack_id in chosen
    }
    return f"{text}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine:
    """Satisfies `kernel.protocol.Engine` structurally; the extra fields are the Phase-1 shim
    the Phase-3 port deletes."""

    id: EngineId
    title: str
    instructions: str
    packs: Mapping[str, BaseModel]
    # The envelope payload models this engine parses at stage two of every disk read.
    state: type[BaseModel] = WorldPayload
    scenario: type[BaseModel] = ScenarioPayload
    character: type[BaseModel] = CharacterPayload
    # The complete list: each engine names the world tools it wants, so core stays import-free.
    tools: tuple[DirectorTool, ...]
    # Reached only by picking the open decision's option that names one, never by the Director.
    resolvers: tuple[DirectorTool, ...] = ()
    creation: CharacterCreation
    validate: Validate
    mechanics_patch: MechanicsPatch
    scene: Callable[[Game], Scene]
    # None while the game can still be played on; the text the player is shown when it cannot.
    over: Callable[[Game], str | None] = lambda state: None
    player_actions: tuple[PlayerAction, ...] = ()
    # Selected packs, the world an extension pass stands on or None, and the opening-slice flag.
    authoring_brief: Callable[[tuple[Slug, ...], WorldState | None, bool], AuthoringBrief]
    growth_due: Callable[[Game, int], bool] = lambda state, frontier: False

    def __post_init__(self) -> None:
        require_unique(
            f"tool names of the {self.id!r} engine",
            (one.name for one in (*self.tools, *self.resolvers)),
        )

    def tool(self, name: str) -> DirectorTool | None:
        return next((one for one in (*self.tools, *self.resolvers) if one.name == name), None)

    def restored(self, raw: str) -> Game:
        envelope = SaveEnvelope.model_validate_json(raw)
        if envelope.engine != self.id:
            raise ValueError(f"the save plays {envelope.engine!r}, not {self.id!r}")
        payload = self.state.model_validate(envelope.payload)
        state = Game.model_validate(envelope.model_dump() | {"payload": payload})
        if state.pending is not None:
            for option in state.pending.options:
                found = self.tool(option.name)
                if found is None:
                    raise ValueError(
                        f"the {self.id!r} engine has no tool {option.name!r} to play "
                        f"option {option.id!r}"
                    )
                _ = found.args.model_validate(option.args)
        self.validate(state)
        return state

    def views(self, state: Game) -> Views:
        scene = self.scene(state)
        visible = VisibleScene.revealed_from(scene, state.world)

        def subject(entity_id: EntityId) -> ArtSubject:
            entity = state.world.require(entity_id)
            return ArtSubject(id=entity.id, name=entity.name, brief=entity.brief)

        prompt = state.pending
        return Views(
            director=DirectorView(sections=scene.director_sections),
            narrator=NarratorView(
                label=visible.label,
                summary=visible.summary,
                sections=visible.sections,
                prompts=visible.prompts,
                art_prompt=visible.art_prompt,
                subjects=tuple(subject(one) for one in visible.art_subject_ids),
            ),
            player=PlayerView(
                player=subject(state.player_id),
                prompt=None
                if prompt is None
                else PlayerPrompt(
                    prompt=prompt.prompt,
                    options=tuple(
                        DecisionOption(id=one.id, label=one.label, detail=one.detail)
                        for one in prompt.options
                    ),
                    allows_text=prompt.allows_text,
                ),
            ),
        )


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
        told = SpokenLine(text="\n".join(told_traces(facts)) or "Nothing changed.")
        draft.record(engine.scene(draft).label, offered_as, draft.player_speaker(), (told,), facts)
        return facts

    return transact(engine.validate, state.draft(), play, rng)
