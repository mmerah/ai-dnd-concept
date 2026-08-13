import re
from dataclasses import dataclass
from random import Random
from typing import Literal

from .facts import CORE, Fact

# Bounds prevent model-written expressions from stalling a turn.
_DICE = re.compile(r"^([1-9]\d{0,2})d([1-9]\d{0,3})$")

RollMode = Literal["normal", "advantage"]


@dataclass(frozen=True, slots=True)
class Rolled:
    total: int
    dice: tuple[int, ...]


def _evaluate(expression: str, rng: Random) -> Rolled:
    matched = _DICE.match(expression.replace(" ", ""))
    if matched is None:
        raise ValueError(f"malformed dice expression {expression!r}")
    drawn = tuple(rng.randint(1, int(matched[2])) for _ in range(int(matched[1])))
    return Rolled(total=sum(drawn), dice=drawn)


def roll(
    expression: str,
    reason: str,
    rng: Random,
    *,
    mode: RollMode = "normal",
) -> tuple[Rolled, Fact]:
    kept, dropped = _evaluate(expression, rng), None
    if mode == "advantage":
        pair = sorted((kept, _evaluate(expression, rng)), key=lambda outcome: outcome.total)
        kept, dropped = pair[-1], pair[0]
    against = "" if dropped is None else f" ({mode}, dropped {dropped.total})"
    faces = ", ".join(str(die) for die in kept.dice)
    return kept, Fact(
        source=CORE,
        kind="dice_rolled",
        trace=f"{reason}: {expression} [{faces}] -> {kept.total}{against}",
        data={
            "dice": expression,
            "mode": mode,
            "rolled": list(kept.dice),
            "total": kept.total,
            "reason": reason,
        },
    )
