from collections.abc import Sequence
from pathlib import Path

from aidm.core.config import Settings
from aidm.core.engine import Engine
from aidm.core.enginepack import load_engine
from aidm.core.packs import Value
from aidm.core.registry import EnginePlugin
from aidm.core.sheet import Sheet

from .actions import Dnd5ePlan
from .advance import check, offered
from .identity import ENGINE_ID
from .resolve import check_plan, resolve_action

ENGINE_DIR = Path(__file__).parent


class Dnd5eConfig(Value):
    pack_paths: tuple[Path, ...] | None = None


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Engine[Sheet]:
    return load_engine(
        ENGINE_DIR,
        ENGINE_ID,
        pack_paths,
        offered=offered,
        check=check,
        plan_type=Dnd5ePlan,
        check_plan=check_plan,
        resolve_action=resolve_action,
    )


def _build(config: Settings) -> Engine[Sheet]:
    section = Dnd5eConfig.model_validate(config.engines.get(ENGINE_ID, {}))
    return build_dnd5e_engine(section.pack_paths)


PLUGIN = EnginePlugin(id=ENGINE_ID, build=_build, badge=("D&D 5E", "red-9"))
