"""The 5e-database schema, as far as this pack projects it: what every family shares.

Tolerant of the 493 fields it does not read, and strict about the ones it does — a closed vocabulary
is narrowed *here*, at the boundary that read it, so a 14th damage type fails with the offending
value named rather than being narrowed later by a hand-written `match` per vocabulary."""

from pydantic import BaseModel, ConfigDict, Field

from aidm.engines.dnd5e.content.vocabulary import (
    ConditionName,
    DamageType,
    EquipmentCategory,
    MagicSchool,
    WeaponProperty,
)


class Upstream(BaseModel):
    """Tolerant of the fields we do not project, strict about the ones we do."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class ApiRef(Upstream):
    index: str


# Upstream is where a closed vocabulary is checked: a 14th damage type or a 16th condition must
# fail at the boundary that read it, with the offending value named, rather than be narrowed later
# by a hand-written `match` per vocabulary.
class DamageTypeRef(Upstream):
    index: DamageType


class SchoolRef(Upstream):
    index: MagicSchool


class ConditionRef(Upstream):
    index: ConditionName


class CategoryRef(Upstream):
    index: EquipmentCategory


class PropertyRef(Upstream):
    index: WeaponProperty


class NamedRef(ApiRef):
    """A reference whose name is read too, because a choice's options are shown to the player."""

    name: str


class Damage(Upstream):
    """Either dice of one type, or a `choose` between options."""

    damage_dice: str | None = None
    damage_type: DamageTypeRef | None = None
    options: "DamageOptions | None" = Field(default=None, alias="from")


class DamageOptions(Upstream):
    options: list[Damage]


Damage.model_rebuild()
