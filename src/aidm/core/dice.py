import re
from dataclasses import dataclass
from random import Random
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from .facts import CORE, Fact

# Bounds prevent model-written expressions from stalling a turn.
_DICE = re.compile(r"^([1-9]\d{0,2})d([1-9]\d{0,3})$")
_CONSTANT = re.compile(r"^\d{1,4}$")
_OPERATORS = re.compile(r"([+-])")
MAX_LENGTH = 64

Sign = Literal[1, -1]
RollMode = Literal["normal", "advantage", "disadvantage"]


@dataclass(frozen=True, slots=True)
class DiceTerm:
    sign: Sign
    count: int
    faces: int


@dataclass(frozen=True, slots=True)
class ConstantTerm:
    sign: Sign
    value: int


Term = DiceTerm | ConstantTerm


def terms(expression: str) -> tuple[Term, ...]:
    pieces = _OPERATORS.split(expression.replace(" ", ""))
    parsed = [_term(pieces[0], 1)]
    for operator, word in zip(pieces[1::2], pieces[2::2], strict=True):
        parsed.append(_term(word, -1 if operator == "-" else 1))
    return tuple(parsed)


def _term(word: str, sign: Sign) -> Term:
    if rolled := _DICE.match(word):
        return DiceTerm(sign=sign, count=int(rolled[1]), faces=int(rolled[2]))
    if _CONSTANT.match(word):
        return ConstantTerm(sign=sign, value=int(word))
    raise ValueError(f"malformed dice term {word!r}")


def _parseable(expression: str) -> str:
    _ = terms(expression)
    return expression


DiceExpr = Annotated[
    str,
    AfterValidator(_parseable),
    Field(max_length=MAX_LENGTH, examples=["1d8", "2d6 + 3", "1d4 - 1"]),
]


@dataclass(frozen=True, slots=True)
class Rolled:
    total: int
    dice: tuple[int, ...]


def _evaluate(expression: str, rng: Random) -> Rolled:
    total = 0
    dice: list[int] = []
    for term in terms(expression):
        match term:
            case DiceTerm(sign=sign, count=count, faces=faces):
                drawn = [rng.randint(1, faces) for _ in range(count)]
                dice.extend(drawn)
                total += sign * sum(drawn)
            case ConstantTerm(sign=sign, value=value):
                total += sign * value
    return Rolled(total=total, dice=tuple(dice))


def roll(
    expression: str,
    reason: str,
    rng: Random,
    *,
    vs: int | None = None,
    mode: RollMode = "normal",
    bonus: int = 0,
) -> tuple[Rolled, Fact]:
    if bonus:
        expression = f"{expression} {'+' if bonus > 0 else '-'} {abs(bonus)}"
    kept, dropped = _evaluate(expression, rng), None
    if mode != "normal":
        pair = sorted((kept, _evaluate(expression, rng)), key=lambda outcome: outcome.total)
        kept, dropped = (pair[-1], pair[0]) if mode == "advantage" else (pair[0], pair[-1])
    success = None if vs is None else kept.total >= vs
    verdict = "" if success is None else f" vs {vs}: {'SUCCESS' if success else 'FAILURE'}"
    against = "" if dropped is None else f" ({mode}, dropped {dropped.total})"
    faces = ", ".join(str(die) for die in kept.dice)
    return kept, Fact(
        source=CORE,
        kind="dice_rolled",
        trace=f"{reason}: {expression} [{faces}] -> {kept.total}{against}{verdict}",
        narrator=None if success is None else f"{reason}: {'success' if success else 'failure'}",
        data={
            "dice": expression,
            "mode": mode,
            "rolled": list(kept.dice),
            "total": kept.total,
            "vs": vs,
            "success": success,
            "reason": reason,
        },
    )
