import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random

from pydantic import JsonValue, TypeAdapter

from .base import EngineId, Entity, Kind, Slug
from .content import AuthoredEntity, AuthoredWorld, Rules, compose_world
from .engine import AdvancementOffer, Engine, ProposalSpec
from .facts import Fact
from .mechanics import Mechanics
from .packs import (
    EMPTY_FROZEN_MAP,
    ENCODING,
    CollectionName,
    Content,
    ContentMiss,
    ContentRef,
    FrozenMap,
    LenientRecord,
    Value,
    lenient_format,
    load,
)
from .plan import TurnPlanBase
from .sheet import Sheet, SheetDefinition, SheetDelta, SheetTemplate, render_sheet
from .world import GameState, WorldState

type Offered = Callable[[GameState[Sheet], Content], AdvancementOffer | None]
type Check = Callable[[GameState[Sheet], AdvancementOffer, SheetDelta], str | None]
type PartsPlanCheck = Callable[[EngineParts, GameState[Sheet], TurnPlanBase], str | None]
type PartsResolver = Callable[[EngineParts, GameState[Sheet], TurnPlanBase, Random], list[Fact]]


class EngineSpec(Value):
    templates: FrozenMap[Kind, SheetTemplate] = EMPTY_FROZEN_MAP
    # Label -> the labels it refills, so a long rest also restores what a short rest would.
    recharge: FrozenMap[str, tuple[str, ...]] = EMPTY_FROZEN_MAP
    collections: tuple[CollectionName, ...] = ()

    def template(self, kind: Kind) -> SheetTemplate:
        return self.templates.get(kind, SheetTemplate())


@dataclass(frozen=True, slots=True)
class EngineParts:
    content: Content
    spec: EngineSpec
    default_rules: Callable[[Entity], Sheet]


def load_engine(
    engine_dir: Path,
    engine_id: EngineId,
    pack_paths: Sequence[Path] | None = None,
    *,
    offered: Offered,
    check: Check,
    plan_type: type[TurnPlanBase],
    check_plan: PartsPlanCheck,
    resolve_action: PartsResolver,
) -> Engine[Sheet]:
    spec = EngineSpec.model_validate_json(_text(engine_dir / "spec.json"))
    directories = _packs(engine_dir) if pack_paths is None else tuple(pack_paths)
    content = load(directories, lenient_format(spec.collections))

    def sheet(kind: Kind, rules: Rules) -> Sheet:
        definition = SheetDefinition.model_validate(rules)
        return definition.runtime(kind, spec.template(kind), _backing(definition.refs, content))

    def entity_rules(authored: AuthoredEntity) -> Sheet:
        return sheet(authored.entity.kind, authored.rules)

    def initial_world(authored: AuthoredWorld, character: Rules) -> WorldState[Sheet]:
        return compose_world(WorldState[Sheet], authored, sheet("actor", character), entity_rules)

    def default_rules(entity: Entity) -> Sheet:
        return SheetDefinition().runtime(entity.kind, spec.template(entity.kind))

    def resolve(ref: ContentRef) -> LenientRecord | None:
        found = content.get(ref, LenientRecord)
        return None if isinstance(found, ContentMiss) else found

    def entity_state(entity: Entity, sheet: Sheet) -> str:
        return render_sheet(entity, sheet, resolve)

    parts = EngineParts(content=content, spec=spec, default_rules=default_rules)
    return Engine(
        id=engine_id,
        state_type=GameState[Sheet],
        initial_world=initial_world,
        validate_state=lambda state: _validate(state, spec, content),
        default_rules=default_rules,
        proposal=ProposalSpec(
            offered=lambda state: offered(state, content),
            instructions=_text(engine_dir / "advancement.md"),
            check=check,
        ),
        toolsets={"director": Mechanics(content=content, refills=spec.recharge).toolset()},
        director_instructions=_text(engine_dir / "director.md") + _examples(engine_dir, plan_type),
        entity_state=entity_state,
        plan_type=plan_type,
        check_plan=lambda state, plan: check_plan(parts, state, plan),
        resolve_action=lambda draft, plan, rng: resolve_action(parts, draft, plan, rng),
    )


def _examples(engine_dir: Path, plan_type: type[TurnPlanBase]) -> str:
    entries = TypeAdapter(list[JsonValue]).validate_json(_text(engine_dir / "examples.json"))
    blocks: list[str] = []
    for number, entry in enumerate(entries, start=1):
        _ = plan_type.model_validate(entry)
        blocks.append(f"Example {number}:\n\n```json\n{json.dumps(entry, indent=2)}\n```")
    if not blocks:
        return ""
    header = "## Worked plans\n\nOne plan per action; a field left out sits at its default."
    return "\n\n" + "\n\n".join([header, *blocks])


def _backing(refs: Sequence[ContentRef], content: Content) -> Mapping[Slug, int]:
    records = [content.require(ref, LenientRecord) for ref in refs]
    return {k: v for record in records for k, v in record.numbers.items()}


def _validate(state: GameState[Sheet], spec: EngineSpec, content: Content) -> None:
    for record in state.world.records.values():
        entity, sheet = record.entity, record.rules
        template = spec.template(entity.kind)
        missing = [
            *sorted(set(template.numbers) - set(sheet.numbers)),
            *sorted(set(template.counters) - set(sheet.counters)),
        ]
        if missing:
            raise ValueError(f"{entity.id!r} is missing the canonical keys {missing}")
        for ref in sheet.refs:
            if (miss := content.resolves(ref)) is not None:
                raise ValueError(f"{entity.id!r}: {miss.summary}")


def _packs(engine_dir: Path) -> tuple[Path, ...]:
    directory = engine_dir / "packs"
    if not directory.is_dir():
        return ()
    return tuple(sorted(path for path in directory.iterdir() if path.is_dir()))


def _text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)
