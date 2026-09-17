"""Converts one SRD adventure-pack markdown page into a Loner pack JSON file.

Run as `uv run python scripts/srd_packs.py <APnn_name.md>...`.
"""

import re
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aidm.core.entities import Refusal, Slug, parse, slug
from aidm.core.play import DecisionOption
from aidm.engines.loner3e.worldsmith import Loner3eBlock, Loner3ePack
from aidm.engines.packs import Location, Names

PACKS_DIR = Path(__file__).resolve().parent.parent / "src/aidm/engines/loner3e/packs"
SOURCE_TEMPLATE = "https://lonersrd.zotiquestgames.com/adventure_packs/{stem}.html"
LICENSE_TEMPLATE = (
    "Adventure Pack {number}: {title}, Loner SRD site (CC BY-SA 4.0), "
    "(c) Roberto Bisceglie / Zotiquest Games"
)
TITLE_SUFFIX = " Adventure Pack"
RULE_SUBSECTION_LEVELS = (3, 4)
BLOCK_LEVEL = 3
GRID_SIZE = 6
SPLIT_KEYS = ("Skills", "Frailty", "Frailties", "Gear")
KNOWN_FIELD_KEYS = (
    "Concept",
    "Skills",
    "Frailty",
    "Frailties",
    "Gear",
    "Goal",
    "Motive",
    "Nemesis",
)
MONSTER_SECTIONS = (
    "Monsters",
    "Hostile Entities",
    "Creatures",
    "Villains",
    "Opponents",
    "Persons of Interest",
    "Field Threats",
    "Threat Actors",
    "Denizens of the Wastes",
    "Wild Encounters",
    "Frontier Threats",
)
NICKNAME_LISTS = (
    "Nicknames",
    "Codenames / Call Signs",
    "Superhero Names",
    "Epithets or Reputation",
)
NUMBERED_FIRST_CELLS = ("D66", "")  # a die number or a grid row number, not a value to keep
SECTION_LEVELS = (1, 2)  # AP04 writes `# Locations` where every other page writes `## Locations`
TRAIT_TABLE_LEVELS = (3,)
NAME_LIST_LEVELS = (3, 4)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
FIELD_LINE_PATTERN = re.compile(r"^[-*]\s+\*\*(\w+):?\*\*:?\s*(.*)$")
STEM_PATTERN = re.compile(r"^AP(\d+)_")
RULE_BLANK_RUN = re.compile(r"\n{3,}")
# Bold and colons vary: `Possible encounters:`, `**Encounters**:`, `**Possible Encounter:**`
ENCOUNTERS_LINE = re.compile(r"^(\*\*)?(possible )?encounters?(:\*\*|\*\*:|:)\s*", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    title: str
    index: int


def convert(markdown: str, stem: str) -> Loner3ePack:
    lines = markdown.splitlines()
    headings = _headings(lines)
    number = _stem_number(stem)
    title = _title(headings)
    rules = _rules(headings, lines)
    data: dict[str, object] = {
        "name": f"AP{number} {title}",
        "source": SOURCE_TEMPLATE.format(stem=stem),
        "license": LICENSE_TEMPLATE.format(number=number, title=title),
        "setting": _setting(headings, lines),
        "names": _names(headings, lines),
        "rules": rules,
        "locations": _locations(headings, lines),
        "seeds": _seeds(headings, lines),
        "concepts": _trait_table(headings, lines, "Concepts"),
        "skills": _trait_table(headings, lines, "Skills"),
        "frailties": _trait_table(headings, lines, "Frailties"),
        "gear": _trait_table(headings, lines, "Gear"),
        "spends_luck": "Luck cost" in rules,
        "factions": _blocks(headings, lines, "Factions"),
        "npcs": _blocks(headings, lines, "NPCs"),
        "monsters": _blocks(headings, lines, *MONSTER_SECTIONS),
    }
    return parse(Loner3ePack, data)


def dump(pack: Loner3ePack) -> str:
    return pack.model_dump_json(indent=2) + "\n"


def main() -> None:
    for raw_path in sys.argv[1:]:
        path = Path(raw_path)
        stem = path.stem
        pack = convert(path.read_text(encoding="utf-8"), stem)
        output = PACKS_DIR / f"{stem.lower().replace('_', '-')}.json"
        output.write_text(dump(pack), encoding="utf-8")


def _headings(lines: Sequence[str]) -> list[Heading]:
    found: list[Heading] = []
    for index, line in enumerate(lines):
        if match := HEADING_PATTERN.match(line):
            found.append(Heading(len(match.group(1)), _clean_heading(match.group(2)), index))
    return found


def _clean_heading(text: str) -> str:
    cleaned = text.rstrip()
    if cleaned.startswith("**") and cleaned.endswith("**") and len(cleaned) >= 4:
        cleaned = cleaned[2:-2]
    return cleaned.strip()


def _stem_number(stem: str) -> str:
    if not (match := STEM_PATTERN.match(stem)):
        raise Refusal(f"{stem!r} is not an APnn_name stem")
    return match.group(1)


def _title(headings: Sequence[Heading]) -> str:
    top = next((heading for heading in headings if heading.level == 1), None)
    if top is None:
        raise Refusal("no top-level heading names the pack")
    return top.title.removesuffix(TITLE_SUFFIX)


def _find(
    headings: Sequence[Heading], lines: Sequence[str], *titles: str, levels: tuple[int, ...]
) -> int:
    index = _found(headings, lines, *titles, levels=levels)
    if index is None:
        raise Refusal(f"no heading among {titles!r} has a body")
    return index


def _found(
    headings: Sequence[Heading], lines: Sequence[str], *titles: str, levels: tuple[int, ...]
) -> int | None:
    """AP09 prints `## Adventure Seeds` twice, the first empty, so an empty body is skipped."""
    for index, heading in enumerate(headings):
        if heading.title not in titles or heading.level not in levels:
            continue
        if any(line.strip() for line in _body(headings, lines, index)):
            return index
    return None


def _section_range(headings: Sequence[Heading], index: int, total_lines: int) -> tuple[int, int]:
    """The body's (start, end) line bounds: end is the next heading no deeper than this one.

    A level-1 section still ends at the next `##`, since AP04 writes `# Locations`.
    """
    level = max(headings[index].level, 2)
    start = headings[index].index + 1
    for other in headings[index + 1 :]:
        if other.level <= level:
            return start, other.index
    return start, total_lines


def _body(headings: Sequence[Heading], lines: Sequence[str], index: int) -> list[str]:
    start, end = _section_range(headings, index, len(lines))
    return list(lines[start:end])


def _nested(headings: Sequence[Heading], lines: Sequence[str], index: int, level: int) -> list[int]:
    start, end = _section_range(headings, index, len(lines))
    return [
        other_index
        for other_index, heading in enumerate(headings)
        if heading.level == level and start <= heading.index < end
    ]


def _row_cells(line: str) -> list[str]:
    trimmed = line.strip().removeprefix("|").removesuffix("|")
    return [cell.strip() for cell in trimmed.split("|")]


def _grid(body: Sequence[str], title: str) -> list[list[str]]:
    rows = [line for line in body if line.strip().startswith("|")][2:]
    grid = [_row_cells(row)[1 : GRID_SIZE + 1] for row in rows]
    if len(grid) != GRID_SIZE or any(sum(1 for cell in row if cell) < GRID_SIZE for row in grid):
        raise Refusal(f"{title!r} is not a 6x6 table")
    return grid


def _folded(label: str) -> str:
    decomposed = unicodedata.normalize("NFKD", label)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _bullet(line: str) -> str:
    stripped = line.strip()
    return stripped[2:] if stripped[:2] in ("- ", "* ") else ""


def _unbulleted(line: str) -> str:
    """The line's text, bullet marker or not: AP03 writes a location as a paragraph."""
    return _bullet(line).strip() or line.strip()


def _setting(headings: Sequence[Heading], lines: Sequence[str]) -> str:
    index = _find(headings, lines, "Setting Information", levels=SECTION_LEVELS)
    paragraphs = [content for line in _body(headings, lines, index) if (content := _bullet(line))]
    return "\n".join(paragraphs)


def _trait_table(
    headings: Sequence[Heading], lines: Sequence[str], title: str
) -> tuple[DecisionOption, ...]:
    index = _find(headings, lines, title, levels=TRAIT_TABLE_LEVELS)
    taken: list[Slug] = []
    options: list[DecisionOption] = []
    for row in _grid(_body(headings, lines, index), headings[index].title):
        for cell in row:
            option_id = slug(_folded(cell), taken)
            taken.append(option_id)
            options.append(DecisionOption(id=option_id, label=cell, detail=""))
    return tuple(options)


def _name_list(headings: Sequence[Heading], lines: Sequence[str], *titles: str) -> tuple[str, ...]:
    return _name_grid(headings, lines, _find(headings, lines, *titles, levels=NAME_LIST_LEVELS))


def _optional_name_list(
    headings: Sequence[Heading], lines: Sequence[str], *titles: str
) -> tuple[str, ...]:
    """A page that prints none of these headings has no such list."""
    index = _found(headings, lines, *titles, levels=NAME_LIST_LEVELS)
    return () if index is None else _name_grid(headings, lines, index)


def _name_grid(headings: Sequence[Heading], lines: Sequence[str], index: int) -> tuple[str, ...]:
    return tuple(
        cell for row in _grid(_body(headings, lines, index), headings[index].title) for cell in row
    )


def _names(headings: Sequence[Heading], lines: Sequence[str]) -> Names:
    return Names(
        female=_name_list(headings, lines, "Female Names"),
        male=_name_list(headings, lines, "Male Names"),
        neutral=_optional_name_list(headings, lines, "Neutral Names"),
        surnames=_name_list(headings, lines, "Surnames"),
        nicknames=_optional_name_list(headings, lines, *NICKNAME_LISTS),
    )


def _fields(body: Sequence[str], title: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in body:
        if match := FIELD_LINE_PATTERN.match(raw.rstrip()):
            key = match.group(1)
            if key not in KNOWN_FIELD_KEYS:
                raise Refusal(f"{title}: unknown field {key!r}")
            fields[key] = match.group(2).strip()
    return fields


def _block(headings: Sequence[Heading], lines: Sequence[str], index: int) -> Loner3eBlock:
    title = headings[index].title
    fields = _fields(_body(headings, lines, index), title)
    data: dict[str, object] = {"name": title, "concept": fields.get("Concept", "")}
    for key in SPLIT_KEYS:
        if key in fields:
            attribute = "frailties" if key in ("Frailty", "Frailties") else key.lower()
            data[attribute] = tuple(fields[key].split(", "))
    for key in ("Goal", "Motive", "Nemesis"):
        if key in fields:
            data[key.lower()] = fields[key]
    try:
        return parse(Loner3eBlock, data)
    except Refusal as refusal:
        raise Refusal(f"{title}: {refusal}") from refusal


def _blocks(
    headings: Sequence[Heading], lines: Sequence[str], *titles: str
) -> tuple[Loner3eBlock, ...]:
    section = _find(headings, lines, *titles, levels=SECTION_LEVELS)
    return tuple(
        _block(headings, lines, child) for child in _nested(headings, lines, section, BLOCK_LEVEL)
    )


def _location(headings: Sequence[Heading], lines: Sequence[str], index: int) -> Location:
    """A body runs as detail until an encounters line; everything after it names encounters."""
    detail_parts: list[str] = []
    encounter_parts: list[str] = []
    reached_encounters = False
    for raw in _body(headings, lines, index):
        content = _unbulleted(raw)
        if not content:
            continue
        if match := ENCOUNTERS_LINE.match(content):
            reached_encounters = True
            content = content[match.end() :]
        if content:
            (encounter_parts if reached_encounters else detail_parts).append(content)
    return Location(
        label=headings[index].title,
        detail=" ".join(detail_parts),
        encounters="; ".join(encounter_parts),
    )


def _locations(headings: Sequence[Heading], lines: Sequence[str]) -> tuple[Location, ...]:
    section = _find(headings, lines, "Locations", levels=SECTION_LEVELS)
    return tuple(
        _location(headings, lines, child)
        for child in _nested(headings, lines, section, BLOCK_LEVEL)
    )


def _seeds(headings: Sequence[Heading], lines: Sequence[str]) -> tuple[str, ...]:
    title = "Adventure Seeds"
    index = _find(headings, lines, title, levels=SECTION_LEVELS)
    rows = [line for line in _body(headings, lines, index) if line.strip().startswith("|")][2:]
    seeds: list[str] = []
    for row in rows:
        cells = _row_cells(row)
        if len(cells) < 2:
            raise Refusal(f"seed row {row!r} has no adventure cell")
        seeds.append(cells[1])
    if not seeds:
        raise Refusal(f"{title!r} has no seed rows")
    return tuple(seeds)


def _consume_rule_table(body: Sequence[str], start: int, out: list[str]) -> int:
    numbered = _row_cells(body[start])[0] in NUMBERED_FIRST_CELLS
    i = start + 2  # skip the header row and the separator row
    while i < len(body) and body[i].strip().startswith("|"):
        cells = _row_cells(body[i])
        if rest := ", ".join(cell for cell in cells[1:] if cell):
            out.append(f"- {rest}" if numbered else f"- {cells[0]}: {rest}")
        i += 1
    return i


def _rule_logical_lines(body: Sequence[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(body):
        raw = body[i].rstrip()
        stripped = raw.strip()
        if not stripped:
            out.append("")
            i += 1
            continue
        if (match := HEADING_PATTERN.match(raw)) and len(match.group(1)) in RULE_SUBSECTION_LEVELS:
            out.append(f"{_clean_heading(match.group(2))}:")
            i += 1
            continue
        if stripped.startswith("|"):
            i = _consume_rule_table(body, i, out)
            continue
        out.append(stripped)
        i += 1
    return out


def _rules(headings: Sequence[Heading], lines: Sequence[str]) -> str:
    sections = [
        RULE_BLANK_RUN.sub(
            "\n\n", "\n".join(_rule_logical_lines(_body(headings, lines, index)))
        ).strip()
        for index, heading in enumerate(headings)
        if heading.level == 2 and heading.title.startswith("Special Rule")
    ]
    return "\n\n".join(section for section in sections if section)


if __name__ == "__main__":
    main()
