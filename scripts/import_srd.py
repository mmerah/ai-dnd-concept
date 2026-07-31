"""One-shot, offline importer: a checkout of 5e-bits/5e-database becomes the shipped
`aidm_5e/data/srd-2014/` pack.

    uv run python scripts/import_srd.py ../5e-database [out-dir]

Run it by hand and commit the result: the shipped pack *is* the edition pin. The projection itself
lives in `srd/`, one module per record family."""

import sys
from collections.abc import Sequence
from pathlib import Path

from srd.build import build
from srd.common import PACK_ID

from aidm_5e.content.library import write_pack

SHIPPED_PACK_DIR = Path(__file__).parent.parent / "src" / "aidm_5e" / "data"


def main(argv: Sequence[str]) -> None:
    if not 1 <= len(argv) <= 2:
        raise SystemExit("usage: import_srd.py <5e-database checkout> [out-dir]")
    out = Path(argv[1]) if len(argv) == 2 else SHIPPED_PACK_DIR / PACK_ID
    pack = build(Path(argv[0]))
    write_pack(out, pack)
    print(f"wrote {out} at v{pack.manifest.version}: {pack.manifest.provides}")


if __name__ == "__main__":
    main(sys.argv[1:])
