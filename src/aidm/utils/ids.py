"""Deterministic id-minting: a name becomes a unique, stable EntityId."""

import re
from collections.abc import Iterable

from ..domain.models import EntityId


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, n = EntityId(base), 2
    while candidate in used:
        candidate, n = EntityId(f"{base}_{n}"), n + 1
    return candidate
