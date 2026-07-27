"""5e content: the canonical record model and the packs that ship it.

The vendored SRD pack is one pack among the third-party ones authors will write, in the same
format. This is the pack API plus the handful of record types the application itself reads; an
importer or a test that needs the rest imports `aidm.content.records` directly, and a caller that
needs only a closed vocabulary imports `aidm.content.vocabulary` — which is all `domain/` does."""

from .library import ContentMiss, Library, MissReason, load, write_pack
from .models import COLLECTIONS, Manifest, Pack, PackStamp
from .records import (
    Collection,
    ContentRef,
    DamageRoll,
    MonsterAction,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
    Record,
)

__all__ = [
    "COLLECTIONS",
    "Collection",
    "ContentMiss",
    "ContentRef",
    "DamageRoll",
    "Library",
    "Manifest",
    "MissReason",
    "MonsterAction",
    "MonsterAttack",
    "MonsterMultiattack",
    "MonsterProcedure",
    "MonsterRecord",
    "MonsterSave",
    "Pack",
    "PackStamp",
    "Record",
    "load",
    "write_pack",
]
