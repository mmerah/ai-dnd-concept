"""The vocabularies that ship a payload: skills, conditions, alignments, languages.

A collection whose records carry nothing but a name is a `Literal` in `vocabulary.py` and no
collection at all. These four are here because each carries something a role can be shown or
`engine/` can read — the ability behind a skill, the rule text of a condition."""

from typing import ClassVar

from pydantic import field_validator

from ...utils.models import Ability
from ..vocabulary import ALIGNMENT_NAMES, CONDITION_NAMES, LANGUAGE_NAMES
from .base import Collection, Record


class VocabularyRecord(Record):
    """A record whose `index` must name a member of a closed vocabulary — because the vocabulary is
    what other records reference, so an index outside it is a record nothing can ever point at.
    Checked here rather than by narrowing `index`, which a subclass may not do to a mutable
    field."""

    VOCABULARY: ClassVar[tuple[str, ...]] = ()

    @field_validator("index")
    @classmethod
    def _in_vocabulary(cls, index: str) -> str:
        if index not in cls.VOCABULARY:
            raise ValueError(f"{index!r} is not one of {cls.VOCABULARY}")
        return index


class SkillRecord(Record):
    COLLECTION: ClassVar[Collection] = "skills"
    ability: Ability


class ConditionRecord(VocabularyRecord):
    COLLECTION: ClassVar[Collection] = "conditions"
    VOCABULARY: ClassVar[tuple[str, ...]] = CONDITION_NAMES
    desc: str


class AlignmentRecord(VocabularyRecord):
    COLLECTION: ClassVar[Collection] = "alignments"
    VOCABULARY: ClassVar[tuple[str, ...]] = ALIGNMENT_NAMES
    abbreviation: str
    desc: str


class LanguageRecord(VocabularyRecord):
    COLLECTION: ClassVar[Collection] = "languages"
    VOCABULARY: ClassVar[tuple[str, ...]] = LANGUAGE_NAMES
    script: str | None = None  # Common has none of its own
    typical_speakers: tuple[str, ...] = ()
