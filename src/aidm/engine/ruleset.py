"""What `engine/` asks of content, stated as profiles rather than records.

A record is the *storage* shape: cumulative level snapshots, a proficiency naming an equipment
category, a 28-field monster. The engine reads these instead — the numbers a rule needs, already
derived — so it never navigates a pack. `pack_ruleset.py` compiles one from loaded packs, and a test
can hand over twenty lines of its own, which is what nothing before this could do.

Protocols rather than one class, so a function's parameter says which half of the ruleset it reads.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from ..content import ContentRef
from ..content.records import ProgressionChoice, Slug
from ..domain.models import Ability, Origin, StatBlock
from ..utils import dice
from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap


class CharacterProfile(Frozen):
    """What a class, a race and a background make of a character, whatever level they reach: these
    are settled at level 1 and never revisited."""

    hit_die: int = Field(ge=1)
    saving_throws: tuple[Ability, ...]
    # Held without choosing; `choices` are what the player answers instead. Save proficiencies are
    # absent — `saving_throws` is the one field `rules.save_bonus` reads.
    proficiencies: tuple[Slug, ...] = ()
    ability_bonuses: FrozenMap[Ability, int] = EMPTY_FROZEN_MAP
    choices: tuple[ProgressionChoice, ...] = ()


class LevelProfile(Frozen):
    """One level, as the delta the pack states as a total: `improvements` is the difference between
    two cumulative records, taken here so no consumer can double-count by applying one whole."""

    prof_bonus: int = Field(ge=2)
    improvements: int = Field(ge=0)
    spell_slots: FrozenMap[int, int] = EMPTY_FROZEN_MAP
    choices: tuple[ProgressionChoice, ...] = ()
    # The class offers a subclass at this level. Whether it is still open is progression's to say,
    # because a subclass is chosen once and never unchosen.
    subclass_choice: ProgressionChoice | None = None


class AttackProfile(Frozen):
    """One attack, resolved: what to add to the d20, and everything a hit rolls. `damage` is `None`
    for an attack that deals none — the net restrains and nothing else."""

    name: str
    to_hit: int
    damage: dice.SelfContainedDice | None = None


class WeaponProfile(Frozen):
    """A weapon as the rules read it. The dice belong to the weapon; the ability modifier and the
    proficiency bonus belong to whoever swings it, so neither is here."""

    index: Slug
    damage: dice.DiceExpr | None = None
    ranged: bool = False
    finesse: bool = False


class ArchetypeProfile(Frozen):
    """An actor backed by content: the numbers a live entity is stamped from at creation, and what
    it can do. Everything descriptive stays in the pack."""

    stats: StatBlock
    attacks: tuple[AttackProfile, ...] = ()


class ArchetypeRules(Protocol):
    """Composing a world out of refs: what an entity may be filled in from, and whether a ref is
    backed at all — a lantern names a record no rule reads, and still must exist."""

    def archetype(self, ref: ContentRef) -> ArchetypeProfile | None: ...
    def provides(self, ref: ContentRef) -> bool: ...


class CombatRules(ArchetypeRules, Protocol):
    """Resolving a swing. An archetype attacks with its own actions, anyone else with what they
    carry, which is why both halves are one protocol."""

    def weapon(self, ref: ContentRef) -> WeaponProfile | None: ...

    def proficient(self, origin: Origin, held: Sequence[Slug], equipment: Slug) -> bool:
        """Whether any proficiency held covers this equipment. `origin` says which pack wrote the
        slugs: an index alone addresses nothing."""
        ...


class ProgressionRules(Protocol):
    """Levelling. Two questions, because a character is what their origin gives them plus what each
    level adds — and a synthetic answer to both is a test's whole ruleset."""

    def character(self, origin: Origin) -> CharacterProfile: ...
    def level(self, origin: Origin, level: int) -> LevelProfile: ...


class Ruleset(ProgressionRules, CombatRules, Protocol):
    """Every question the engine asks of content, as one injected value."""
