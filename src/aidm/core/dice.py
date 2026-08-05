import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

# Bounds prevent model-written expressions from stalling a turn.
_DICE = re.compile(r"^([1-9]\d{0,2})d([1-9]\d{0,3})$")
_CONSTANT = re.compile(r"^\d{1,4}$")
_OPERATORS = re.compile(r"([+-])")
MAX_LENGTH = 64

Sign = Literal[1, -1]


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
