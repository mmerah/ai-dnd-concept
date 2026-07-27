"""Flattening upstream's recursive `Choice`/`OptionSet` tree into one `ProgressionChoice`.

A nested arm's options are **unioned** into its parent's and the pick counts multiplied. Equal pick
counts across the arms are necessary but not sufficient for that to be exact — unioning also lets a
pick be spent in one arm and the next in another, which the arms did not offer. Both nodes it
applies to are exact anyway, checked by hand against v5.10.0:

- the monk's "one artisan's tool or one musical instrument" spends 1 pick either way, so 1 from 29
  cannot combine anything;
- `rogue-expertise-1`'s "two skills, or one skill and thieves' tools" is 2 from 19, and every
  cross-arm pair — a skill and the tools — is a combination the second arm already allowed.

`_arms` still refuses arms that disagree about pick count, which is the shape a third node would
most likely arrive in. Only `starting_equipment_options` disagrees today, and this pack does not
project it."""

from collections.abc import Iterator, Sequence

from aidm.content.records import (
    AbilityBonus,
    BonusOption,
    ChoiceEffect,
    ChoiceOption,
    Collection,
    ContentRef,
    ProgressionChoice,
    RecordOption,
)

from .common import PACK_ID, ability
from .upstream import Choice, Option


def flatten(
    node: Choice,
    id: str,
    collection: Collection | None = None,
    *,
    universe: Sequence[ChoiceOption] = (),
    effect: ChoiceEffect = "grant",
) -> ProgressionChoice:
    """`collection` is where this choice's `reference` options point; `None` is for a choice whose
    options are not records at all (a race's "+1 to two abilities of your choice"). `universe`
    stands in for a `resource_list` option set, which names a whole collection by url rather than
    listing it (the Acolyte's "two languages of your choice")."""
    picks, options = _arms(node, collection, universe)
    return ProgressionChoice(
        id=id,
        prompt=node.desc or f"choose {picks}",
        choose=picks,
        effect=effect,
        options=tuple(_deduplicated(options)),
    )


def _arms(
    node: Choice, collection: Collection | None, universe: Sequence[ChoiceOption]
) -> tuple[int, list[ChoiceOption]]:
    if node.options.option_set_type == "resource_list":
        return node.choose, list(universe)  # an empty one is refused by `options`' min_length
    arms = [_arm(option, collection, universe) for option in node.options.options]
    spent = {picks for picks, _ in arms}
    if len(spent) != 1:
        raise ValueError(f"choice {node.desc!r} has arms spending {sorted(spent)} picks")
    return node.choose * spent.pop(), [o for _, options in arms for o in options]


def _arm(
    option: Option, collection: Collection | None, universe: Sequence[ChoiceOption]
) -> tuple[int, list[ChoiceOption]]:
    """How many picks this arm spends, and what they may be spent on."""
    match option.option_type:
        case "reference" if option.item is not None and collection is not None:
            ref = ContentRef(pack=PACK_ID, collection=collection, index=option.item.index)
            return 1, [RecordOption(label=option.item.name, ref=ref)]
        case "ability_bonus" if option.ability_score is not None and option.bonus is not None:
            bonus = AbilityBonus(ability=ability(option.ability_score.index), bonus=option.bonus)
            return 1, [BonusOption(bonus=bonus)]
        case "multiple":
            nested = [_arm(item, collection, universe) for item in option.items]
            return sum(p for p, _ in nested), [o for _, options in nested for o in options]
        case "choice" if option.choice is not None:
            return _arms(option.choice, collection, universe)
        case _:
            raise ValueError(f"unprojected option shape {option!r}")


def _deduplicated(options: Sequence[ChoiceOption]) -> Iterator[ChoiceOption]:
    """Unioned arms overlap — all 18 skills appear in both of `rogue-expertise-1`'s."""
    seen: set[str] = set()
    for option in options:
        if option.key not in seen:
            seen.add(option.key)
            yield option
