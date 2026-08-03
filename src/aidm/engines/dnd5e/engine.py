from collections.abc import Sequence
from pathlib import Path

from aidm.base import ActorEntity, Entity, ItemEntity, LocationEntity
from aidm.config import Settings
from aidm.content import AuthoredActor, AuthoredItem, AuthoredWorld, Rules, compose_world
from aidm.engine import Engine
from aidm.registry import EnginePlugin
from aidm.world import GameState, WorldState

from . import bestiary, progression
from .advancement import Dnd5eAdvancement
from .content.library import load
from .content.pack_ruleset import compile_ruleset
from .director import Dnd5eDirector
from .identity import ENGINE_ID
from .presentation import Dnd5ePresentation
from .rules import Dnd5eRules
from .ruleset import Ruleset
from .state import Dnd5eActorState, Dnd5eCharacterData, Dnd5eItemState, StatBlock
from .values import Value

SHIPPED_PACK = Path(__file__).parent / "data" / "srd-2014"


class Dnd5eConfig(Value):
    pack_paths: tuple[Path, ...] | None = None


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Engine:
    ruleset = compile_ruleset(load((SHIPPED_PACK,) if pack_paths is None else tuple(pack_paths)))
    return dnd5e_engine(ruleset)


def dnd5e_engine(ruleset: Ruleset) -> Engine:
    rules = Dnd5eRules(ruleset)
    director = Dnd5eDirector(rules)
    presentation = Dnd5ePresentation(ruleset)
    advancement = Dnd5eAdvancement(ruleset)

    def actor_rules(authored: AuthoredActor) -> Rules:
        statted = bestiary.statted_actor(authored.entity.id, authored.rules, ruleset)
        return statted.model_dump(mode="json")

    def item_rules(authored: AuthoredItem) -> Rules:
        statted = bestiary.statted_item(authored.entity.id, authored.rules, ruleset)
        return statted.model_dump(mode="json")

    def initial_world(authored: AuthoredWorld, character: Rules) -> WorldState:
        sheet = Dnd5eCharacterData.model_validate(character)
        start = progression.first_level(sheet, ruleset)
        player = Dnd5eActorState(
            stats=StatBlock(attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain),
            progression=start.progression,
        )
        return compose_world(authored, player.model_dump(mode="json"), actor_rules, item_rules)

    def validate_state(state: GameState) -> None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"5e received a {state.engine!r} game")
        rules.validate_state(state)

    def default_rules(entity: Entity) -> Rules:
        match entity:
            case ActorEntity():
                return Dnd5eActorState(stats=StatBlock()).model_dump(mode="json")
            case ItemEntity():
                return Dnd5eItemState().model_dump(mode="json")
            case LocationEntity():
                return {}

    return Engine(
        id=ENGINE_ID,
        initial_world=initial_world,
        validate_state=validate_state,
        default_rules=default_rules,
        resolve=rules.resolve,
        advance=advancement.advance,
        advancement_available=advancement.available,
        director_output=director.output(),
        director_instructions=director.instructions(),
        entity_state=presentation.entity_state,
        advancement=advancement,
    )


def _build(config: Settings) -> Engine:
    section = Dnd5eConfig.model_validate(config.engines.get(ENGINE_ID, {}))
    return build_dnd5e_engine(section.pack_paths)


PLUGIN = EnginePlugin(id=ENGINE_ID, build=_build, badge=("D&D 5E", "red-9"))
