from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from random import Random
from string import Formatter
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, Field, JsonValue, TypeAdapter, create_model, model_validator
from pydantic_core import PydanticUndefined

from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Slug
from aidm.state.dice import DiceExpr, RollMode, roll
from aidm.state.effects import ProgramEffect
from aidm.state.facts import Fact
from aidm.state.packs import CollectionName, Content, ContentMiss, Record, Value, parse_ref
from aidm.state.sheet import Sheet
from aidm.state.world import GameState, sheet_of

REF = "$"
EFFECT = TypeAdapter[ProgramEffect](ProgramEffect)
DICE = TypeAdapter[str](DiceExpr)

type Resolved = tuple[list[Fact], Slug | None]
type DefaultRules = Callable[[Entity], Sheet]


def _judged_name(token: str) -> str:
    """A literal is always present, so a `present` over one can only be an authoring typo."""
    if not token.startswith(REF):
        raise ValueError(f"present judges a param or binding: write {REF}{token}")
    return token


type JudgedName = Annotated[str, AfterValidator(_judged_name)]


class ParamBase(Value):
    description: str
    optional: bool = False


class EntityParam(ParamBase):
    type: Literal["entity-id"]
    kind: Literal["actor", "item"] = "actor"


class SlugParam(ParamBase):
    type: Literal["slug"]


class IntParam(ParamBase):
    type: Literal["int"]
    ge: int | None = None
    le: int | None = None


class StrParam(ParamBase):
    type: Literal["str"]
    min_length: int | None = None
    max_length: int | None = None


class EnumParam(ParamBase):
    type: Literal["enum"]
    values: tuple[str, ...] = Field(min_length=1)
    default: str | None = None

    @model_validator(mode="after")
    def _default_is_a_value(self) -> Self:
        if self.default is not None and self.default not in self.values:
            raise ValueError(f"default {self.default!r} is not one of the values")
        return self


class BoolParam(ParamBase):
    type: Literal["bool"]
    default: bool = False


class DiceParam(ParamBase):
    type: Literal["dice-expr"]


type Param = Annotated[
    EntityParam | SlugParam | IntParam | StrParam | EnumParam | BoolParam | DiceParam,
    Field(discriminator="type"),
]


def _annotation(param: Param) -> tuple[Any, dict[str, Any]]:
    """The field's type and the constraints that belong on its `Field`, kept together so the
    generated schema matches a hand-written model exactly."""
    match param:
        case EntityParam():
            return EntityId, {}
        case SlugParam():
            return Slug, {}
        case IntParam(ge=ge, le=le):
            return int, {"ge": ge, "le": le}
        case StrParam(min_length=low, max_length=high):
            return str, {"min_length": low, "max_length": high}
        case EnumParam(values=values):
            return Literal[tuple(values)], {}
        case BoolParam():
            return bool, {}
        case DiceParam():
            return DiceExpr, {}


def _default(param: Param) -> Any:
    match param:
        case BoolParam(default=default):
            return default
        case EnumParam(default=default) if default is not None:
            return default
        case _:
            return PydanticUndefined


class ConstExpr(Value):
    expr: Literal["const"]
    value: int


class ValueExpr(Value):
    """A bound name read back as a number; `times` scales it, so -1 negates."""

    expr: Literal["value"]
    of: str
    times: int = 1


class NumberExpr(Value):
    expr: Literal["number"]
    actor: str
    key: str
    default: int | None = None


class TableExpr(Value):
    expr: Literal["table"]
    on: str
    values: Mapping[str, int]
    default: int = 0


class PresentExpr(Value):
    """An optional param that was written counts as `weight`, one left out as nothing."""

    expr: Literal["present"]
    of: JudgedName
    weight: int = 1


type Term = Annotated[
    ConstExpr | ValueExpr | NumberExpr | TableExpr | PresentExpr, Field(discriminator="expr")
]


class SumExpr(Value):
    expr: Literal["sum"]
    terms: tuple[Term, ...] = Field(min_length=1)


class DivExpr(Value):
    """The summed terms, floor-divided: the 5e ability modifier and half-on-save both live here."""

    expr: Literal["div"]
    terms: tuple[Term, ...] = Field(min_length=1)
    by: int | str


class MaxExpr(Value):
    expr: Literal["max"]
    terms: tuple[Term, ...] = Field(min_length=1)


type Expr = Annotated[
    ConstExpr | ValueExpr | NumberExpr | TableExpr | PresentExpr | SumExpr | DivExpr | MaxExpr,
    Field(discriminator="expr"),
]


class HasTag(Value):
    pred: Literal["has-tag"]
    actor: str
    tag: str
    carried: bool = False


class CounterFull(Value):
    pred: Literal["counter-full"]
    actor: str
    counter: str


class IsPlayer(Value):
    pred: Literal["is-player"]
    actor: str


class Equals(Value):
    pred: Literal["equals"]
    of: str
    value: bool | str


class Present(Value):
    """Whether an optional param or binding holds a value — the one predicate an omitted
    optional does not make undecidable."""

    pred: Literal["present"]
    of: JudgedName


class Carries(Value):
    pred: Literal["carries"]
    actor: str
    item: str


class AtLeast(Value):
    pred: Literal["at-least"]
    of: str
    least: int | str


type SimplePredicate = Annotated[
    HasTag | CounterFull | IsPlayer | Equals | Present | Carries | AtLeast,
    Field(discriminator="pred"),
]


class Not(Value):
    pred: Literal["not"]
    that: SimplePredicate


class AllOf(Value):
    """One nesting level: members are simple or negated, never `and` again."""

    pred: Literal["and"]
    all: tuple[Annotated[SimplePredicate | Not, Field(discriminator="pred")], ...] = Field(
        min_length=2
    )


type Predicate = Annotated[
    HasTag | CounterFull | IsPlayer | Equals | Present | Carries | AtLeast | Not | AllOf,
    Field(discriminator="pred"),
]


class InstructionBase(Value):
    """Every instruction may be guarded; one that fails its guards is skipped and binds
    nothing. `choose` alone treats the guards as its condition instead."""

    when: Predicate | None = None
    when_outcome: Slug | None = None


class Let(InstructionBase):
    op: Literal["let"]
    name: Slug
    value: Expr


class Require(InstructionBase):
    """`message` is formatted with the params, the bound names, and `<param>_name` for each
    entity param, so a refusal can name the actor the model chose."""

    op: Literal["require"]
    that: Predicate
    expect: bool = True
    message: str


class Roll(InstructionBase):
    op: Literal["roll"]
    dice: str
    reason: str
    bonus: str | None = None
    vs: int | str | None = None
    mode: str | None = None
    into: Slug


class Outcome(InstructionBase):
    """A threshold ref holding null skips the pick: an uncontested roll settles nothing."""

    op: Literal["outcome"]
    of: str
    at: Mapping[Slug, int | str]
    default: Slug


class Choose(InstructionBase):
    """Bind `then` when the guards pass, `otherwise` when they fail. Always binds."""

    op: Literal["choose"]
    into: Slug
    then: JsonValue
    otherwise: JsonValue = None

    @model_validator(mode="after")
    def _conditional(self) -> Self:
        if self.when is None and self.when_outcome is None:
            raise ValueError("choose needs a `when` or `when_outcome` to decide by")
        return self


class Format(InstructionBase):
    op: Literal["format"]
    into: Slug
    template: str


class Lookup(InstructionBase):
    """Bind a content record: the first of a collection on an entity's sheet refs, or the one a
    ref-string param names. Binds `<into>_name` beside it, like an entity param."""

    op: Literal["lookup"]
    into: Slug
    collection: CollectionName
    from_entity: str | None = None
    ref: str | None = None
    require_fact: Slug | None = None
    missing: str

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.from_entity is None) == (self.ref is None):
            raise ValueError("lookup takes exactly one of `from_entity` and `ref`")
        return self


class Read(InstructionBase):
    op: Literal["read"]
    record: str
    fact: Slug
    into: Slug
    default: JsonValue = None


class Ladder(InstructionBase):
    """The last `[threshold, value]` row at or below `at` in a fact ladder; an absent fact or
    an empty reach binds null."""

    op: Literal["ladder"]
    record: str
    fact: Slug
    at: str
    into: Slug


class Apply(InstructionBase):
    op: Literal["apply"]
    effect: dict[str, JsonValue]


type Instruction = Annotated[
    Let | Require | Roll | Outcome | Choose | Format | Lookup | Read | Ladder | Apply,
    Field(discriminator="op"),
]

_MODES: frozenset[str] = frozenset(("normal", "advantage", "disadvantage"))


class ActionDef(Value):
    """One action a content pack declares: the model the Director fills in, and the program the
    kernel runs instead of engine Python."""

    name: Slug
    doc: str
    params: Mapping[str, Param]
    labels: tuple[Slug, ...] = ()
    program: tuple[Instruction, ...]

    @model_validator(mode="after")
    def _resolvable(self) -> Self:
        bound = set(self.params)
        records: set[str] = set()
        named = {f"{name}_name" for name, p in self.params.items() if isinstance(p, EntityParam)}
        # A guarded binding may be skipped at runtime, so a template may name it only from under
        # the same guard: anywhere else it would surface mid-turn as a KeyError, not a refusal.
        guarded: dict[str, tuple[Predicate | None, Slug | None]] = {}
        for step in self.program:
            known = bound | records
            guard = (step.when, step.when_outcome)
            if unknown := sorted(name for name in _refs(step) if name not in known):
                raise ValueError(f"{self.name}: {step.op} reads undefined {unknown}")
            self._check_labels(step)
            for template in _templates(step):
                placeholders = _placeholders(template)
                if unwritable := sorted(placeholders - bound - named):
                    raise ValueError(f"{self.name}: a message names undefined {unwritable}")
                if skipped := sorted(n for n in placeholders if guarded.get(n, guard) != guard):
                    raise ValueError(
                        f"{self.name}: a message names {skipped}, whose binding a guard may skip"
                    )
            self._check_step(step, records)
            if isinstance(step, Lookup):
                self._bind(step.into, bound, records, into=records)
                bound.add(f"{step.into}_name")
                if guard != (None, None):
                    guarded[f"{step.into}_name"] = guard
            elif (binding := _binds(step)) is not None:
                self._bind(binding, bound, records, into=bound)
                if guard != (None, None) and not isinstance(step, Choose):
                    guarded[binding] = guard
        if self.labels and not any(isinstance(step, Outcome) for step in self.program):
            raise ValueError(f"{self.name}: declares outcomes but never picks one")
        return self

    def _bind(self, name: str, bound: set[str], records: set[str], *, into: set[str]) -> None:
        if name in bound or name in records:
            raise ValueError(f"{self.name}: {name!r} is bound twice")
        into.add(name)

    def _check_step(self, step: Instruction, records: set[str]) -> None:
        match step:
            case Apply(effect=effect):
                _check_effect(self.name, effect)
            case Roll(dice=dice, mode=mode):
                if not dice.startswith(REF):
                    _ = DICE.validate_python(dice)
                if mode is not None and not mode.startswith(REF) and mode not in _MODES:
                    raise ValueError(f"{self.name}: {mode!r} is no roll mode")
            case Read(record=record) | Ladder(record=record):
                # A record token silently defaults when its lookup was skipped, so a typo here
                # must fail at load, not read a default forever.
                if (record[1:] if record.startswith(REF) else record) not in records:
                    raise ValueError(f"{self.name}: {record!r} names no lookup of this program")
            case _:
                pass

    def _check_labels(self, step: Instruction) -> None:
        named: tuple[Slug, ...] = ()
        if isinstance(step, Outcome):
            named = (*step.at, step.default)
        if step.when_outcome is not None:
            named = (*named, step.when_outcome)
        if outside := sorted(set(named) - set(self.labels)):
            raise ValueError(f"{self.name}: {outside} is no outcome of this action")

    def model(self) -> type[Frozen]:
        fields: dict[str, Any] = {"act": (Literal[self.name], Field(default=self.name))}
        for name, param in self.params.items():
            annotation, constraints = _annotation(param)
            if param.optional:
                inner: Any = (
                    Annotated[annotation, Field(**constraints)] if constraints else annotation
                )
                fields[name] = (
                    inner | None,
                    Field(default=None, description=param.description),
                )
            else:
                fields[name] = (
                    annotation,
                    Field(default=_default(param), description=param.description, **constraints),
                )
        return create_model(_title(self.name), __base__=Frozen, __doc__=self.doc, **fields)


def _binds(step: Instruction) -> str | None:
    match step:
        case Let(name=name):
            return name
        case Roll(into=into) | Choose(into=into) | Format(into=into):
            return into
        case Read(into=into) | Ladder(into=into):
            return into
        case _:
            return None


def _templates(step: Instruction) -> Iterator[str]:
    match step:
        case Require(message=message):
            yield message
        case Roll(reason=reason):
            yield reason
        case Format(template=template):
            yield template
        case Lookup(missing=missing):
            yield missing
        case _:
            return


def _placeholders(message: str) -> set[str]:
    return {field for _, field, _, _ in Formatter().parse(message) if field}


def _check_effect(action: Slug, effect: dict[str, JsonValue]) -> None:
    """Substitution reaches an effect's own fields and no deeper, so a ref that hides in a nested
    value would silently survive into the applied effect."""
    written = {_reference(value) for value in effect.values()} - {None}
    if nested := sorted(set(_refs(effect)) - written):
        raise ValueError(f"{action}: an effect reads {nested} below its own fields")
    if not written:
        _ = EFFECT.validate_python(effect)


def _reference(value: JsonValue) -> str | None:
    return value[1:] if isinstance(value, str) and value.startswith(REF) else None


def _title(name: Slug) -> str:
    return "".join(word.capitalize() for word in name.split("-"))


def _refs(value: JsonValue | Value) -> Iterator[str]:
    match value:
        case Value():
            yield from _refs(value.model_dump(mode="json"))
        case str() if value.startswith(REF):
            yield value[1:]
        case dict():
            for held in value.values():
                yield from _refs(held)
        case list():
            for held in value:
                yield from _refs(held)
        case _:
            return


@dataclass(slots=True)
class _Run:
    draft: GameState
    rng: Random
    default_rules: DefaultRules
    content: Content
    values: dict[str, JsonValue]
    entities: dict[str, Entity]
    records: dict[str, Record] = field(default_factory=dict[str, Record])
    facts: list[Fact] = field(default_factory=list[Fact])
    outcome: Slug | None = None

    def read(self, token: str) -> JsonValue:
        if not token.startswith(REF):
            return token
        name = token[1:]
        if name not in self.values:
            raise ValueError(f"{token} is unbound here")
        return self.values[name]

    def text(self, token: str) -> str:
        value = self.read(token)
        if not isinstance(value, str):
            raise ValueError(f"{token} holds {value!r}, which is no name")
        return value

    def number(self, token: str) -> int:
        value = self.read(token)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{token} holds {value!r}, which is no number")
        return value

    def entity(self, token: str) -> Entity:
        name = token[1:] if token.startswith(REF) else token
        if name not in self.entities:
            raise ValueError(f"{token} names no actor or item of this action")
        return self.entities[name]

    def sheet(self, token: str) -> Sheet:
        return sheet_of(self.draft, self.entity(token).id)

    def record(self, token: str) -> Record | None:
        """None when the binding lookup was skipped by its guard: reads then fall back to their
        defaults, so one guard on the lookup covers its whole read chain."""
        name = token[1:] if token.startswith(REF) else token
        return self.records.get(name)

    def namespace(self) -> dict[str, JsonValue]:
        return {**self.values, **{f"{name}_name": e.name for name, e in self.entities.items()}}


def run_program(
    program: tuple[Instruction, ...],
    draft: GameState,
    action: Frozen,
    rng: Random,
    default_rules: DefaultRules,
    params: Mapping[str, Param],
    content: Content,
) -> Resolved:
    """Straight-line: every refusal is a `ValueError` the kernel's trial resolve turns into a
    retry, so a declarative action needs no separate check."""
    values: dict[str, JsonValue] = action.model_dump()
    entities: dict[str, Entity] = {}
    for name, param in params.items():
        if isinstance(param, EntityParam) and values.get(name) is not None:
            entity_id = EntityId(str(values[name]))
            if param.kind == "actor":
                entities[name] = require_actor_here(draft, entity_id)
            else:
                entities[name] = draft.world.record(entity_id, "item").entity
    run = _Run(
        draft=draft,
        rng=rng,
        default_rules=default_rules,
        content=content,
        values=values,
        entities=entities,
    )
    for step in program:
        _step(run, step)
    return run.facts, run.outcome


def _step(run: _Run, step: Instruction) -> None:
    if isinstance(step, Choose):
        picked = step.then if _passes(run, step) else step.otherwise
        run.values[step.into] = run.read(picked) if isinstance(picked, str) else picked
        return
    if not _passes(run, step):
        return
    match step:
        case Let(name=name, value=value):
            run.values[name] = _evaluate(run, value)
        case Require():
            _require(run, step)
        case Roll():
            _roll(run, step)
        case Outcome():
            _outcome(run, step)
        case Format(into=into, template=template):
            run.values[into] = template.format_map(run.namespace())
        case Lookup():
            _lookup(run, step)
        case Read():
            _read(run, step)
        case Ladder():
            _ladder(run, step)
        case Apply():
            _apply(run, step)


def _passes(run: _Run, step: Instruction) -> bool:
    if step.when_outcome is not None and step.when_outcome != run.outcome:
        return False
    if step.when is not None:
        return _decidable(run, step.when) and _holds(run, step.when)
    return True


def _evaluate(run: _Run, expr: Expr) -> int:
    match expr:
        case ConstExpr(value=value):
            return value
        case ValueExpr(of=of, times=times):
            return run.number(of) * times
        case SumExpr(terms=terms):
            return sum(_evaluate(run, term) for term in terms)
        case DivExpr(terms=terms, by=by):
            divisor = run.number(by) if isinstance(by, str) else by
            if divisor == 0:
                raise ValueError("division by zero in a program expression")
            return sum(_evaluate(run, term) for term in terms) // divisor
        case MaxExpr(terms=terms):
            return max(_evaluate(run, term) for term in terms)
        case NumberExpr(actor=actor, key=key, default=default):
            sheet, name = run.sheet(actor), run.text(key)
            if name not in sheet.numbers:
                if default is not None:
                    return default
                raise ValueError(f"{run.entity(actor).name} has no {name!r} on their sheet")
            return sheet.numbers[name]
        case TableExpr(on=on, values=values, default=default):
            return values.get(str(run.read(on)), default)
        case PresentExpr(of=of, weight=weight):
            return weight if run.read(of) is not None else 0


def _require(run: _Run, step: Require) -> None:
    if not _decidable(run, step.that) or _holds(run, step.that) is step.expect:
        return
    raise ValueError(step.message.format_map(run.namespace()))


def _decidable(run: _Run, predicate: Predicate) -> bool:
    """A predicate over an omitted optional param has nothing to judge, so it never fires —
    except `present`, whose whole point is to judge exactly that."""
    match predicate:
        case Present():
            return True
        case Not(that=member):
            return _decidable(run, member)
        case AllOf(all=members):
            return all(_decidable(run, member) for member in members)
        case _:
            return all(run.values.get(name) is not None for name in _refs(predicate))


def _holds(run: _Run, predicate: Predicate) -> bool:
    match predicate:
        case IsPlayer(actor=actor):
            return run.entity(actor).id == PLAYER_ID
        case Equals(of=of, value=value):
            return run.read(of) == (run.read(value) if isinstance(value, str) else value)
        case Present(of=of):
            return run.values.get(of[1:]) is not None
        case Carries(actor=actor, item=item):
            return run.entity(item).parent_id == run.entity(actor).id
        case AtLeast(of=of, least=least):
            floor = run.number(least) if isinstance(least, str) else least
            return run.number(of) >= floor
        case Not(that=member):
            return not _holds(run, member)
        case AllOf(all=members):
            return all(_decidable(run, member) and _holds(run, member) for member in members)
        case CounterFull(actor=actor, counter=counter):
            sheet, key = run.sheet(actor), run.text(counter)
            if key not in sheet.counters:
                raise ValueError(f"{run.entity(actor).name} has no {key!r} pool on their sheet")
            return sheet.counters[key].current == sheet.counters[key].maximum
        case HasTag(actor=actor, tag=tag, carried=carried):
            tag_id = run.text(tag)
            if run.sheet(actor).tag(tag_id) is not None:
                return True
            if not carried:
                return False
            held = run.draft.world.children(run.entity(actor).id, "item")
            return any(sheet_of(run.draft, item.id).tag(tag_id) is not None for item in held)


def _mode(run: _Run, token: str | None) -> RollMode:
    value = "normal" if token is None else run.text(token)
    match value:
        case "normal" | "advantage" | "disadvantage":
            return value
        case _:
            raise ValueError(f"{value!r} is no roll mode")


def _roll(run: _Run, step: Roll) -> None:
    vs = step.vs
    if isinstance(vs, str):
        held = run.read(vs)
        if held is not None and (not isinstance(held, int) or isinstance(held, bool)):
            raise ValueError(f"{vs} holds {held!r}, which is no number")
        vs = held  # a null ref is an uncontested roll
    rolled, fact = roll(
        run.text(step.dice),
        step.reason.format_map(run.namespace()),
        run.rng,
        vs=vs,
        mode=_mode(run, step.mode),
        bonus=0 if step.bonus is None else run.number(step.bonus),
    )
    run.values[step.into] = rolled.total
    run.facts.append(fact)


def _outcome(run: _Run, step: Outcome) -> None:
    resolved: dict[Slug, int] = {}
    for label, threshold in step.at.items():
        value = run.read(threshold) if isinstance(threshold, str) else threshold
        if value is None:
            return
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"outcome threshold {label!r} holds {value!r}, which is no number")
        resolved[label] = value
    total = run.number(step.of)
    reached = [label for label, least in resolved.items() if total >= least]
    run.outcome = max(reached, key=lambda label: resolved[label], default=step.default)


def _lookup(run: _Run, step: Lookup) -> None:
    if step.ref is not None:
        reference = parse_ref(run.text(step.ref))
        if reference.collection != step.collection:
            raise ValueError(step.missing.format_map(run.namespace()))
        found = run.content.record(reference)
        if isinstance(found, ContentMiss):
            raise ValueError(f"{found.summary}; use a ref exactly as it was shown")
        record = found
    else:
        assert step.from_entity is not None  # `_one_source` validated at load
        record = _first_of(run, step.from_entity, step.collection, step.require_fact)
        if record is None:
            raise ValueError(step.missing.format_map(run.namespace()))
    run.records[step.into] = record
    run.values[f"{step.into}_name"] = record.name


def _first_of(
    run: _Run, entity: str, collection: CollectionName, require_fact: Slug | None
) -> Record | None:
    for ref in run.sheet(entity).refs:
        if ref.collection != collection:
            continue
        held = run.content.record(ref)
        if isinstance(held, ContentMiss):
            continue
        if require_fact is not None and require_fact not in held.facts:
            continue
        return held
    return None


def _read(run: _Run, step: Read) -> None:
    record = run.record(step.record)
    value = None if record is None else record.facts.get(step.fact)
    run.values[step.into] = step.default if value is None else value


def _ladder(run: _Run, step: Ladder) -> None:
    record = run.record(step.record)
    rows = None if record is None else record.facts.get(step.fact)
    if rows is None:
        run.values[step.into] = None
        return
    if not isinstance(rows, list):
        raise ValueError(f"fact {step.fact!r} holds {rows!r}, which is no ladder")
    key = run.number(step.at)
    best: int | None = None
    picked: JsonValue = None
    for row in rows:
        match row:
            case [int() as threshold, value] if not isinstance(threshold, bool):
                if threshold <= key and (best is None or threshold >= best):
                    best, picked = threshold, value
            case _:
                raise ValueError(f"fact {step.fact!r} row {row!r} is no [threshold, value] pair")
    run.values[step.into] = picked


def _apply(run: _Run, step: Apply) -> None:
    written = {
        key: run.read(value) if isinstance(value, str) else value
        for key, value in step.effect.items()
    }
    effect = EFFECT.validate_python(written)
    run.facts.extend(apply_effect(run.draft, effect, run.default_rules))
