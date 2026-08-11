import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from random import Random
from typing import Annotated, Self

from pydantic import (
    Field,
    JsonValue,
    TypeAdapter,
    model_validator,
)
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
PLUGIN = "PLUGIN"

type EntityRenderer = Callable[[Entity], str]


class EngineSpec(Frozen):
    # Collection name -> the facts every record in it must carry (empty: no requirement).
    collections: FrozenMap[CollectionName, FactSchema] = EMPTY_FROZEN_MAP
    # Collections whose int facts land on the mechanics of any entity that refs a record in them.
    projecting: tuple[CollectionName, ...] = ()

    @model_validator(mode="after")
    def _projects_known_collections(self) -> Self:
        if unknown := sorted(set(self.projecting) - set(self.collections)):
            raise ValueError(f"projecting names no such collection: {unknown}")
        return self


@dataclass(frozen=True, slots=True)
class EnginePlugin:
    """Every callable takes the loaded `Engine` first, because content and the spec belong to the
    load and the plan lifecycle belongs to the engine module that declares this."""

    id: EngineId
    badge: tuple[str, str]
    engine_dir: Path
    plan_type: type[TurnPlanBase]
    proposal_type: type[ProposalBase]
    # Writes `state.mechanics` for a new game from the authored rules, keyed by entity id.
    begin: "Callable[[Engine, GameState, Mapping[EntityId, Rules]], None]"
    # The one path that validates the mechanics half: it also gives any new entity its own.
    commit: "Callable[[Engine, GameState], None]"
    render: "Callable[[Engine, GameState], EntityRenderer]"
    check: "Callable[[Engine, GameState, TurnPlanBase], str | None]"
    resolve: "Callable[[Engine, GameState, TurnPlanBase, Random], list[Fact]]"
    offered: "Callable[[Engine, GameState], AdvancementOffer | None]"
    advance: "Callable[[Engine, GameState, ProposalBase], tuple[Fact, ...]]"
    check_proposal: "Callable[[Engine, GameState, AdvancementOffer, ProposalBase], str | None]"


@dataclass(frozen=True, slots=True)
class Engine:
    plugin: EnginePlugin
    spec: EngineSpec
    content: Content
    director_instructions: str
    advancement_instructions: str
    director_toolset: AbstractToolset[object]

    @property
    def id(self) -> EngineId:
        return self.plugin.id

    @property
    def badge(self) -> tuple[str, str]:
        return self.plugin.badge

    @property
    def plan_type(self) -> type[TurnPlanBase]:
        return self.plugin.plan_type

    @property
    def proposal_type(self) -> type[ProposalBase]:
        return self.plugin.proposal_type

    def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None:
        self.plugin.begin(self, state, rules)
        self.commit(state)

    def commit(self, state: GameState) -> None:
        """Called at load, at the end of every transaction, and after a new game is composed."""
        self.plugin.commit(self, state)

    def renderer(self, state: GameState) -> EntityRenderer:
        return self.plugin.render(self, state)

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        """Must not raise: an output validator that raises kills the turn instead of retrying."""
        return self.plugin.check(self, state, plan)

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        return self.plugin.resolve(self, draft, plan, rng)

    def offered(self, state: GameState) -> AdvancementOffer | None:
        return self.plugin.offered(self, state)

    def advance(self, draft: GameState, proposal: ProposalBase) -> tuple[Fact, ...]:
        """Mutates the draft; the caller's commit revalidates both halves of the copy."""
        return self.plugin.advance(self, draft, proposal)

    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        """One legality rule for the advisor's retry and for the commit, so neither can drift."""
        return self.plugin.check_proposal(self, state, offer, proposal)

    def record(self, ref: ContentRef) -> Record | None:
        found = self.content.record(ref)
        return None if isinstance(found, ContentMiss) else found


def plugins() -> tuple[EnginePlugin, ...]:
    """Imported by name, because a static import would put core back inside the engine packages."""
    found = tuple(_plugin(module) for module in ENGINE_MODULES)
    if len({plugin.id for plugin in found}) != len(found):
        raise ValueError(f"engine ids collide: {[plugin.id for plugin in found]}")
    return found


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(plugin.id for plugin in plugins())


def plugin_for(engine_id: EngineId) -> EnginePlugin:
    found = next((plugin for plugin in plugins() if plugin.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def load_engine(plugin: EnginePlugin, pack_paths: Sequence[Path] | None = None) -> Engine:
    engine_dir = plugin.engine_dir
    spec = EngineSpec.model_validate_json(_text(engine_dir / "spec.json"))
    directories = _packs(engine_dir) if pack_paths is None else tuple(pack_paths)
    content = load(directories, spec.collections)
    return Engine(
        plugin=plugin,
        spec=spec,
        content=content,
        director_instructions=_text(engine_dir / "director.md")
        + _effect_vocabulary()
        + _examples(engine_dir, plugin.plan_type),
        advancement_instructions=_text(engine_dir / "advancement.md"),
        director_toolset=_director_toolset(content),
    )


def _plugin(module: str) -> EnginePlugin:
    declared = getattr(import_module(module), PLUGIN, None)
    if not isinstance(declared, EnginePlugin):
        raise ValueError(f"engine module {module!r} declares no {PLUGIN}")
    return declared


def _examples(engine_dir: Path, plan_type: type[TurnPlanBase]) -> str:
    entries = TypeAdapter(list[JsonValue]).validate_json(_text(engine_dir / "examples.json"))
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
        _text(Path(__file__).parent / "examples.json")
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


def _text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)
