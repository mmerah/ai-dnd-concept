from pathlib import Path


def pack_paths(shipped: Path, extra: Path | None) -> dict[str, Path]:
    """User packs merge over shipped ones by file stem, so one can replace a shipped table set."""
    paths = {path.stem: path for path in sorted(shipped.glob("*.json"))}
    if extra is not None and extra.is_dir():
        paths.update({path.stem: path for path in sorted(extra.glob("*.json"))})
    return paths
