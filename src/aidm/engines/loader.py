import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from random import Random
from types import MappingProxyType
from typing import Annotated

from pydantic import Field, JsonValue, TypeAdapter, ValidationError
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.content.authored import AuthoredEntity, AuthoredWorld, Rules, compose_world
from aidm.state.base import EngineId, Entity, Kind, Slug
from aidm.state.effects import Effect, effect_ops
from aidm.state.facts import Fact
from aidm.state.packs import (
    EMPTY_FROZEN_MAP,
    ENCODING,
    CollectionName,
    Content,
    ContentMiss,
    ContentRef,
    FrozenMap,
    PackFormat,
    Record,
    Value,
    load,
    pack_format,
    parse_ref,
)
from aidm.state.plan import TurnPlanBase
from aidm.state.sheet import (
    AddRef,
    AdvancementOffer,
    Sheet,
    SheetDefinition,
    SheetDelta,
    SheetTemplate,
    apply_delta,
    render_sheet,
)
from aidm.state.world import GameState, WorldState, player_sheet

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.story.rules",
    "aidm.engines.dnd5e.rules",
)
PLUGIN = "PLUGIN"

type EntityRenderer = Callable[[Entity], str]
type PlanCheck = Callable[[Engine, GameState, TurnPlanBase], str | None]
"""Judges the untouched committed state and returns the refusal. It must not raise: an output
validator turns an exception into a dead turn instead of a retry."""
type ActionResolver = Callable[[Engine, GameState, TurnPlanBase, Random], list[Fact]]
"""Mutates the draft: the action's rolls, its intrinsic consequences, and the branch taken."""
type Offered = Callable[[Engine, GameState], AdvancementOffer | None]
type DeltaCheck = Callable[[GameState, SheetDelta], str | None]


class EngineSpec(Value):
    templates: FrozenMap[Kind, SheetTemplate] = EMPTY_FROZEN_MAP
    # Label -> the labels it refills, so a long rest also restores what a short rest would.
    recharge: FrozenMap[str, tuple[str, ...]] = EMPTY_FROZEN_MAP
    collections: tuple[CollectionName, ...] = ()

    def template(self, kind: Kind) -> SheetTemplate:
        return self.templates.get(kind, SheetTemplate())


@dataclass(frozen=True, slots=True)
class EnginePlugin:
    """What an engine declares: its identity, its directory of data, and the four hooks that hold
    everything the loader cannot derive from that data."""

    id: EngineId
    badge: tuple[str, str]
    engine_dir: Path
    plan_type: type[TurnPlanBase]
    check_plan: PlanCheck
    resolve_action: ActionResolver
    offered: Offered
    check_delta: DeltaCheck
    record_types: Mapping[CollectionName, type[Record]] = MappingProxyType({})

    def pack_format(self, spec: EngineSpec) -> PackFormat:
        return pack_format(spec.collections, self.record_types)


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

    def default_rules(self, entity: Entity) -> Sheet:
        return SheetDefinition().runtime(entity.kind, self.spec.template(entity.kind))

    def initial_world(self, authored: AuthoredWorld, character: Rules) -> WorldState:
        return compose_world(authored, self._sheet("actor", character), self._entity_rules)

    def entity_state(self, entity: Entity, sheet: Sheet) -> str:
        return render_sheet(entity, sheet, self._record)

    def renderer(self, state: GameState) -> EntityRenderer:
        return lambda entity: self.entity_state(entity, state.world.record(entity.id).rules)

    def validate_state(self, state: GameState) -> None:
        for record in state.world.records.values():
            entity, sheet = record.entity, record.rules
            template = self.spec.template(entity.kind)
            missing = [
                *sorted(set(template.numbers) - set(sheet.numbers)),
                *sorted(set(template.counters) - set(sheet.counters)),
            ]
            if missing:
                raise ValueError(f"{entity.id!r} is missing the canonical keys {missing}")
            for ref in sheet.refs:
                if (miss := self.content.resolves(ref)) is not None:
                    raise ValueError(f"{entity.id!r}: {miss.summary}")

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        return self.plugin.check_plan(self, state, plan)

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        return self.plugin.resolve_action(self, draft, plan, rng)

    def offered(self, state: GameState) -> AdvancementOffer | None:
        return self.plugin.offered(self, state)

    def violation(self, state: GameState, offer: AdvancementOffer, delta: SheetDelta) -> str | None:
        """One legality rule for the advisor's retry and for the commit, so neither can drift."""
        picked = [change.ref for change in delta.changes if isinstance(change, AddRef)]
        if outside := sorted(str(ref) for ref in picked if ref not in offer.options):
            allowed = ", ".join(str(ref) for ref in offer.options) or "(none)"
            return f"{', '.join(outside)} is not on offer here. The legal picks are: {allowed}"
        if len(picked) != offer.choose:
            return (
                f"this offer takes exactly {offer.choose} picks, the proposal makes {len(picked)}"
            )
        trial = player_sheet(state).model_copy(deep=True)
        try:
            _ = apply_delta(trial, delta)
            _ = Sheet.model_validate(trial.model_dump())
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return self.plugin.check_delta(state, delta)

    def _sheet(self, kind: Kind, rules: Rules) -> Sheet:
        definition = SheetDefinition.model_validate(rules)
        return definition.runtime(
            kind, self.spec.template(kind), _backing(definition.refs, self.content)
        )

    def _entity_rules(self, authored: AuthoredEntity) -> Sheet:
        return self._sheet(authored.entity.kind, authored.rules)

    def _record(self, ref: ContentRef) -> Record | None:
        found = self.content.get(ref, Record)
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
    content = load(directories, plugin.pack_format(spec))
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
    entries = TypeAdapter(list[JsonValue]).validate_json(
        _text(Path(__file__).parent / "examples.json")
    )
    checked = TypeAdapter(list[Effect]).validate_python(entries)
    if (
        len(checked) != len(effect_ops())
        or frozenset(entry.op for entry in checked) != effect_ops()
    ):
        raise ValueError("the shared examples.json must show every effect op exactly once")
    lines = "\n".join(json.dumps(entry) for entry in entries)
    header = (
        "## Effects\n\nEvery effect, one example each. Ids, keys, and tags here are "
        "illustrative: use the exact ids the scene shows and the counter keys on that "
        "entity's own sheet. Most turns need few or no effects: an empty `effects` with "
        "no branches is a normal plan. But a turn whose fiction starts or ends a lasting "
        "state — a condition taking hold or passing — must write that tag change, with "
        "or without an action: nothing records it otherwise."
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
        found = content.get(reference, Record)
        if isinstance(found, ContentMiss):
            raise ModelRetry(found.summary)
        return _record_text(found, ref)

    return FunctionToolset[object]([read_content])


def _record_text(record: Record, ref: str) -> str:
    numbers = ", ".join(f"{key} {value}" for key, value in sorted(record.sheet_numbers().items()))
    notes = "; ".join(f"{key}={value}" for key, value in sorted(record.noted().items()))
    options = ", ".join(str(option) for option in record.options)
    lines = [
        f"{record.name} [{ref}]",
        *([f"numbers: {numbers}"] if numbers else []),
        *([f"notes: {notes}"] if notes else []),
        *([f"tags: {', '.join(record.tags)}"] if record.tags else []),
        *([f"choose {record.choose} of: {options}"] if options else []),
        *([record.text] if record.text else []),
    ]
    return "\n".join(lines)


def _backing(refs: Sequence[ContentRef], content: Content) -> Mapping[Slug, int]:
    records = [content.require(ref, Record) for ref in refs]
    return {k: v for record in records for k, v in record.sheet_numbers().items()}


def _packs(engine_dir: Path) -> tuple[Path, ...]:
    directory = engine_dir / "packs"
    if not directory.is_dir():
        return ()
    return tuple(sorted(path for path in directory.iterdir() if path.is_dir()))


def _text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)
