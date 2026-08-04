from collections.abc import Sequence
from pathlib import Path

from aidm.base import PLAYER_ID, Entity, EntityId
from aidm.config import Settings
from aidm.content import AuthoredEntity, AuthoredWorld, Rules, compose_world
from aidm.engine import Engine
from aidm.registry import EnginePlugin
from aidm.world import GameState, WorldState

from . import bestiary, progression
from .access import read_actor, read_item
from .advancement import Dnd5eAdvancement
from .content.library import load
from .content.pack_ruleset import compile_ruleset
from .identity import ENGINE_ID
from .presentation import Dnd5ePresentation
from .ruleset import Ruleset
from .state import Dnd5eActorState, Dnd5eCharacterData, Dnd5eItemState, StatBlock
from .tools import DIRECTOR_INSTRUCTIONS, Dnd5eTools
from .ui import advancement_panel_for
from .values import Value

SHIPPED_PACK = Path(__file__).parent / "data" / "srd-2014"


def _no_location_rules(entity_id: EntityId, rules: Rules) -> None:
    if rules:
        raise ValueError(f"location {entity_id!r} carries 5e rules, but 5e defines none")


class Dnd5eConfig(Value):
    pack_paths: tuple[Path, ...] | None = None


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Engine:
    ruleset = compile_ruleset(load((SHIPPED_PACK,) if pack_paths is None else tuple(pack_paths)))
    return dnd5e_engine(ruleset)


def _validate_payloads(state: GameState, ruleset: Ruleset) -> None:
    """A foreign or malformed payload breaks here, not mid-combat."""
    actors = tuple(read_actor(state, entity.id) for entity in state.world.entities("actor"))
    for actor in actors:
        if actor.ref is not None and not ruleset.provides(actor.ref):
            raise ValueError(f"5e actor {actor.id!r} has unknown ref {actor.ref}")
    for entity in state.world.entities("item"):
        item = read_item(state, entity.id)
        if item.ref is not None and not ruleset.provides(item.ref):
            raise ValueError(f"5e item {item.id!r} has unknown ref {item.ref}")
    # `LeveledUp` names no target, so an NPC carrying progression would be ambiguous.
    levelled = sorted(
        actor.id for actor in actors if actor.progression is not None and actor.id != PLAYER_ID
    )
    if levelled:
        raise ValueError(f"only the player may have progression: {levelled}")


def dnd5e_engine(ruleset: Ruleset) -> Engine:
    presentation = Dnd5ePresentation(ruleset)
    advancement = Dnd5eAdvancement(ruleset)

    def entity_rules(authored: AuthoredEntity) -> Rules:
        match authored.entity.kind:
            case "actor":
                statted = bestiary.statted_actor(authored.entity.id, authored.rules, ruleset)
                return statted.model_dump(mode="json")
            case "item":
                statted = bestiary.statted_item(authored.entity.id, authored.rules, ruleset)
                return statted.model_dump(mode="json")
            case "location":
                _no_location_rules(authored.entity.id, authored.rules)
                return {}

    def initial_world(authored: AuthoredWorld, character: Rules) -> WorldState:
        sheet = Dnd5eCharacterData.model_validate(character)
        start = progression.first_level(sheet, ruleset)
        player = Dnd5eActorState(
            stats=StatBlock(attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain),
            progression=start.progression,
        )
        return compose_world(authored, player.model_dump(mode="json"), entity_rules)

    def validate_state(state: GameState) -> None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"5e received a {state.engine!r} game")
        for record in state.world.records.values():
            if record.entity.kind == "location":
                _no_location_rules(record.entity.id, record.rules)
        _validate_payloads(state, ruleset)

    def default_rules(entity: Entity) -> Rules:
        match entity.kind:
            case "actor":
                return Dnd5eActorState(stats=StatBlock()).model_dump(mode="json")
            case "item":
                return Dnd5eItemState().model_dump(mode="json")
            case "location":
                return {}

    return Engine(
        id=ENGINE_ID,
        initial_world=initial_world,
        validate_state=validate_state,
        default_rules=default_rules,
        advance=advancement.advance,
        advancement_available=advancement.available,
        advancement_panel=advancement_panel_for(advancement),
        director_toolset=Dnd5eTools(ruleset).toolset(),
        director_instructions=DIRECTOR_INSTRUCTIONS,
        entity_state=presentation.entity_state,
    )


def _build(config: Settings) -> Engine:
    section = Dnd5eConfig.model_validate(config.engines.get(ENGINE_ID, {}))
    return build_dnd5e_engine(section.pack_paths)


PLUGIN = EnginePlugin(id=ENGINE_ID, build=_build, badge=("D&D 5E", "red-9"))
