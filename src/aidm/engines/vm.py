from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from random import Random
from string import Formatter
from typing import Annotated, Any, Literal, Self

from pydantic import Field, JsonValue, TypeAdapter, create_model, model_validator

from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Slug
from aidm.state.dice import DiceExpr, roll
from aidm.state.effects import TurnEffect
from aidm.state.facts import Fact
from aidm.state.packs import Value
from aidm.state.sheet import Sheet
from aidm.state.world import GameState, sheet_of

REF = "$"
EFFECT = TypeAdapter[TurnEffect](TurnEffect)

type Resolved = tuple[list[Fact], Slug | None]
type DefaultRules = Callable[[Entity], Sheet]


class ParamBase(Value):
    description: str
    optional: bool = False


class EntityParam(ParamBase):
    type: Literal["entity-id"]


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


type Param = Annotated[
    EntityParam | SlugParam | IntParam | StrParam | EnumParam, Field(discriminator="type")
]


def _annotation(param: Param) -> tuple[Any, Any]:
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


class NumberExpr(Value):
    expr: Literal["number"]
    actor: str
    key: str


class TableExpr(Value):
    expr: Literal["table"]
    on: str
    values: Mapping[str, int]
    default: int = 0


class PresentExpr(Value):
    """An optional param that was written counts as `weight`, one left out as nothing."""

    expr: Literal["present"]
    of: str
    weight: int = 1


type Term = Annotated[NumberExpr | TableExpr | PresentExpr, Field(discriminator="expr")]


class SumExpr(Value):
    expr: Literal["sum"]
    terms: tuple[Term, ...] = Field(min_length=1)


type Expr = Annotated[NumberExpr | TableExpr | PresentExpr | SumExpr, Field(discriminator="expr")]


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


type Predicate = Annotated[HasTag | CounterFull | IsPlayer, Field(discriminator="pred")]


class Let(Value):
    op: Literal["let"]
    name: Slug
    value: Expr


class Require(Value):
    """`message` is formatted with the params, the bound names, and `<param>_name` for each
    entity param, so a refusal can name the actor the model chose."""

    op: Literal["require"]
    that: Predicate
    expect: bool = True
    message: str


class Roll(Value):
    op: Literal["roll"]
    dice: DiceExpr
    reason: str
    bonus: str | None = None
    vs: int | None = None
    into: Slug


class Outcome(Value):
    op: Literal["outcome"]
    of: str
    at: Mapping[Slug, int]
    default: Slug


class Apply(Value):
    op: Literal["apply"]
    effect: dict[str, JsonValue]
    when_outcome: Slug | None = None
    when: Predicate | None = None


type Instruction = Annotated[Let | Require | Roll | Outcome | Apply, Field(discriminator="op")]


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
        named = {f"{name}_name" for name, p in self.params.items() if isinstance(p, EntityParam)}
        for step in self.program:
            if unknown := sorted(name for name in _refs(step) if name not in bound):
                raise ValueError(f"{self.name}: {step.op} reads undefined {unknown}")
            self._check_labels(step)
            match step:
                case Let(name=name) | Roll(into=name):
                    if name in bound:
                        raise ValueError(f"{self.name}: {name!r} is bound twice")
                    bound.add(name)
                case Require(message=message):
                    if unwritable := sorted(_placeholders(message) - bound - named):
                        raise ValueError(f"{self.name}: the refusal names undefined {unwritable}")
                case Apply(effect=effect):
                    _check_effect(self.name, effect)
                case _:
                    pass
        if self.labels and not any(isinstance(step, Outcome) for step in self.program):
            raise ValueError(f"{self.name}: declares outcomes but never picks one")
        return self

    def _check_labels(self, step: Instruction) -> None:
        named: tuple[Slug, ...] = ()
        if isinstance(step, Outcome):
            named = (*step.at, step.default)
        elif isinstance(step, Apply) and step.when_outcome is not None:
            named = (step.when_outcome,)
        if outside := sorted(set(named) - set(self.labels)):
            raise ValueError(f"{self.name}: {outside} is no outcome of this action")

    def model(self) -> type[Frozen]:
        fields: dict[str, Any] = {"act": (Literal[self.name], Field(default=self.name))}
        for name, param in self.params.items():
            annotation, constraints = _annotation(param)
            if param.optional:
                fields[name] = (
                    annotation | None,
                    Field(default=None, description=param.description, **constraints),
                )
            else:
                fields[name] = (annotation, Field(description=param.description, **constraints))
        return create_model(_title(self.name), __base__=Frozen, __doc__=self.doc, **fields)


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
    values: dict[str, JsonValue]
    actors: dict[str, Entity]
    facts: list[Fact] = field(default_factory=list[Fact])
    outcome: Slug | None = None

    def read(self, token: str) -> JsonValue:
        return self.values[token[1:]] if token.startswith(REF) else token

    def text(self, token: str) -> str:
        value = self.read(token)
        if not isinstance(value, str):
            raise ValueError(f"{token} holds {value!r}, which is no name")
        return value

    def number(self, token: str) -> int:
        value = self.read(token)
        if not isinstance(value, int):
            raise ValueError(f"{token} holds {value!r}, which is no number")
        return value

    def actor(self, token: str) -> Entity:
        return self.actors[token[1:]] if token.startswith(REF) else self.actors[token]

    def sheet(self, token: str) -> Sheet:
        return sheet_of(self.draft, self.actor(token).id)

    def namespace(self) -> dict[str, JsonValue]:
        return {**self.values, **{f"{name}_name": e.name for name, e in self.actors.items()}}


def run_program(
    program: tuple[Instruction, ...],
    draft: GameState,
    action: Frozen,
    rng: Random,
    default_rules: DefaultRules,
    params: Mapping[str, Param],
) -> Resolved:
    """Straight-line: every refusal is a `ValueError` the kernel's trial resolve turns into a
    retry, so a declarative action needs no separate check."""
    values: dict[str, JsonValue] = action.model_dump()
    run = _Run(
        draft=draft,
        rng=rng,
        default_rules=default_rules,
        values=values,
        actors={
            name: require_actor_here(draft, EntityId(str(values[name])))
            for name, param in params.items()
            if isinstance(param, EntityParam) and values.get(name) is not None
        },
    )
    for step in program:
        _step(run, step)
    return run.facts, run.outcome


def _step(run: _Run, step: Instruction) -> None:
    match step:
        case Let(name=name, value=value):
            run.values[name] = _evaluate(run, value)
        case Require():
            _require(run, step)
        case Roll():
            _roll(run, step)
        case Outcome(of=of, at=at, default=default):
            total = run.number(of)
            reached = [label for label, least in at.items() if total >= least]
            run.outcome = max(reached, key=lambda label: at[label], default=default)
        case Apply():
            _apply(run, step)


def _evaluate(run: _Run, expr: Expr) -> int:
    match expr:
        case SumExpr(terms=terms):
            return sum(_evaluate(run, term) for term in terms)
        case NumberExpr(actor=actor, key=key):
            sheet, name = run.sheet(actor), run.text(key)
            if name not in sheet.numbers:
                raise ValueError(f"{run.actor(actor).name} has no {name!r} on their sheet")
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
    """A predicate over an omitted optional param has nothing to judge, so it never fires."""
    return all(run.values.get(name) is not None for name in _refs(predicate))


def _holds(run: _Run, predicate: Predicate) -> bool:
    match predicate:
        case IsPlayer(actor=actor):
            return run.actor(actor).id == PLAYER_ID
        case CounterFull(actor=actor, counter=counter):
            sheet, key = run.sheet(actor), run.text(counter)
            if key not in sheet.counters:
                raise ValueError(f"{run.actor(actor).name} has no {key!r} pool on their sheet")
            return sheet.counters[key].current == sheet.counters[key].maximum
        case HasTag(actor=actor, tag=tag, carried=carried):
            tag_id = run.text(tag)
            if run.sheet(actor).tag(tag_id) is not None:
                return True
            if not carried:
                return False
            held = run.draft.world.children(run.actor(actor).id, "item")
            return any(sheet_of(run.draft, item.id).tag(tag_id) is not None for item in held)


def _roll(run: _Run, step: Roll) -> None:
    rolled, fact = roll(
        step.dice,
        run.text(step.reason),
        run.rng,
        vs=step.vs,
        bonus=0 if step.bonus is None else run.number(step.bonus),
    )
    run.values[step.into] = rolled.total
    run.facts.append(fact)


def _apply(run: _Run, step: Apply) -> None:
    if step.when_outcome is not None and step.when_outcome != run.outcome:
        return
    if step.when is not None and not (_decidable(run, step.when) and _holds(run, step.when)):
        return
    written = {
        key: run.read(value) if isinstance(value, str) else value
        for key, value in step.effect.items()
    }
    effect = EFFECT.validate_python(written)
    run.facts.extend(apply_effect(run.draft, effect, run.default_rules))
