from typing import ClassVar

from pydantic import field_validator

from aidm.core.packs import Record

from ...values import Ability
from ..vocabulary import ALIGNMENT_NAMES, CONDITION_NAMES, LANGUAGE_NAMES


class VocabularyRecord(Record):
    """Validates inherited indexes because Pydantic forbids narrowing mutable fields."""

    VOCABULARY: ClassVar[tuple[str, ...]] = ()

    @field_validator("index")
    @classmethod
    def _in_vocabulary(cls, index: str) -> str:
        if index not in cls.VOCABULARY:
            raise ValueError(f"{index!r} is not one of {cls.VOCABULARY}")
        return index


class SkillRecord(Record):
    ability: Ability


class ConditionRecord(VocabularyRecord):
    VOCABULARY: ClassVar[tuple[str, ...]] = CONDITION_NAMES
    desc: str


class AlignmentRecord(VocabularyRecord):
    VOCABULARY: ClassVar[tuple[str, ...]] = ALIGNMENT_NAMES
    abbreviation: str
    desc: str


class LanguageRecord(VocabularyRecord):
    VOCABULARY: ClassVar[tuple[str, ...]] = LANGUAGE_NAMES
    script: str | None = None
    typical_speakers: tuple[str, ...] = ()
