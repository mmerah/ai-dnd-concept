from pathlib import Path

from aidm.engines.loader import EnginePlugin
from aidm.state.base import EngineId
from aidm.state.packs import Record

from .actions import Dnd5ePlan
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
from .resolve import check_plan, resolve_action

ENGINE_ID: EngineId = EngineId("dnd5e")

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("D&D 5E", "red-9"),
    engine_dir=Path(__file__).parent,
    plan_type=Dnd5ePlan,
    check_plan=check_plan,
    resolve_action=resolve_action,
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
