import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import JsonValue, TypeAdapter
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.authored import Binding, CreatedCharacter
from aidm.content.store import ENCODING
from aidm.state.base import EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.creation import CreationStep, Picks
from aidm.state.facts import Fact
from aidm.state.plan import Resolution, TurnPlanBase
from aidm.state.world import GameState

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.loner3e.rules",
    "aidm.engines.twentyfourxx.rules",
    "aidm.engines.cairn2e.rules",
)
ENGINE = "ENGINE"
WORLD_EXAMPLES: Path = Path(__file__).parent / "examples.json"

type EntityRenderer = Callable[[Entity], str]


class Offer(Frozen):
    """One change a subsystem holds open for one subject, already resolved out of content."""

    subject_id: EntityId
    prompt: str
    text: str = ""


class ProposalBase(Frozen):
    """What a subsystem writes, in the engine's own vocabulary."""


class Subsystem(ABC):
    """Optional capability an engine plugs in."""

    id: ClassVar[Slug]
    proposal_type: ClassVar[type[ProposalBase]]

    def __init__(self, engine_dir: Path) -> None:
        self.instructions = engine_text(engine_dir / f"{self.id}.md")

    @abstractmethod
    def offers(self, state: GameState) -> tuple[Offer, ...]: ...

    @abstractmethod
    def resolve(
        self, draft: GameState, offer: Offer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        """Mutates the draft; the caller's commit revalidates both halves of the copy."""

    @abstractmethod
    def violation(self, state: GameState, offer: Offer, proposal: ProposalBase) -> str | None:
        """One legality rule for the advisor's retry and for the commit, so neither can drift."""


class Creation(ABC):
    """The optional creation capability: an engine without one offers no new-character page."""

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Engine(ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of the
    state core keeps but cannot read. What content it needs is its own to load."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    plan_type: type[TurnPlanBase]
    # What a continuation answers with: the plan's own beat, without the turn's framing.
    beat_type: type[Frozen]
    engine_dir: ClassVar[Path]

    def __init__(self, extra_packs: Path | None = None) -> None:
        self.director_instructions: str = (
            engine_text(self.engine_dir / "director.md")
            + _effect_vocabulary()
            + _examples(self.engine_dir, self.plan_type)
        )
        # An engine with content advertises its own lookups; one without teaches the model no tool.
        self.director_toolsets: tuple[AbstractToolset[object], ...] = ()
        self.subsystems: tuple[Subsystem, ...] = ()
        # An engine that creates characters replaces this; the app offers only what it finds.
        self.creation: Creation | None = None

    @abstractmethod
    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        """Refuses an authored overlay this engine cannot read."""

    def binding(self) -> Binding:
        return Binding(
            engine=self.id, parse_effect=self.parse_effect, check_overlay=self.check_overlay
        )

    @abstractmethod
    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        """Writes the mechanics of a new game from the authored rules; the caller validates."""

    @abstractmethod
    def validate(self, state: GameState) -> None:
        """Refuses a state whose mechanics are missing or contradict the world; never repairs it."""

    @abstractmethod
    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        """Gives an entity created during play whatever mechanics this engine tracks for it."""

    @abstractmethod
    def parse_effect(self, effect: JsonValue) -> Frozen:
        """This engine's effect vocabulary: raises on an authored effect it cannot apply."""

    @abstractmethod
    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        """Applies one authored hook effect, parsed through this engine's own vocabulary."""

    @abstractmethod
    def renderer(self, state: GameState) -> EntityRenderer: ...

    @abstractmethod
    def check_beat(self, state: GameState, beat: Frozen) -> str | None:
        """Must not raise: an output validator that raises kills the turn instead of retrying.
        A plan is a beat with framing on it, so the first beat of a turn comes through here too."""

    @abstractmethod
    def resolve_beat(self, draft: GameState, beat: Frozen, rng: Random) -> Resolution: ...


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
    header = (
        "## Worked plans\n\nOne plan per turn, each opening its own beat; a later beat of the "
        "same turn is the same shape without `focus` or `speaker_id`. A field left out sits at "
        "its default."
    )
    return "\n\n" + "\n\n".join([header, *blocks])


def _effect_vocabulary() -> str:
    """Only the world half is shared: what an engine's own effects mean is its own to teach."""
    entries = TypeAdapter(list[JsonValue]).validate_json(engine_text(WORLD_EXAMPLES))
    lines = "\n".join(json.dumps(entry) for entry in entries)
    header = (
        "## World effects\n\nA worked example of every effect that changes the world. Ids, keys, "
        "and traits here are illustrative: use the exact ids the scene shows. Most beats need few "
        "or no effects: an empty `effects` is a normal answer. But a beat whose fiction starts or "
        "ends a lasting state — a condition taking hold or passing — must write that trait "
        "change, with or without an action: nothing records it otherwise."
    )
    return f"\n\n{header}\n\n```json\n{lines}\n```"
