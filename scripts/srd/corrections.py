"""Corrections to upstream data, applied to the projected records.

Upstream is authoritative about content and occasionally wrong about a number. A defect that a rule
would read as a legal value cannot be left in the pack: the rogue's *cumulative* ability score total
falls at level 11, and a level-up is the diff of two of those totals, so the pack as published says
level 11 takes an improvement away and level 12 grants two.

Applied here rather than to the written JSON, so the pack stays a function of the checkout and the
byte-identical round-trip is still the regression check. Every entry must still bite: an upstream
fix raises here instead of silently patching nothing, which keeps this list from rotting."""

from collections.abc import Mapping

from aidm_5e.content.records.base import Collection, Record
from aidm_5e.utils.models import Slug

# A 5e rogue takes an ability score improvement at 4, 8, 10, 12, 16 and 19, so the cumulative total
# is the count of those levels reached: 0,0,0,1,1,1,1,2,2,3,3,4,4,4,4,5,5,5,6,6. Upstream is right
# at every level that grants one and a step behind at the levels in between. The other 11 classes
# agree with the SRD, fighter's extra improvements at 6 and 14 included.
_ROGUE_IMPROVEMENTS = {11: 3, 13: 4, 14: 4, 15: 4, 17: 5, 18: 5, 20: 6}

# Record -> the fields upstream got wrong, with the value the SRD states. Keyed by collection and
# index, so a correction to any record of any collection is one line.
CORRECTIONS: Mapping[Collection, Mapping[Slug, Mapping[str, object]]] = {
    "levels": {
        f"rogue-{level}": {"ability_score_bonuses": total}
        for level, total in _ROGUE_IMPROVEMENTS.items()
    },
}


def corrected(
    collections: Mapping[Collection, Mapping[str, Record]],
) -> dict[Collection, Mapping[str, Record]]:
    """The projection with every correction applied. A correction only ever rewrites fields of a
    record that exists, so no count a manifest declares can move."""
    patched = dict(collections)
    for name, fixes in CORRECTIONS.items():
        patched[name] = _fixed(collections[name], fixes)
    return patched


def _fixed(
    records: Mapping[str, Record], fixes: Mapping[Slug, Mapping[str, object]]
) -> dict[str, Record]:
    """Each correction revalidated through `updated`, so a field that upstream renamed away is a
    failure here rather than a silently dropped fix."""
    corrected = dict(records)
    for index, fields in fixes.items():
        before = corrected.get(index)
        if before is None:
            raise ValueError(f"correction names {index!r}, which the projection does not produce")
        after = type(before).model_validate({**before.model_dump(round_trip=True), **fields})
        if after == before:
            raise ValueError(f"correction to {index!r} changes nothing: upstream fixed it, drop it")
        corrected[index] = after
    return corrected
