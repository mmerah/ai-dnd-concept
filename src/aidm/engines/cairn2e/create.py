from collections.abc import Mapping

from pydantic import JsonValue

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.loader import Creation
from aidm.engines.packs import pack_step
from aidm.state.base import PLAYER_ID, Entity, EntityId, Trait
from aidm.state.creation import CreationOption, CreationStep, Picks, check_picks, picked

from .pack import Background, Gear, Pack, Spread


class Cairn2eCreation(Creation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        steps = [
            first,
            CreationStep(
                id="background",
                prompt="Choose a background",
                options=_options(pack.backgrounds),
            ),
        ]
        background = _picked_entry(pack.backgrounds, picks, "background")
        if background is not None and background.chooses:
            steps.append(
                CreationStep(
                    id="traits",
                    prompt=_count_prompt("quirk", background.chooses),
                    options=background.traits,
                    choose=background.chooses,
                )
            )
        steps.append(
            CreationStep(
                id="spread",
                prompt="Choose their attributes",
                options=_options(pack.spreads),
            )
        )
        return tuple(steps)

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self._packs[picked(picks, "pack")[0]]
        background = _find(pack.backgrounds, picked(picks, "background")[0])
        spread = _find(pack.spreads, picked(picks, "spread")[0])

        items = tuple(
            Entity(
                id=EntityId(gear.id),
                kind="item",
                name=gear.name,
                brief=gear.brief,
                known=True,
                parent_id=PLAYER_ID,
            )
            for gear in background.gear
        )
        invented = tuple(_find(background.traits, trait_id) for trait_id in picked(picks, "traits"))
        traits = tuple(
            Trait(id=option.id, name=option.label, text=option.detail) for option in invented
        )

        entities: dict[EntityId, dict[str, JsonValue]] = {
            EntityId(gear.id): _gear_payload(gear) for gear in background.gear
        }

        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, traits=traits, items=items),
            overlay=CharacterOverlay(
                character={
                    "background": background.label,
                    "strength": {"current": spread.strength, "maximum": spread.strength},
                    "dexterity": {"current": spread.dexterity, "maximum": spread.dexterity},
                    "willpower": {"current": spread.willpower, "maximum": spread.willpower},
                    "hp": {"current": spread.hp, "maximum": spread.hp},
                    "gold": {"current": background.gold},
                },
                entities=entities,
            ),
        )


def _gear_payload(gear: Gear) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {"slots": gear.slots}
    if gear.damage:
        payload["damage"] = gear.damage
    if gear.armor:
        payload["armor"] = gear.armor
    if gear.uses:
        payload["uses"] = {"current": gear.uses, "maximum": gear.uses}
    return payload


def _options(entries: tuple[Background, ...] | tuple[Spread, ...]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def _find[T: Background | Spread | CreationOption](entries: tuple[T, ...], chosen: str) -> T:
    return next(entry for entry in entries if entry.id == chosen)


def _picked_entry(entries: tuple[Background, ...], picks: Picks, step: str) -> Background | None:
    chosen = picked(picks, step)
    if not chosen:
        return None
    return next((entry for entry in entries if entry.id == chosen[0]), None)


def _count_prompt(what: str, count: int) -> str:
    return f"Choose one {what}" if count == 1 else f"Choose {count} {what}s"
