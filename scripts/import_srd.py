"""One-shot, offline importer: a checkout of 5e-bits/5e-database becomes the shipped
`aidm/engines/dnd5e/packs/srd-2014/` lenient pack.

    uv run python scripts/import_srd.py ../5e-database [out-dir]

Run it by hand and commit the result: the shipped pack *is* the edition pin."""

import re
import sys
from collections.abc import Sequence
from pathlib import Path

from srd.build import build
from srd.project import PACK_ID

from aidm.core.packs import write_pack

REPOSITORY_ROOT = Path(__file__).parent.parent
SHIPPED_PACK_DIR = REPOSITORY_ROOT / "src" / "aidm" / "engines" / "dnd5e" / "packs"
SAVE_VERSION_FILE = REPOSITORY_ROOT / "src" / "aidm" / "core" / "base.py"
SAVE_VERSION_PATTERN = re.compile(r"^SAVE_VERSION = (\d+)$", re.MULTILINE)


def bump_save_version() -> int:
    """Actor stats are snapshots of pack content, so a regenerated pack invalidates every save."""
    body = SAVE_VERSION_FILE.read_text(encoding="utf-8")
    found = SAVE_VERSION_PATTERN.search(body)
    if found is None:
        raise SystemExit(f"no SAVE_VERSION assignment in {SAVE_VERSION_FILE}")
    bumped = int(found.group(1)) + 1
    SAVE_VERSION_FILE.write_text(
        SAVE_VERSION_PATTERN.sub(f"SAVE_VERSION = {bumped}", body, count=1),
        encoding="utf-8",
    )
    return bumped


def main(argv: Sequence[str]) -> None:
    if not 1 <= len(argv) <= 2:
        raise SystemExit("usage: import_srd.py <5e-database checkout> [out-dir]")
    out = SHIPPED_PACK_DIR / PACK_ID if len(argv) == 1 else Path(argv[1])
    shipped = out.resolve() == (SHIPPED_PACK_DIR / PACK_ID).resolve()
    pack = build(Path(argv[0]))
    write_pack(out, pack)
    print(f"wrote {out} at v{pack.manifest.version}: {pack.manifest.provides}")
    if shipped:
        print(f"bumped SAVE_VERSION to {bump_save_version()}")


if __name__ == "__main__":
    main(sys.argv[1:])
