from collections.abc import Mapping
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from aidm.content.store import ENCODING
from aidm.state.base import Frozen
from aidm.state.creation import ContentSlug


class PackEntry(Frozen):
    id: ContentSlug
    label: str
    # Empty for packs whose entries are bare phrases, such as AP01.
    detail: str = ""


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
    source: str
    license: str
    concepts: tuple[PackEntry, ...] = Field(min_length=1)
    skills: tuple[PackEntry, ...] = Field(min_length=1)
    frailties: tuple[PackEntry, ...] = Field(min_length=1)
    gear: tuple[PackEntry, ...] = Field(min_length=1)
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _twist_columns_pair_up(self) -> Self:
        if (self.twist_subjects is None) != (self.twist_actions is None):
            raise ValueError("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != 6:
                raise ValueError("a twist column is one d6: exactly six entries")
        return self


def load_packs(directory: Path) -> dict[str, Pack]:
    packs = {
        path.stem: Pack.model_validate_json(path.read_text(encoding=ENCODING))
        for path in sorted(directory.glob("*.json"))
    }
    if not packs:
        raise ValueError(f"no packs in {str(directory)!r}")
    return packs


def twist_table(packs: Mapping[str, Pack]) -> tuple[tuple[str, str], ...]:
    """Exactly one pack carries the twist columns; the resolver rolls against that one."""
    carrying = [
        pack
        for pack in packs.values()
        if pack.twist_subjects is not None and pack.twist_actions is not None
    ]
    if len(carrying) != 1:
        raise ValueError("exactly one pack must carry the twist table")
    chosen = carrying[0]
    assert chosen.twist_subjects is not None and chosen.twist_actions is not None
    return tuple(zip(chosen.twist_subjects, chosen.twist_actions, strict=True))
