"""Dice expressions: `2d8 + 4d6`, `1d6-1`, `10`, `1d8 + MOD`"""

import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

MOD = "MOD"

# `_term` is the only constructor of a term, so these bounds are the whole of a term's validation.
# Digit counts are capped so a pathological expression cannot stall a turn.
_DICE = re.compile(r"^([1-9]\d{0,2})d([1-9]\d{0,3})$")
_CONSTANT = re.compile(r"^\d{1,4}$")
_OPERATORS = re.compile(r"([+-])")

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


@dataclass(frozen=True, slots=True)
class ModifierTerm:
    sign: Sign


Term = DiceTerm | ConstantTerm | ModifierTerm


def terms(expression: str) -> tuple[Term, ...]:
    """A leading sign is refused: the sign of an outcome lives in the verb consuming the roll."""
    pieces = _OPERATORS.split(expression.replace(" ", ""))
    parsed = [_term(pieces[0], 1)]
    for operator, word in zip(pieces[1::2], pieces[2::2], strict=True):
        parsed.append(_term(word, -1 if operator == "-" else 1))
    return tuple(parsed)


def _term(word: str, sign: Sign) -> Term:
    if word == MOD:
        return ModifierTerm(sign=sign)
    rolled = _DICE.match(word)
    if rolled is not None:
        return DiceTerm(sign=sign, count=int(rolled[1]), faces=int(rolled[2]))
    if _CONSTANT.match(word):
        return ConstantTerm(sign=sign, value=int(word))
    raise ValueError(f"malformed dice term {word!r}")


def _parseable(expression: str) -> str:
    terms(expression)  # the parse is the validation, so a bad expression fails at its boundary
    return expression


DiceExpr = Annotated[str, AfterValidator(_parseable), Field(examples=["1d8", "2d6 + 3", "4"])]
