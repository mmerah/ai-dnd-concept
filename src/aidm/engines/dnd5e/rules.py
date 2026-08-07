from pathlib import Path

from aidm.engines.loader import ActionSpec, EnginePlugin
from aidm.state.base import EngineId
from aidm.state.packs import Record

from .actions import CONTESTED, UNCONTESTED, Attack, CastSpell, Check, Improvise, Rest, UseFeature
from .advance import check_delta, offered
from .records import (
    AlignmentRecord,
    ArmorRecord,
    BackgroundRecord,
    ClassRecord,
    FeatRecord,
    FeatureRecord,
    GearRecord,
    LanguageRecord,
    LevelRecord,
    MagicItemRecord,
    MonsterRecord,
    ProficiencyRecord,
    RaceRecord,
    SkillRecord,
    SpellRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
    VehicleRecord,
    WeaponRecord,
)
from .resolve import (
    cast_labels,
    check_cast,
    check_feature,
    improvise_labels,
    resolve_attack,
    resolve_cast,
    resolve_check,
    resolve_feature,
    resolve_improvise,
    resolve_rest,
)

ENGINE_ID: EngineId = EngineId("dnd5e")

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("D&D 5E", "red-9"),
    engine_dir=Path(__file__).parent,
    actions=(
        ActionSpec(model=Attack, labels=CONTESTED, resolve=resolve_attack),
        ActionSpec(model=CastSpell, labels=cast_labels, resolve=resolve_cast, check=check_cast),
        ActionSpec(model=Check, labels=CONTESTED, resolve=resolve_check),
        ActionSpec(
            model=UseFeature, labels=UNCONTESTED, resolve=resolve_feature, check=check_feature
        ),
        ActionSpec(model=Rest, labels=UNCONTESTED, resolve=resolve_rest),
        ActionSpec(model=Improvise, labels=improvise_labels, resolve=resolve_improvise),
    ),
    action_doc="The one action this turn resolves, or null when nothing needs resolving.",
    offered=offered,
    check_delta=check_delta,
    record_types={
        "spells": SpellRecord,
        "weapons": WeaponRecord,
        "armor": ArmorRecord,
        "gear": GearRecord,
        "tools": GearRecord,
        "vehicles": VehicleRecord,
        "classes": ClassRecord,
        "races": RaceRecord,
        "backgrounds": BackgroundRecord,
        "skills": SkillRecord,
        "magic_items": MagicItemRecord,
        "subraces": SubraceRecord,
        "subclasses": SubclassRecord,
        "features": FeatureRecord,
        "traits": TraitRecord,
        "levels": LevelRecord,
        "monsters": MonsterRecord,
        "conditions": Record,
        "languages": LanguageRecord,
        "alignments": AlignmentRecord,
        "feats": FeatRecord,
        "proficiencies": ProficiencyRecord,
    },
)
