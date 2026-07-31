from collections.abc import Sequence
from pathlib import Path

from .content.library import load
from .engine.pack_ruleset import compile_ruleset
from .facade import Dnd5eEngine


def create_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Dnd5eEngine:
    selected = (
        (Path(__file__).parent / "data" / "srd-2014",) if pack_paths is None else tuple(pack_paths)
    )
    return Dnd5eEngine(compile_ruleset(load(selected)))
