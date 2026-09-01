"""Maze Rats character creation and the procedural table pack it draws on."""

from collections.abc import Mapping, Sequence
from random import Random
from typing import Self

from pydantic import Field, model_validator

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, EntityId, Frozen, Slug, slug
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.mazerats.state import (
    PATHS,
    WEAPON_CLASSES,
    ActorSheet,
    InventoryItem,
    ItemSheet,
    MazeRatsCharacter,
    MazeRatsCharacterFile,
    WeaponClass,
)

_BACKGROUND_TABLES: tuple[Slug, ...] = ("civilized-npcs", "underworld-npcs", "wilderness-npcs")

_FEATURES = (
    DecisionOption(
        id="attack-bonus", label="+1 attack bonus", detail="Add 1 to every attack roll."
    ),
    DecisionOption(
        id="spell-slot", label="One spell slot", detail="Generate one spell from the Magic tables."
    ),
    DecisionOption(
        id="briarborn",
        label="Briarborn path",
        detail="Advantage on tracking, foraging, and survival.",
    ),
    DecisionOption(
        id="fingersmith",
        label="Fingersmith path",
        detail="Advantage on tinkering and picking locks or pockets.",
    ),
    DecisionOption(
        id="roofrunner",
        label="Roofrunner path",
        detail="Advantage on climbing, leaping, and balancing.",
    ),
    DecisionOption(
        id="shadowjack",
        label="Shadowjack path",
        detail="Advantage on moving silently and hiding in shadows.",
    ),
)


class Table(Frozen):
    """One Maze Rats random table, exactly as the source prints it."""

    name: str = Field(min_length=1)
    entries: tuple[str, ...] = Field(min_length=1)
    # The source's own note wherever its entry count is not the usual 36.
    note: str = ""


class SpellFormula(Frozen):
    roll: int = Field(ge=1, le=12)
    first: Slug
    second: Slug


class AbilityRow(Frozen):
    roll: int = Field(ge=1, le=6)
    strength: int = Field(ge=0, le=2)
    dexterity: int = Field(ge=0, le=2)
    will: int = Field(ge=0, le=2)


class Pack(Frozen):
    """A complete, replaceable Maze Rats table set, loaded and validated like a user pack."""

    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    tables: dict[Slug, Table] = Field(min_length=1)
    formulas: tuple[SpellFormula, ...] = Field(min_length=12, max_length=12)
    ability_rows: tuple[AbilityRow, ...] = Field(min_length=6, max_length=6)
    # Which starting items dose a wound, by entry slug: the mechanic is data, not a name reading.
    medicine_items: tuple[Slug, ...] = ()

    @model_validator(mode="after")
    def _pack_is_coherent(self) -> Self:
        if "CC BY 4.0" not in self.license.upper() and "CC-BY-4.0" not in self.license.upper():
            raise ValueError("Maze Rats packs must identify the CC BY 4.0 licence")
        if {one.roll for one in self.formulas} != set(range(1, 13)):
            raise ValueError("spell formulas must cover rolls 1 through 12 exactly once")
        named = {one.first for one in self.formulas} | {one.second for one in self.formulas}
        if missing := sorted(named - self.tables.keys()):
            raise ValueError(f"spell formula names unknown table(s): {missing}")
        if {one.roll for one in self.ability_rows} != set(range(1, 7)):
            raise ValueError("starting abilities must cover rolls 1 through 6 exactly once")
        starting = self.tables.get("starting-items")
        named = {slug(entry, ()) for entry in starting.entries} if starting else set[str]()
        if unknown := sorted(set(self.medicine_items) - named):
            raise ValueError(f"medicine names entries no starting item has: {unknown}")
        return self


def creation_steps(packs: Mapping[str, Pack], picks: Picks) -> tuple[CreationStep, ...]:
    """Return the SRD creation steps that need an answer; name, level, and XP are not among them."""
    first = CreationStep(
        id="pack", prompt="Choose a Maze Rats table set", options=pack_options(packs)
    )
    pack = packs.get(picked(picks, "pack"))
    if pack is None:
        return (first,)

    def table_options(key: Slug) -> tuple[DecisionOption, ...]:
        return _options_for(_table(pack, key).entries)

    return (
        first,
        CreationStep(
            id="abilities",
            prompt="Roll or choose your Strength, Dexterity, and Will",
            options=tuple(
                DecisionOption(
                    id=f"row-{row.roll}",
                    label=f"STR +{row.strength}, DEX +{row.dexterity}, WIL +{row.will}",
                )
                for row in pack.ability_rows
            ),
        ),
        CreationStep(id="feature", prompt="Choose one starting feature", options=_FEATURES),
        CreationStep(
            id="items",
            prompt="Roll or choose six utility items (enter six comma-separated choices)",
            hint=", ".join(_table(pack, "starting-items").entries[:6]),
        ),
        CreationStep(
            id="weapon-one",
            prompt="Choose your first weapon (light armour and a shield are automatic)",
            options=_weapon_options(pack),
        ),
        CreationStep(
            id="weapon-two", prompt="Choose your second weapon", options=_weapon_options(pack)
        ),
        CreationStep(
            id="appearance",
            prompt="Roll or create appearance",
            options=table_options("appearances"),
        ),
        CreationStep(
            id="detail",
            prompt="Roll or create physical detail",
            options=table_options("physical-details"),
        ),
        CreationStep(
            id="background",
            prompt="Roll or create background (no direct mechanical effect)",
            options=_options_for(
                tuple(entry for key in _BACKGROUND_TABLES for entry in _table(pack, key).entries)
            ),
        ),
        CreationStep(
            id="clothing", prompt="Roll or create clothing", options=table_options("clothing")
        ),
        CreationStep(
            id="personality",
            prompt="Roll or create personality",
            options=table_options("personalities"),
        ),
        CreationStep(
            id="mannerism", prompt="Roll or create mannerism", options=table_options("mannerisms")
        ),
    )


def check_creation(packs: Mapping[str, Pack], picks: Picks) -> None:
    """Validate the visible choices before the engine builds its typed character payload."""
    check_picks(creation_steps(packs, picks), picks)
    items = picked(picks, "items")
    if len([one for one in items.split(",") if one.strip()]) != 6:
        raise ValueError("items must contain exactly six comma-separated utility items")


def create_character(
    packs: Mapping[str, Pack], name: str, brief: str, picks: Picks
) -> AnyCharacter:
    """Build a typed Maze Rats character; generated spell names never come from the model."""
    check_creation(packs, picks)
    chosen = picked(picks, "pack")
    pack = packs.get(chosen)
    if pack is None:
        raise ValueError(f"the {picked(picks, 'pack')!r} table set is not installed")
    answer = picked(picks, "abilities")
    row = next((one for one in pack.ability_rows if f"row-{one.roll}" == answer), None)
    if row is None:
        raise ValueError(f"abilities has no row {answer!r}")
    feature = picked(picks, "feature")
    sheet = ActorSheet(
        strength=row.strength,
        dexterity=row.dexterity,
        will=row.will,
        attack_bonus=1 if feature == "attack-bonus" else 0,
        paths=tuple(one for one in PATHS if one == feature),
        spell_slots=(spell_name(pack, Random(f"{name}:{brief}")),)
        if feature == "spell-slot"
        else (),
    )
    return MazeRatsCharacterFile(
        id=slug(name, ()),
        engine=EngineId("mazerats"),
        name=name,
        brief=brief,
        payload=MazeRatsCharacter(
            sheet=sheet, pack=chosen, inventory=_starting_inventory(pack, picks)
        ),
    )


def preview_character(character: AnyCharacter) -> Rows:
    """Render only the public mechanical sheet during character creation."""
    if not isinstance(character, MazeRatsCharacterFile):
        raise ValueError("Maze Rats received an incompatible character")
    return character.payload.sheet.rows()


def table_entry(pack: Pack, table_id: Slug, rng: Random) -> str:
    """A uniform pick, which is what the book's group-of-six 2d read comes to."""
    entries = _table(pack, table_id).entries
    return entries[rng.randrange(len(entries))]


def spell_name(pack: Pack, rng: Random) -> str:
    """Generate a spell name from the SRD formula and two tables; effects stay a GM ruling."""
    formula = pack.formulas[rng.randint(1, 12) - 1]
    return f"{table_entry(pack, formula.first, rng)} {table_entry(pack, formula.second, rng)}"


def pack_options(packs: Mapping[str, Pack]) -> tuple[DecisionOption, ...]:
    return tuple(
        DecisionOption(id=key, label=one.name, detail=one.source) for key, one in packs.items()
    )


def _table(pack: Pack, table_id: Slug) -> Table:
    table = pack.tables.get(table_id)
    if table is None:
        raise ValueError(f"the {pack.name!r} table set has no {table_id!r} table")
    return table


def _weapon_options(pack: Pack) -> tuple[DecisionOption, ...]:
    return tuple(
        DecisionOption(
            id=kind,
            label=_table(pack, f"{kind}-weapons").name,
            detail=", ".join(_table(pack, f"{kind}-weapons").entries),
        )
        for kind in WEAPON_CLASSES
    )


def _options_for(entries: Sequence[str]) -> tuple[DecisionOption, ...]:
    used: set[str] = set()
    options: list[DecisionOption] = []
    for entry in entries:
        entry_id = slug(entry, used)
        used.add(entry_id)
        options.append(DecisionOption(id=entry_id, label=entry))
    return tuple(options)


def _starting_inventory(pack: Pack, picks: Picks) -> tuple[InventoryItem, ...]:
    used: set[str] = set()
    items = [
        _item(name.strip(), ItemSheet(medicine=slug(name, ()) in pack.medicine_items), used)
        for name in picked(picks, "items").split(",")
    ]
    items.append(_item("Light armour", ItemSheet(armour="light", position="worn"), used))
    items.append(_item("Shield", ItemSheet(shield=True, position="hands"), used))
    held = False
    for weapon in _weapons(picks):
        # The shield already fills one hand, so only a single light weapon can be held.
        position = "hands" if weapon == "light" and not held else "belt"
        held = held or position == "hands"
        items.append(
            _item(
                f"{weapon.capitalize()} weapon", ItemSheet(weapon=weapon, position=position), used
            )
        )
    return tuple(items)


def _weapons(picks: Picks) -> tuple[WeaponClass, ...]:
    chosen: tuple[WeaponClass, ...] = tuple(
        one
        for step in ("weapon-one", "weapon-two")
        for one in WEAPON_CLASSES
        if one == picked(picks, step)
    )
    if len(chosen) != 2:
        raise ValueError("both weapons must be light, heavy, or ranged")
    return chosen


def _item(name: str, sheet: ItemSheet, used: set[str]) -> InventoryItem:
    item_id = slug(name, used)
    used.add(item_id)
    return InventoryItem(id=EntityId(item_id), name=name, sheet=sheet)
