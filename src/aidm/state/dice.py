from collections.abc import Callable, Sequence
from random import Random

from .facts import CORE, Fact


def roll_pool(faces: Sequence[int], reason: str, rng: Random) -> tuple[int, Fact]:
    """Roll one die per entry and keep the highest; a single die is a pool of one."""
    return _rolled(faces, reason, rng, max)


def roll_sum(faces: Sequence[int], reason: str, rng: Random) -> tuple[int, Fact]:
    """Roll one die per entry and total them: a 3d6 attribute or a scar's recovery roll."""
    return _rolled(faces, reason, rng, sum)


def _rolled(
    faces: Sequence[int], reason: str, rng: Random, keep: Callable[[tuple[int, ...]], int]
) -> tuple[int, Fact]:
    if not faces:
        raise ValueError("a dice pool rolls at least one die")
    drawn = tuple(rng.randint(1, face) for face in faces)
    kept = keep(drawn)
    shown = ", ".join(str(die) for die in drawn)
    return kept, Fact(
        source=CORE,
        kind="dice_rolled",
        trace=f"{reason}: {_notation(faces)} [{shown}] -> {kept}",
        data={"faces": list(faces), "rolled": list(drawn), "kept": kept, "reason": reason},
    )


def _notation(faces: Sequence[int]) -> str:
    """`2d6` for a uniform pool, `d8+d10` for a mixed one."""
    if len(set(faces)) == 1:
        return f"{len(faces)}d{faces[0]}"
    return "+".join(f"d{face}" for face in faces)
