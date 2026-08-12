from collections.abc import Mapping

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.loader import Creation
from aidm.state.base import Slug, Trait
from aidm.state.creation import CreationOption, CreationStep, Picks, check_picks

# Authored spreads keep creation at pick-from-options; free point allocation would need a
# numeric step type, which is the deliberate ceiling of this workflow.
_SPREADS: Mapping[Slug, Mapping[str, int]] = {
    "daring": {"bold": 2, "subtle": 1, "clever": 1, "empathetic": 0},
    "sly": {"subtle": 2, "clever": 1, "empathetic": 1, "bold": 0},
    "keen": {"clever": 2, "subtle": 1, "bold": 1, "empathetic": 0},
    "warm": {"empathetic": 2, "bold": 1, "clever": 1, "subtle": 0},
}

_EDGES: Mapping[Slug, Trait] = {
    "silver-tongued": Trait(
        id="silver-tongued",
        name="Silver-Tongued",
        text="(edge) Words open doors that force cannot.",
    ),
    "old-soldier": Trait(
        id="old-soldier",
        name="Old Soldier",
        text="(edge) Drilled instincts read a fight before it starts.",
    ),
    "sharp-eyed": Trait(
        id="sharp-eyed",
        name="Sharp-Eyed",
        text="(edge) Small details out of place never go unnoticed.",
    ),
    "sure-footed": Trait(
        id="sure-footed",
        name="Sure-Footed",
        text="(edge) Ledges, rigging, and rooftops feel like level ground.",
    ),
}

_BURDENS: Mapping[Slug, Trait] = {
    "haunted": Trait(
        id="haunted",
        name="Haunted",
        text="(burden) A death they witnessed follows them into quiet moments.",
    ),
    "hunted": Trait(
        id="hunted",
        name="Hunted",
        text="(burden) Someone with reach wants them found.",
    ),
    "debt-bound": Trait(
        id="debt-bound",
        name="Debt-Bound",
        text="(burden) An old promise can be called in at the worst time.",
    ),
    "soft-hearted": Trait(
        id="soft-hearted",
        name="Soft-Hearted",
        text="(burden) They cannot walk past someone in need, whatever it costs.",
    ),
}


def _trait_options(traits: Mapping[Slug, Trait]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=key, label=trait.name, detail=trait.text) for key, trait in traits.items()
    )


_STEPS = (
    CreationStep(
        id="archetype",
        prompt="Choose an archetype",
        options=tuple(
            CreationOption(
                id=key,
                label=key.capitalize(),
                detail=", ".join(f"{name} {value}" for name, value in spread.items()),
            )
            for key, spread in _SPREADS.items()
        ),
    ),
    CreationStep(id="edge", prompt="Choose an edge", options=_trait_options(_EDGES)),
    CreationStep(id="burden", prompt="Choose a burden", options=_trait_options(_BURDENS)),
)


class StoryCreation(Creation):
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        del picks  # every story step is static
        return _STEPS

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(_STEPS, picks)
        return CreatedCharacter(
            profile=CharacterProfile(
                name=name,
                brief=brief,
                traits=(_EDGES[picks["edge"][0]], _BURDENS[picks["burden"][0]]),
            ),
            overlay=CharacterOverlay(character=dict(_SPREADS[picks["archetype"][0]])),
        )
