import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from random import Random
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import Field, JsonValue, TypeAdapter, ValidationError, create_model
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.content.authored import AuthoredEntity, AuthoredWorld, Rules, compose_world
from aidm.engines.vm import ActionDef, Resolved, run_program
from aidm.state.apply import apply_effect
from aidm.state.base import EngineId, Entity, Frozen, Kind, Slug
from aidm.state.effects import AddRef, SheetDelta, TurnEffect, turn_effect_ops
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
    Value,
    load,
    parse_ref,
)
from aidm.state.plan import TurnPlanBase, apply_branch, check_plan_base
from aidm.state.sheet import (
    AdvancementOffer,
    Sheet,
    SheetDefinition,
    SheetTemplate,
    render_sheet,
)
from aidm.state.world import GameState, WorldState, player_sheet

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.story.rules",
    "aidm.engines.dnd5e.rules",
)
PLUGIN = "PLUGIN"

type EntityRenderer = Callable[[Entity], str]


class EngineSpec(Value):
    templates: FrozenMap[Kind, SheetTemplate] = EMPTY_FROZEN_MAP
    # Collection name -> the facts every record in it must carry (empty: no requirement).
    collections: FrozenMap[CollectionName, FactSchema] = EMPTY_FROZEN_MAP

    def template(self, kind: Kind) -> SheetTemplate:
        return self.templates.get(kind, SheetTemplate())


@dataclass(frozen=True, slots=True)
class ActionSpec[A: Frozen]:
    """`resolve` mutates the draft and names the outcome; the kernel applies that outcome's
    branch. `check` judges the whole plan against the untouched committed state."""

    model: type[A]
    labels: "frozenset[Slug] | Callable[[Engine, A], frozenset[Slug]]"
    resolve: "Callable[[Engine, GameState, A, Random], Resolved]"
    check: Callable[[GameState, TurnPlanBase, A], str | None] | None = None


@dataclass(frozen=True, slots=True)
class EnginePlugin:
    id: EngineId
    badge: tuple[str, str]
    engine_dir: Path
    action_doc: str
    offered: "Callable[[Engine, GameState], AdvancementOffer | None]"
    # Judges the sheet the proposal would leave, which the kernel has already applied and validated.
    check_delta: Callable[[GameState, Sheet], str | None]
    # Named exceptions for declared actions the VM cannot judge alone, keyed by action name:
    # labels that depend on the action's values or content, and whole-plan checks.
    dynamic_labels: "Mapping[Slug, Callable[[Engine, Any], frozenset[Slug]]]" = MappingProxyType({})
    plan_checks: Mapping[Slug, Callable[[GameState, TurnPlanBase, Any], str | None]] = (
        MappingProxyType({})
    )


@dataclass(frozen=True, slots=True)
class Engine:
    plugin: EnginePlugin
    actions: tuple[ActionSpec[Any], ...]
    spec: EngineSpec
    content: Content
    plan_type: type[TurnPlanBase]
    director_instructions: str
    advancement_instructions: str
    director_toolset: AbstractToolset[object]

    @property
    def id(self) -> EngineId:
        return self.plugin.id

    @property
    def badge(self) -> tuple[str, str]:
        return self.plugin.badge

    def default_rules(self, entity: Entity) -> Sheet:
        return SheetDefinition().runtime(entity.kind, self.spec.template(entity.kind))

    def initial_world(self, authored: AuthoredWorld, character: Rules) -> WorldState:
        return compose_world(authored, self._sheet("actor", character), self._entity_rules)

    def entity_state(self, entity: Entity, sheet: Sheet) -> str:
        return render_sheet(sheet, self._record)

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
        """Must not raise: an output validator that raises kills the turn instead of retrying.
        The trial resolve owes the model every refusal the real resolve raises."""
        action = _action(plan)
        if action is None:
            return check_plan_base(state, plan, frozenset[Slug](), self.default_rules)
        try:
            spec = self._spec(action)
            _ = spec.resolve(self, state.draft(), action, Random(0))
            held = spec.labels
            labels: frozenset[Slug] = held(self, action) if callable(held) else held
        except ValueError as refused:
            return str(refused)
        if spec.check is not None and (refusal := spec.check(state, plan, action)):
            return refusal
        return check_plan_base(state, plan, labels, self.default_rules)

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        action = _action(plan)
        if action is None:
            return []
        facts, outcome = self._spec(action).resolve(self, draft, action, rng)
        if outcome is not None:
            facts.extend(apply_branch(draft, plan, outcome, self.default_rules))
        return facts

    def offered(self, state: GameState) -> AdvancementOffer | None:
        return self.plugin.offered(self, state)

    def advance(self, draft: GameState, delta: SheetDelta) -> tuple[Fact, ...]:
        """Mutates the draft's player sheet; the caller's commit revalidates the whole copy."""
        return tuple(
            fact
            for change in delta.changes
            for fact in apply_effect(draft, change, self.default_rules, advancing=True)
        )

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
        if unexplained := sorted({change.op for change in delta.changes if not change.why}):
            return f"every change needs a `why` the player can read, and {unexplained} has none"
        draft = state.draft()
        try:
            _ = self.advance(draft, delta)
            after = draft.committed()
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return self.plugin.check_delta(state, player_sheet(after))

    def _spec(self, action: Frozen) -> ActionSpec[Any]:
        for spec in self.actions:
            if type(action) is spec.model:
                return spec
        raise ValueError(f"{self.id} registers no action {type(action).__name__}")

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
    content = load(directories, spec.collections)
    actions = _declared_actions(plugin)
    plan_type = _plan_model(actions, plugin.action_doc)
    return Engine(
        plugin=plugin,
        actions=actions,
        spec=spec,
        content=content,
        plan_type=plan_type,
        director_instructions=_text(engine_dir / "director.md")
        + _effect_vocabulary()
        + _examples(engine_dir, plan_type),
        advancement_instructions=_text(engine_dir / "advancement.md"),
        director_toolset=_director_toolset(content),
    )


def _plan_model(actions: tuple[ActionSpec[Any], ...], action_doc: str) -> type[TurnPlanBase]:
    """A discriminator on a lone model raises, so a single-action engine gets its model plain."""
    models: tuple[type[Frozen], ...] = tuple(spec.model for spec in actions)
    if not models:
        return TurnPlanBase
    union: Any = models[0]  # An annotation assembled at runtime carries no static type.
    for other in models[1:]:
        union = union | other
    if len(models) > 1:
        union = Annotated[union, Field(discriminator="act")]
    return create_model(
        "TurnPlan",
        __base__=TurnPlanBase,
        action=(union | None, Field(default=None, description=action_doc)),
    )


def _declared_actions(plugin: EnginePlugin) -> tuple[ActionSpec[Any], ...]:
    """An engine's `actions.json` needs no Python: the kernel runs its programs."""
    path = plugin.engine_dir / "actions.json"
    if not path.is_file():
        return ()
    declared = TypeAdapter(tuple[ActionDef, ...]).validate_json(_text(path))
    return tuple(_declared_spec(action, plugin) for action in declared)


def _declared_spec(declared: ActionDef, plugin: EnginePlugin) -> ActionSpec[Any]:
    def resolve(engine: Engine, draft: GameState, action: Any, rng: Random) -> Resolved:
        return run_program(
            declared.program,
            draft,
            action,
            rng,
            engine.default_rules,
            declared.params,
            engine.content,
        )

    return ActionSpec(
        model=declared.model(),
        labels=plugin.dynamic_labels.get(declared.name, frozenset(declared.labels)),
        resolve=resolve,
        check=plugin.plan_checks.get(declared.name),
    )


def _action(plan: TurnPlanBase) -> Frozen | None:
    """The plan model is built per engine, so the base type the kernel holds knows no `action`."""
    action: object = getattr(plan, "action", None)
    assert action is None or isinstance(action, Frozen)
    return action


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
    checked = TypeAdapter(list[TurnEffect]).validate_python(entries)
    ops = turn_effect_ops()
    if len(checked) != len(ops) or frozenset(entry.op for entry in checked) != ops:
        raise ValueError("the shared examples.json must show every turn effect op exactly once")
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
