"""One-shot, offline importer: a checkout of 5e-bits/5e-database becomes `packs/srd-2014/`.

    uv run python scripts/import_srd.py ../5e-database [out-dir]

Run it by hand and commit the result: the shipped pack *is* the edition pin. The projection itself
lives in `srd/`, one module per record family."""

import sys
from collections.abc import Sequence
from pathlib import Path

from srd import PACK_ID, build

from aidm.content import write_pack


def main(argv: Sequence[str]) -> None:
    if not 1 <= len(argv) <= 2:
        raise SystemExit("usage: import_srd.py <5e-database checkout> [out-dir]")
    out = Path(argv[1]) if len(argv) == 2 else Path("packs") / PACK_ID
    pack = build(Path(argv[0]))
    write_pack(out, pack)
    print(f"wrote {out} at v{pack.manifest.version}: {pack.manifest.provides}")


if __name__ == "__main__":
    main(sys.argv[1:])
