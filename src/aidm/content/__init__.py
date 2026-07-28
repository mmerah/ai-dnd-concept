"""5e content: the canonical record model and the packs that ship it.

The vendored SRD pack is one pack among the third-party ones authors will write, in the same
format. This is the pack API plus the handful of record types the application itself reads; an
importer or a test that needs the rest imports `aidm.content.records` directly, and a caller that
needs only a closed vocabulary imports `aidm.content.vocabulary` — which is all `domain/` does."""

from .library import Content, ContentMiss, load, loaded, read_pack, write_pack
from .models import Manifest, Pack, PackStamp
from .records import (
    ContentRef,
    DamageRoll,
    MonsterAction,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
)
from .registry import COLLECTION_SPECS

__all__ = [
    "COLLECTION_SPECS",
    "Content",
    "ContentMiss",
    "ContentRef",
    "DamageRoll",
    "Manifest",
    "MonsterAction",
    "MonsterAttack",
    "MonsterMultiattack",
    "MonsterProcedure",
    "MonsterRecord",
    "MonsterSave",
    "Pack",
    "PackStamp",
    "load",
    "loaded",
    "read_pack",
    "write_pack",
]
