import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from random import Random
from typing import ClassVar, Self

from pydantic import Field, JsonValue, TypeAdapter, model_validator
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.authored import CreatedCharacter, Rules
from aidm.content.store import ENCODING
from aidm.state.base import EngineId, Entity, EntityId, Frozen
from aidm.state.creation import Picks, Step
from aidm.state.effects import WorldEffect, effect_key, effect_keys
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase
from aidm.state.world import GameState

ENGINE_MODULES: tuple[str, ...] = ("aidm.engines.story.rules", "aidm.engines.oracle.rules")
ENGINE = "ENGINE"

type EntityRenderer = Callable[[Entity], str]


class AdvancementOffer(Frozen):
    """One pending advancement, already resolved out of content."""

    prompt: str
    text: str = ""
    # What the advancement hands over unasked. The advisor never picks these; the prompt carries
    # them so it can see what the growth already gives before it answers what is left.
    granted: tuple[str, ...] = ()
    options: tuple[str, ...] = ()
    choose: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        if bool(self.choose) != bool(self.options):
            raise ValueError("options and choose are set together, or neither is")
        if self.choose > len(self.options):
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


class ProposalBase(Frozen):
    """What an advancement writes, in the engine's own vocabulary."""


class Advancement(ABC):
    """The optional growth capability: an engine without one never offers the player a change."""

    proposal_type: ClassVar[type[ProposalBase]]

    def __init__(self, engine_dir: Path) -> None:
        self.instructions = engine_text(engine_dir / "advancement.md")

    @abstractmethod
    def offered(self, state: GameState) -> AdvancementOffer | None: ...

    @abstractmethod
    def advance(self, draft: GameState, proposal: ProposalBase) -> tuple[Fact, ...]:
        """Mutates the draft; the caller's commit revalidates both halves of the copy."""

    @abstractmethod
    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        """One legality rule for the advisor's retry and for the commit, so neither can drift."""


class Creation(ABC):
    """The optional creation capability: an engine without one offers no new-character page."""

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[Step, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Engine(ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of the
    state core keeps but cannot read. What content it needs is its own to load."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    plan_type: ClassVar[type[TurnPlanBase]]
    engine_dir: ClassVar[Path]

    def __init__(self) -> None:
        self.director_instructions: str = (
            engine_text(self.engine_dir / "director.md")
            + _effect_vocabulary()
            + _examples(self.engine_dir, self.plan_type)
        )
        # An engine with content advertises its own lookups; one without teaches the model no tool.
        self.director_toolsets: tuple[AbstractToolset[object], ...] = ()
        # An engine that grows its characters replaces this; the app offers only what it finds.
        self.advancement: Advancement | None = None
        # An engine that creates characters replaces this; the app offers only what it finds.
        self.creation: Creation | None = None

    @abstractmethod
    def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None:
        """Writes the mechanics of a new game from the authored rules; the caller commits."""

    @abstractmethod
    def commit(self, state: GameState) -> None:
        """Called at load, at the end of every transaction, and after a new game is composed: it
        gives an entity created during play its mechanics and validates the half core cannot read.
        """

    @abstractmethod
    def renderer(self, state: GameState) -> EntityRenderer: ...

    @abstractmethod
    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        """Must not raise: an output validator that raises kills the turn instead of retrying."""

    @abstractmethod
    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]: ...


def engines() -> tuple[type[Engine], ...]:
    """Imported by name, because a static import would put core back inside the engine packages."""
    found = tuple(_engine_class(module) for module in ENGINE_MODULES)
    if len({engine.id for engine in found}) != len(found):
        raise ValueError(f"engine ids collide: {[engine.id for engine in found]}")
    return found


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in engines())


def engine_class(engine_id: EngineId) -> type[Engine]:
    found = next((engine for engine in engines() if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def engine_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


def _engine_class(module: str) -> type[Engine]:
    declared = getattr(import_module(module), ENGINE, None)
    if not (isinstance(declared, type) and issubclass(declared, Engine)):
        raise ValueError(f"engine module {module!r} declares no {ENGINE}")
    return declared


def _examples(engine_dir: Path, plan_type: type[TurnPlanBase]) -> str:
    path = engine_dir / "examples.json"
    if not path.is_file():
        return ""
    entries = TypeAdapter(list[JsonValue]).validate_json(engine_text(path))
    blocks: list[str] = []
    for number, entry in enumerate(entries, start=1):
        _ = plan_type.model_validate(entry)
        blocks.append(f"Example {number}:\n\n```json\n{json.dumps(entry, indent=2)}\n```")
    if not blocks:
        return ""
    header = "## Worked plans\n\nOne plan per turn; a field left out sits at its default."
    return "\n\n" + "\n\n".join([header, *blocks])


def _effect_vocabulary() -> str:
    """Only the world half is shared: what an engine's own effects mean is its own to teach."""
    entries = TypeAdapter(list[JsonValue]).validate_json(
        engine_text(Path(__file__).parent / "examples.json")
    )
    checked = TypeAdapter(list[WorldEffect]).validate_python(entries)
    missing = effect_keys(WorldEffect.__value__) - {effect_key(entry) for entry in checked}
    if missing:
        raise ValueError(f"the shared examples.json teaches no {sorted(missing)}")
    lines = "\n".join(json.dumps(entry) for entry in entries)
    header = (
        "## World effects\n\nA worked example of every effect that changes the world. Ids, keys, "
        "and traits here are illustrative: use the exact ids the scene shows. Most turns need few "
        "or no effects: an empty `effects` with no branches is a normal plan. But a turn whose "
        "fiction starts or ends a lasting state — a condition taking hold or passing — must write "
        "that trait change, with or without an action: nothing records it otherwise."
    )
    return f"\n\n{header}\n\n```json\n{lines}\n```"
