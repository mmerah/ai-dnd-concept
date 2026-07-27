"""The offline 5e-database importer, split to mirror `aidm.content.records`.

Upstream models are `extra="ignore"`, so a rename there cannot be caught here — only by
`tests/test_content.py`'s corpus invariants."""

from .build import PACK_ID, build

__all__ = ["PACK_ID", "build"]
