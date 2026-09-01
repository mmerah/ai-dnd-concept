from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, EntityId, slug
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    ABILITY_POINTS,
    STARTING_ITEMS,
    TunnelGoonsCharacter,
    TunnelGoonsCharacterFile,
    player_goon,
)

STARTING_ITEM_LIST: tuple[str, ...] = (
    "Melee Weapon (specify)",
    "Ranged Weapon (specify)",
    "Piece of Armor (specify)",
    "Cloak (specify colour)",
    "Ration (specify)",
    "Torch",
    "Net",
    "Bear Trap",
    "Hammer",
    "Mirror",
    "Rope",
    "Manacles",
    "Flask",
    "Marbles",
    "Pitons",
    "Scissors",
    "Wire",
    "Flint Steel",
)

_POINT_OPTIONS: tuple[DecisionOption, ...] = tuple(
    DecisionOption(id=str(points), label=str(points)) for points in range(ABILITY_POINTS + 1)
)


def creation_steps(_picks: Picks) -> tuple[CreationStep, ...]:
    ability_steps = tuple(
        CreationStep(
            id=ability,
            prompt=f"Points in {ability.capitalize()}",
            options=_POINT_OPTIONS,
            hint=f"{ABILITY_POINTS} points across the three",
        )
        for ability in ABILITIES
    )
    item_steps = tuple(
        CreationStep(id=f"item-{n}", prompt=f"Item {n}", hint=", ".join(STARTING_ITEM_LIST))
        for n in range(1, STARTING_ITEMS + 1)
    )
    return (*ability_steps, *item_steps)


def create_character(name: str, brief: str, picks: Picks) -> TunnelGoonsCharacterFile:
    check_picks(creation_steps(picks), picks)
    payload = TunnelGoonsCharacter(
        brute=int(picked(picks, "brute")),
        skulker=int(picked(picks, "skulker")),
        erudite=int(picked(picks, "erudite")),
        items=tuple(picked(picks, f"item-{n}") for n in range(1, STARTING_ITEMS + 1)),
    )
    return TunnelGoonsCharacterFile(
        id=slug(name, ()), engine=EngineId("tunnelgoons"), name=name, brief=brief, payload=payload
    )


def preview_character(character: AnyCharacter) -> Rows:
    if not isinstance(character, TunnelGoonsCharacterFile):
        raise ValueError("Tunnel Goons received an incompatible character")
    goon = player_goon(character, EntityId("nowhere"))
    return (*goon.rows(), ("Items", ", ".join(character.payload.items)))
