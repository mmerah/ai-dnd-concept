from typing import Literal, cast, get_args

from aidm.core.packs import Value

Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

ABILITIES: tuple[Ability, ...] = get_args(Ability)


class Attributes(Value):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    def __getitem__(self, ability: Ability) -> int:
        return cast(int, getattr(self, ability))


assert set(ABILITIES) <= set(Attributes.model_fields), "an Ability has no Attributes field"
