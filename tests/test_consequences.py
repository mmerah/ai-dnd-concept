"""The vocabulary's own contracts: what `_own_refs` and the trace panel read off the classes.
Both scans are silent by nature — an id they cannot see is an id nobody validates — so what they
rely on is asserted here rather than left to the next author to remember."""

from typing import get_args

from aidm.domain.models import CONSEQUENCE_TYPES, EntityId, References, RollCheck, branches


def mentions_an_id(annotation: object) -> bool:
    return annotation is EntityId or any(mentions_an_id(a) for a in get_args(annotation))


def test_every_id_field_declares_what_it_references() -> None:
    """An id field with no `References` marker is an id the Director may invent unchecked. This
    also catches a marker written inside a union member or a list, where pydantic drops it from
    `field.metadata` and the scan would see nothing."""
    for consequence in CONSEQUENCE_TYPES:
        for name, field in consequence.model_fields.items():
            if mentions_an_id(field.annotation):
                marked = any(isinstance(m, References) for m in field.metadata)
                assert marked, f"{consequence.__name__}.{name} names an id but declares nothing"


def test_branch_names_are_real_fields() -> None:
    """The trace panel excludes branches from its field dump by these names, and `model_dump`
    ignores an unknown name silently — a typo would leak the branch back in as an opaque dict."""
    check = RollCheck(ability="wisdom", dc=10)
    assert set(branches(check)) <= set(RollCheck.model_fields)
