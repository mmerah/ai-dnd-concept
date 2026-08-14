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
from aidm.state.plan import DirectorBeat, DirectorPlan, Resolution
from aidm.state.world import GameState

from .vocabulary import EFFECT_CALLS, EFFECTS_CARD, ROLLS_CARD, card, translate

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.loner3e.rules",
    "aidm.engines.twentyfourxx.rules",
    "aidm.engines.cairn2e.rules",
)
ENGINE = "ENGINE"
WORKED_PLANS = (
    "One plan per turn, each opening its own beat; a later beat of the same turn is the same shape "
    "without `focus` or `speaker_id`. Most beats need few or no effects, and an empty `effects` is "
    "a normal answer. But a beat whose fiction starts or ends a lasting state — a condition taking "
    "hold or passing — must write that trait change: nothing records it otherwise."
)

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
    engine_dir: ClassVar[Path]
    # What a beat's `roll` may name: this engine's own vocabulary, by the name a call gives it.
    actions: ClassVar[Mapping[Slug, type[Frozen]]]

    def __init__(self, extra_packs: Path | None = None) -> None:
        parts = (
            engine_text(self.engine_dir / "director.md"),
            card("Rolls", ROLLS_CARD, self.actions),
            card("Effects", EFFECTS_CARD, EFFECT_CALLS),
            self._worked_plans(),
        )
        self.director_instructions: str = "\n\n".join(part for part in parts if part)
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
    def check_beat(self, state: GameState, beat: DirectorBeat) -> str | None:
        """Must not raise: an output validator that raises kills the turn instead of retrying.
        A plan is a beat with framing on it, so the first beat of a turn comes through here too."""

    @abstractmethod
    def resolve_beat(self, draft: GameState, beat: DirectorBeat, rng: Random) -> Resolution: ...

    def _worked_plans(self) -> str:
        path = self.engine_dir / "examples.json"
        if not path.is_file():
            return ""
        plans = TypeAdapter(list[DirectorPlan]).validate_json(engine_text(path))
        blocks: list[str] = []
        for number, plan in enumerate(plans, start=1):
            _ = translate(plan, self.actions)
            blocks.append(f"Example {number}:\n\n```json\n{plan.model_dump_json(indent=2)}\n```")
        return "\n\n".join(["## Worked plans", WORKED_PLANS, *blocks]) if blocks else ""


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
