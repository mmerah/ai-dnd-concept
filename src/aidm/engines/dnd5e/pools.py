from collections.abc import Mapping

from aidm.engines.counters import Counter
from aidm.state.base import Slug

# How many rages the class has at a level, highest rung first; below the last rung it is two. The
# pack spells this as a string ("2" … "unlimited"), so the ladder lives here instead.
# ponytail: level 20 is unlimited in the SRD, and a counter with a recharge must have a maximum,
# so a level-20 barbarian rages six times. Model an unbounded pool upstream to lift it.
_RAGES: tuple[tuple[int, int], ...] = ((17, 6), (12, 5), (6, 4), (3, 3))
_LAY_ON_HANDS_PER_LEVEL = 5
# Font of Inspiration: from level 5 the bard's inspiration comes back on a short rest.
_FONT_OF_INSPIRATION = 5


def feature_pool(
    index: Slug, level: int, modifiers: Mapping[Slug, int]
) -> tuple[Slug, Counter] | None:
    """The pool a class feature brings, at the size its own prose gives it for this level and the
    ability modifier it scales on. Authored because nothing upstream answers it: `feature_specific`
    is None for all six, every size is `desc` prose, and the level rows count ki and sorcery points
    but never rage, lay on hands or bardic inspiration."""
    charisma = modifiers["charisma"]
    match index:
        case "rage":
            return _held("rage", next((n for rung, n in _RAGES if level >= rung), 2), "long-rest")
        case "second-wind":
            return _held("second-wind", 1, "short-rest")
        case "bardic-inspiration-d6":
            # The die grows with the level and the sheet's `bardic-inspiration-die` carries it;
            # what this counts is the uses, which is the Charisma modifier and at least one.
            rest = "short-rest" if level >= _FONT_OF_INSPIRATION else "long-rest"
            return _held("bardic-inspiration", max(1, charisma), rest)
        case "divine-sense":
            return _held("divine-sense", 1 + charisma, "long-rest")
        case "lay-on-hands":
            return _held("lay-on-hands", _LAY_ON_HANDS_PER_LEVEL * level, "long-rest")
        case "arcane-recovery":
            return _held("arcane-recovery", 1, "long-rest")
        case _:
            # One pool behind the three refs a druid collects as its shapes widen.
            return _held("wild-shape", 2, "short-rest") if index.startswith("wild-shape-") else None


def _held(key: Slug, uses: int, recharge: str) -> tuple[Slug, Counter] | None:
    """A paladin whose Charisma is a penalty has no Divine Sense to spend, and a 0/0 counter would
    advertise a use it can never make; the pool arrives when the score does."""
    if uses < 1:
        return None
    return key, Counter(current=uses, maximum=uses, recharge=recharge)
