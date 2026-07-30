import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

MOD = "MOD"

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


@dataclass(frozen=True, slots=True)
class ModifierTerm:
    sign: Sign


Term = DiceTerm | ConstantTerm | ModifierTerm


def terms(expression: str) -> tuple[Term, ...]:
    """Reject leading signs because the consuming action owns the outcome's sign."""
    pieces = _OPERATORS.split(expression.replace(" ", ""))
    parsed = [_term(pieces[0], 1)]
    for operator, word in zip(pieces[1::2], pieces[2::2], strict=True):
        parsed.append(_term(word, -1 if operator == "-" else 1))
    return tuple(parsed)


def _term(word: str, sign: Sign) -> Term:
    if word == MOD:
        return ModifierTerm(sign=sign)
    if rolled := _DICE.match(word):
        return DiceTerm(sign=sign, count=int(rolled[1]), faces=int(rolled[2]))
    if _CONSTANT.match(word):
        return ConstantTerm(sign=sign, value=int(word))
    raise ValueError(f"malformed dice term {word!r}")


def is_constant(expression: str) -> bool:
    return all(isinstance(term, ConstantTerm) for term in terms(expression))


def _word(term: DiceTerm | ConstantTerm) -> str:
    return f"{term.count}d{term.faces}" if isinstance(term, DiceTerm) else str(term.value)


def substituted(expression: str, modifier: int) -> str:
    """Fold a caster's own modifier into every MOD term, so the result is rollable on its own.
    Signs are recombined rather than pasted, because a negative modifier would leave '+ -2'."""
    parsed = terms(expression)
    if isinstance(parsed[0], ModifierTerm) and modifier < 0:
        # A leading sign has no valid spelling, so this cannot be written rather than mis-signed.
        raise ValueError(f"a leading {MOD} cannot carry the negative modifier {modifier}")
    words: list[str] = []
    for term in parsed:
        negative = (term.sign < 0) != (isinstance(term, ModifierTerm) and modifier < 0)
        word = str(abs(modifier)) if isinstance(term, ModifierTerm) else _word(term)
        words.append(f"{'-' if negative else '+'} {word}" if words else word)
    return " ".join(words)


def _parseable(expression: str) -> str:
    terms(expression)
    return expression


def _self_contained(expression: str) -> str:
    if any(isinstance(term, ModifierTerm) for term in terms(expression)):
        raise ValueError(f"{MOD} is a caster's own modifier and cannot be rolled on its own")
    return expression


def _positive(expression: str) -> str:
    parsed = terms(expression)
    if any(term.sign < 0 for term in parsed):
        raise ValueError("a positive dice expression cannot subtract")
    if not any(
        isinstance(term, DiceTerm) or (isinstance(term, ConstantTerm) and term.value > 0)
        for term in parsed
    ):
        raise ValueError("a positive dice expression must roll or add something")
    return expression


DiceExpr = Annotated[
    str,
    AfterValidator(_parseable),
    Field(max_length=MAX_LENGTH, examples=["1d8", "2d6 + 3", "1d4 - 1"]),
]

# Role-written dice cannot leave a caster modifier unresolved.
SelfContainedDice = Annotated[DiceExpr, AfterValidator(_self_contained)]
PositiveDice = Annotated[SelfContainedDice, AfterValidator(_positive)]
