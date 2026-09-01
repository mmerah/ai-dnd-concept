"""One-off: the pack is vendored, its source is not, so this records how srd.json was built from https://rules.moddable.games/games/maze-rats/data/."""

import json
import sys
from pathlib import Path
from typing import Any

OUT = Path(__file__).parents[1] / "src/aidm/engines/mazerats/packs/srd.json"
SOURCE = "https://rules.moddable.games/games/maze-rats/data/"
CREATION_NOTE = (
    "Printed as a prose list on the Maze Rats character-creation page, not as a data table; "
    "entries capitalized to match the other tables."
)
POINTER_NOTE = "The source's pointer table: each entry names the table(s) to roll on next."

# Step 4 of the character-creation page, transcribed in printed order.
STARTING_ITEMS = (
    "Animal scent, bear trap, bedroll, caltrops, chain (10 ft.), chalk, iron tongs, "
    "lantern and oil, large sack, lockpicks (3), manacles, medicine (3), chisel, crowbar, "
    "fishing net, glass marbles, glue, grappling hook, metal file, rations (3), rope (50 ft.), "
    "steel wire, shovel, steel mirror, grease, hacksaw, hammer, hand drill, horn, iron spikes, "
    "ten foot pole, tinderbox, torch, vial of acid, vial of poison, waterskin"
)

# The one starting item the rules give a mechanic: "a dose of medicine restores 1 point of health".
MEDICINE_ITEMS = ["medicine-3"]

# Step 5 of the same page: open example lists, not 36-entry tables.
WEAPONS = {
    "light-weapons": (
        "Light Weapons (1 hand)",
        "axes, daggers, maces, short swords, flails, one-handed spears",
    ),
    "heavy-weapons": (
        "Heavy Weapons (+1 damage, 2 hands)",
        "spears, halberds, long swords, warhammers",
    ),
    "ranged-weapons": ("Ranged Weapons (2 hands)", "bows, crossbows, slings"),
}

# Step 1 of the same page.
ABILITY_ROWS = (
    (1, 2, 1, 0),
    (2, 2, 0, 1),
    (3, 1, 2, 0),
    (4, 0, 2, 1),
    (5, 1, 0, 2),
    (6, 0, 1, 2),
)


def main() -> None:
    source_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mrsrd/mrdata")
    tables: dict[str, dict[str, object]] = {}
    formulas: list[dict[str, object]] = []
    licence = attribution = ""
    for path in sorted(source_dir.glob("*.json")):
        book: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        licence, attribution = book["licence"], book["attribution"]
        for table in book["tables"]:
            if table["id"] == "spells":
                formulas = [
                    {"roll": one["roll"], "first": one["formula"][0], "second": one["formula"][1]}
                    for one in table["entries"]
                ]
                continue
            tables[table["id"]] = _table(table)
    for key, (name, printed) in WEAPONS.items():
        tables[key] = {"name": name, "entries": _split(printed), "note": CREATION_NOTE}
    tables["starting-items"] = {
        "name": "Starting Items",
        "entries": _split(STARTING_ITEMS),
        "note": CREATION_NOTE,
    }
    pack = {
        "name": "Maze Rats SRD tables",
        "source": f"Maze Rats by Ben Milton, machine-readable tables from {SOURCE}",
        "license": licence,
        "attribution": attribution,
        "tables": tables,
        "formulas": formulas,
        "ability_rows": [
            {"roll": roll, "strength": strength, "dexterity": dexterity, "will": will}
            for roll, strength, dexterity, will in ABILITY_ROWS
        ],
        "medicine_items": MEDICINE_ITEMS,
    }
    OUT.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(tables)} tables, {len(formulas)} formulas")


def _table(table: dict[str, Any]) -> dict[str, object]:
    entries = table["entries"]
    if entries and isinstance(entries[0], dict):
        return {
            "name": table["name"],
            "entries": [one["result"] for one in entries],
            "note": POINTER_NOTE,
        }
    return {"name": table["name"], "entries": entries, "note": table.get("count_note", "")}


def _split(printed: str) -> list[str]:
    return [one.strip().capitalize() for one in printed.split(",")]


if __name__ == "__main__":
    main()
