from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from random import Random

from .base import AdvancementDecision, EngineId, Entity, Kind, Slug
from .content import AuthoredEntity, AuthoredWorld, Rules, compose_world
from .engine import AdvancementPanel, Engine, Transition
from .mechanics import Mechanics
from .packs import (
    EMPTY_FROZEN_MAP,
    ENCODING,
    CollectionName,
    Content,
    ContentRef,
    FrozenMap,
    LenientRecord,
    Value,
    lenient_format,
    load,
)
from .sheet import Sheet, SheetDefinition, SheetTemplate, render_sheet
from .world import GameState, WorldState


class EngineSpec(Value):
    templates: FrozenMap[Kind, SheetTemplate] = EMPTY_FROZEN_MAP
    # Label -> the labels it refills, so a long rest also restores what a short rest would.
    recharge: FrozenMap[str, tuple[str, ...]] = EMPTY_FROZEN_MAP
    collections: tuple[CollectionName, ...] = ()

    def template(self, kind: Kind) -> SheetTemplate:
        return self.templates.get(kind, SheetTemplate())


def load_engine(
    engine_dir: Path,
    engine_id: EngineId,
    pack_paths: Sequence[Path] | None = None,
    *,
    advance: Callable[[AdvancementDecision, GameState[Sheet], Random], Transition[Sheet]],
    advancement_available: Callable[[GameState[Sheet]], bool],
    advancement_panel: AdvancementPanel,
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

    return Engine(
        id=engine_id,
        state_type=GameState[Sheet],
        initial_world=initial_world,
        validate_state=lambda state: _validate(state, spec, content),
        default_rules=default_rules,
        advance=advance,
        advancement_available=advancement_available,
        advancement_panel=advancement_panel,
        toolsets={"director": Mechanics(content=content, refills=spec.recharge).toolset()},
        director_instructions=_text(engine_dir / "director.md"),
        entity_state=render_sheet,
    )


def _backing(refs: Sequence[ContentRef], content: Content) -> Mapping[Slug, int]:
    """A monster is authored as one ref, so its record's numbers land on its sheet."""
    return {k: v for ref in refs for k, v in content.require(ref, LenientRecord).numbers.items()}


def _validate(state: GameState[Sheet], spec: EngineSpec, content: Content) -> None:
    """The other half of the misname guard: a sheet keeps its kind's keys and its refs resolve."""
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
