import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from pathlib import Path
from random import Random
from typing import Annotated, ClassVar

from pydantic import Field, JsonValue, TypeAdapter
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.content.authored import Rules
from aidm.state.advancement import AdvancementOffer, ProposalBase
from aidm.state.base import EngineId, Entity, EntityId, Frozen
from aidm.state.effects import WorldEffect, effect_key, effect_keys
from aidm.state.facts import Fact
from aidm.state.packs import (
    EMPTY_FROZEN_MAP,
    ENCODING,
    CollectionName,
    Content,
    ContentMiss,
    ContentRef,
    FactSchema,
    FrozenMap,
    Record,
    fact_line,
    load,
    parse_ref,
)
from aidm.state.plan import TurnPlanBase
from aidm.state.world import GameState

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.story.rules",
    "aidm.engines.dnd5e.rules",
)
ENGINE = "ENGINE"

type EntityRenderer = Callable[[Entity], str]


class EngineSpec(Frozen):
    # Collection name -> the facts every record in it must carry (empty: no requirement).
    collections: FrozenMap[CollectionName, FactSchema] = EMPTY_FROZEN_MAP


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


class Engine(ABC):
    """One object per engine: its metadata, its content, its plan lifecycle, and the mechanics
    half of the state core keeps but cannot read."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    plan_type: ClassVar[type[TurnPlanBase]]
    engine_dir: ClassVar[Path]

    def __init__(self, pack_paths: Sequence[Path] | None = None) -> None:
        directories = _packs(self.engine_dir) if pack_paths is None else tuple(pack_paths)
        self.collections = engine_spec(self.engine_dir).collections
        self.content: Content = load(directories, self.collections)
        self.director_instructions: str = (
            engine_text(self.engine_dir / "director.md")
            + _effect_vocabulary()
            + _examples(self.engine_dir, self.plan_type)
        )
        self.director_toolset: AbstractToolset[object] = _director_toolset(self.content)
        # An engine that grows its characters replaces this; the app offers only what it finds.
        self.advancement: Advancement | None = None

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

    def record(self, ref: ContentRef) -> Record | None:
        found = self.content.record(ref)
        return None if isinstance(found, ContentMiss) else found


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


def engine_spec(engine_dir: Path) -> EngineSpec:
    """Every engine carries one, so the pack format of an engine without content reads as empty
    rather than as absent."""
    return EngineSpec.model_validate_json(engine_text(engine_dir / "spec.json"))


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


def _director_toolset(content: Content) -> FunctionToolset[object]:
    def read_content(
        ref: Annotated[
            str, Field(description="A content ref written `pack/collection/index`, as shown.")
        ],
    ) -> str:
        """Read the rules text of one content record.

        Use before planning from a spell, feature, or monster action whose wording you cannot
        quote. It reads canon and changes nothing.
        """
        try:
            reference = parse_ref(ref)
        except ValueError as malformed:
            raise ModelRetry(str(malformed)) from malformed
        found = content.record(reference)
        if isinstance(found, ContentMiss):
            raise ModelRetry(found.summary)
        return _record_text(found, ref)

    return FunctionToolset[object]([read_content])


def _record_text(record: Record, ref: str) -> str:
    rendered = (fact_line(k, v, ladder_full=True) for k, v in sorted(record.facts.items()))
    # Values carry commas of their own ("1d4+2 piercing"), so only a semicolon separates facts.
    facts = "; ".join(line for line in rendered if line is not None)
    options = ", ".join(str(option) for option in record.options)
    lines = [
        f"{record.name} [{ref}]",
        *([f"facts: {facts}"] if facts else []),
        *([f"tags: {', '.join(record.tags)}"] if record.tags else []),
        *([f"choose {record.choose} of: {options}"] if options else []),
        *([record.text] if record.text else []),
    ]
    return "\n".join(lines)


def _packs(engine_dir: Path) -> tuple[Path, ...]:
    directory = engine_dir / "packs"
    if not directory.is_dir():
        return ()
    return tuple(sorted(path for path in directory.iterdir() if path.is_dir()))
