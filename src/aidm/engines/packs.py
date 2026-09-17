import logging
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, cast, get_origin

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import EngineId, Frozen, Refusal, Slug, content_id, parse, slug
from aidm.core.io import read_model
from aidm.core.model import PackSelection
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, section_if, sections

LOGGER = logging.getLogger(__name__)

DASH = " — "  # `Label — detail` in a table line; nowhere inside a label or a detail
SEPARATOR = ", "  # how a list reads inside a block line; nowhere inside an item
PROSE_ROWS = 8
NAME_ROWS = 4
LIST_ROWS = 14
NAME_LABELS: Mapping[Slug, str] = {
    "female": "Female names",
    "male": "Male names",
    "neutral": "Neutral names",
    "surnames": "Surnames",
    "nicknames": "Nicknames",
}
SRD_PACK: Slug = "srd"
MAX_SUPPLEMENTS = 2  # two packs in play beside the source fill the worldsmith's command line
SOURCE_BOUND = (
    "Everything comes from SOURCE MATERIAL, its premise and, when it holds one, its document; "
    "nothing outside it."
)
HEAD_ASK = (
    "Write the head of a pack for this setting. A pack is a genre kit the worldsmith reads when "
    "it writes scenarios in this setting. `setting` is a few paragraphs on what this world is "
    "and what a story in it is about. The creation tables are the labels a player picks from, "
    "each with a one-line `detail` only where the label does not explain itself. The name lists "
    "fit the setting, six to twelve each, and a list is left empty when the setting has no such "
    "names. `rules` is the genre's one special rule as prose, if it has one, else empty. "
    f"{SOURCE_BOUND}"
)
BODY_ASK = (
    "Write the rest of the pack. THE PACK SO FAR is the head, and everything here belongs to "
    "that setting. The cast blocks are written to be met, so write each one whole enough to be "
    "filed into a scene's cast as it stands. Locations say what is found there and who may be "
    "met there. Seeds are one-line adventure premises a player could start a scenario from. "
    f"{SOURCE_BOUND}"
)


class Names(Frozen):
    female: tuple[str, ...] = ()
    male: tuple[str, ...] = ()
    neutral: tuple[str, ...] = ()
    surnames: tuple[str, ...] = ()
    nicknames: tuple[str, ...] = ()

    @property
    def listed(self) -> tuple[tuple[Slug, tuple[str, ...]], ...]:
        return (
            ("female", self.female),
            ("male", self.male),
            ("neutral", self.neutral),
            ("surnames", self.surnames),
            ("nicknames", self.nicknames),
        )

    @model_validator(mode="after")
    def _every_name_reads_in_a_list(self) -> Self:
        for kind, values in self.listed:
            check_items(kind, values)
        return self


class Labelled(Frozen):
    """One row of a creation table as the worldsmith writes it, before code makes its id."""

    label: str = Field(min_length=1, max_length=60)
    detail: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _reads_as_one_table_line(self) -> Self:
        check_lines("a table entry", (self.label, self.detail))
        if DASH in self.label or DASH in self.detail:
            raise ValueError(f'a table entry holds "{DASH}", which parts a label from its detail')
        return self


class Location(Frozen):
    label: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    encounters: str = ""  # the SRD's "Possible encounters" line, names the worldsmith may use

    @model_validator(mode="after")
    def _reads_in_a_block(self) -> Self:
        check_lines("a location", (self.label, self.detail, self.encounters))
        return self


class EditField(Frozen):
    """One textarea on the pack page: what it is called, what it holds, how tall it stands."""

    id: Slug
    label: str
    text: str
    rows: int


class Pack(Frozen):
    """The setting kit every engine's pack carries; an engine adds its tables and its cast."""

    name: str = Field(min_length=1)
    source: str
    license: str
    setting: str = ""
    names: Names = Field(default_factory=Names)  # built on use: its checks live below
    rules: str = ""  # special rules as prose, read by the master alone
    locations: tuple[Location, ...] = ()
    seeds: tuple[str, ...] = ()

    def defined_ids(self) -> tuple[Slug, ...]:
        """The option ids this pack defines; two selected packs may not share one."""
        return ()

    @property
    def counts(self) -> tuple[tuple[str, int], ...]:
        """What the home page counts; an engine puts its tables before the kit's."""
        return (("locations", len(self.locations)), ("seeds", len(self.seeds)))

    @property
    def summary(self) -> str:
        return " · ".join(f"{count} {what}" for what, count in self.counts if count)

    def sections(self, *, opening: bool) -> Sections:
        """Setting, names, locations always; seeds at the opening only; an engine adds its own."""
        name_lines = "\n".join(
            f"{kind}: {SEPARATOR.join(values)}" for kind, values in self.names.listed if values
        )
        location_lines: list[str] = []
        for location in self.locations:
            location_lines.append(f"- {location.label} — {location.detail}")
            if location.encounters:
                location_lines.append(f"  encounters: {location.encounters}")
        return (
            *section_if("SETTING", self.setting),
            *section_if("NAMES", name_lines),
            *section_if("LOCATIONS", "\n".join(location_lines)),
            *(bullets("ADVENTURE SEEDS", self.seeds) if opening else ()),
        )

    def head_fields(self) -> tuple[EditField, ...]:
        """The kit fields of the head, as the page shows them; an engine's tables follow."""
        return (
            EditField(id="setting", label="Setting", text=self.setting, rows=PROSE_ROWS),
            *(
                EditField(id=kind, label=NAME_LABELS[kind], text="\n".join(values), rows=NAME_ROWS)
                for kind, values in self.names.listed
            ),
            EditField(id="rules", label="Special rules", text=self.rules, rows=PROSE_ROWS),
        )

    def body_fields(self) -> tuple[EditField, ...]:
        return (
            EditField(
                id="locations",
                label="Locations",
                text=blocks_text(location.model_dump() for location in self.locations),
                rows=LIST_ROWS,
            ),
            EditField(
                id="seeds", label="Adventure seeds", text="\n".join(self.seeds), rows=LIST_ROWS
            ),
        )


class PackHead(Frozen):
    """The first ask: what the setting is, what a player picks from, what people are called."""

    setting: str = Field(
        min_length=1,
        description="A few paragraphs on what this world is and what a story in it is about.",
    )
    names: Names = Field(
        description="Names that fit the setting, six to twelve per list, a list left empty "
        "where the setting has no such names.",
    )
    rules: str = Field(
        default="",
        description="The genre's one special rule, as prose the game master reads; empty where "
        "the genre has none.",
    )

    def pack_fields(self) -> dict[str, object]:
        """The pack fields this head fills; an engine overrides to make ids for its tables."""
        return self.model_dump()


class PackBody(Frozen):
    """The second ask: who is met, where, and what a story could start from."""

    locations: tuple[Location, ...] = Field(
        min_length=3,
        max_length=6,
        description="Places in this setting, each saying what is found there and who may be met "
        "there.",
    )
    seeds: tuple[str, ...] = Field(
        min_length=6,
        max_length=36,
        description="One-line adventure premises, such as 'A salt barge comes in with no crew "
        "aboard'.",
    )

    @model_validator(mode="after")
    def _every_seed_reads_on_one_line(self) -> Self:
        check_lines("a seed", self.seeds)
        return self


@dataclass(frozen=True, slots=True)
class PackSet[K: Pack]:
    engine: EngineId
    shipped: Mapping[Slug, K]
    written: Mapping[Slug, K]  # the player's, from `packs/<engine>/`; never shadows a shipped id
    installed: Mapping[Slug, K] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "installed", {**self.shipped, **self.written})

    def srd(self) -> K:
        found = self.installed.get(SRD_PACK)
        if found is None:
            raise ValueError(f"the {self.engine!r} engine ships no {SRD_PACK!r} pack")
        return found

    def require(self, selection: PackSelection | None) -> PackSelection:
        if selection is None:
            raise Refusal(f"a {self.engine!r} game needs a table set")
        return selection

    def supplements(self) -> tuple[tuple[Slug, K], ...]:
        return tuple((key, pack) for key, pack in self.installed.items() if key != SRD_PACK)

    def chosen(self, selection: PackSelection | None) -> tuple[K, ...]:
        if selection is None:
            return ()
        return tuple(self.installed[pack_id] for pack_id in selection.ids)

    def select(self, selection: PackSelection) -> PackSelection:
        if missing := sorted(set(selection.ids) - set(self.installed)):
            raise Refusal(f"packs not installed for {self.engine!r}: {missing}")
        supplements = [pack_id for pack_id in selection.ids if pack_id != SRD_PACK]
        if len(supplements) > MAX_SUPPLEMENTS:
            raise Refusal(f"a game plays at most {MAX_SUPPLEMENTS} packs beside the SRD")
        defined: dict[Slug, Slug] = {}
        for pack_id in selection.ids:
            ids = set(self.installed[pack_id].defined_ids())
            if shared := sorted(ids & defined.keys()):
                raise Refusal(f"{pack_id!r} and {defined[shared[0]]!r} both define {shared[0]!r}")
            defined.update(dict.fromkeys(ids, pack_id))
        return selection

    def installing(self, pack_id: Slug, pack: K) -> "PackSet[K]":
        """A new set: the same shipped packs, `written` with this one added or replaced."""
        return PackSet(self.engine, self.shipped, {**self.written, pack_id: pack})

    def check_addable(self, pack_id: Slug, pack: K) -> None:
        """Refuse a pack that could not be selected beside the SRD, before anything is written."""
        if pack_id in self.shipped:
            raise Refusal(f"{pack_id!r} is a shipped pack")
        ids = (SRD_PACK, pack_id) if SRD_PACK in self.installed else (pack_id,)
        self.installing(pack_id, pack).select(parse(PackSelection, {"ids": ids}))

    def guidance(self, selection: PackSelection | None, *, opening: bool) -> str:
        blocks = [
            f"PACK: {pack.name}\n\n{sections(parts)}"
            for pack in self.chosen(selection)
            if (parts := pack.sections(opening=opening))
        ]
        return "\n\n".join(blocks)

    def rules_sections(self, selection: PackSelection | None) -> Sections:
        return tuple(
            (f"SPECIAL RULES: {pack.name}", pack.rules)
            for pack in self.chosen(selection)
            if pack.rules
        )

    def seeds(self, selection: PackSelection | None) -> tuple[str, ...]:
        return tuple(seed for pack in self.chosen(selection) for seed in pack.seeds)


def block_line(name: str, brief: str, *fields: tuple[str, str]) -> str:
    """`name — brief; key: value; …`, empty values dropped: how a cast block reads in a prompt."""
    return "; ".join((f"{name} — {brief}", *(f"{key}: {value}" for key, value in fields if value)))


def options(labelled: Iterable[Labelled], taken: list[Slug]) -> tuple[DecisionOption, ...]:
    """Ids from labels; `taken` grows so the ids stay unique across a pack's tables."""
    made: list[DecisionOption] = []
    for entry in labelled:
        made.append(
            DecisionOption(id=slug(entry.label, taken), label=entry.label, detail=entry.detail)
        )
        taken.append(made[-1].id)
    return tuple(made)


def bullets(title: str, lines: Iterable[str]) -> Sections:
    return section_if(title, "\n".join(f"- {line}" for line in lines))


def table_text(entries: Iterable[DecisionOption]) -> str:
    """One entry per line, `Label` or `Label — detail`."""
    return "\n".join(
        f"{entry.label}{DASH}{entry.detail}" if entry.detail else entry.label for entry in entries
    )


def parse_table(text: str) -> tuple[Labelled, ...]:
    """A blank line is skipped; a line with two dashes is refused as `line N: one " — " at most`."""
    entries: list[Labelled] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(DASH)
        if len(parts) > 2:
            raise Refusal(f'line {number}: one "{DASH}" at most')
        label, detail = parts[0], parts[1] if len(parts) == 2 else ""
        try:
            entries.append(parse(Labelled, {"label": label.strip(), "detail": detail.strip()}))
        except Refusal as refused:
            raise Refusal(f"line {number}: {refused}") from refused
    return tuple(entries)


def parse_list(text: str) -> tuple[str, ...]:
    return tuple(stripped for line in text.splitlines() if (stripped := line.strip()))


def blocks_text(blocks: Iterable[Mapping[str, object]]) -> str:
    """Blocks a blank line apart: the first value is the name line, then `Key: value` per field."""
    return "\n\n".join(_block_text(block) for block in blocks)


def parse_blocks[T: BaseModel](model: type[T], text: str) -> tuple[T, ...]:
    """The first field is the name line; a key is a field name, `hit_points` as `Hit points`."""
    fields = model.model_fields
    named = next(iter(fields))
    blocks: list[T] = []
    for number, lines in enumerate(_blocks(text), start=1):
        where = f"block {number} ({lines[0].strip()})"
        written: dict[str, object] = {named: lines[0].strip()}
        for line in lines[1:]:
            key, marked, value = line.partition(": ")
            if not marked:
                raise Refusal(f'{where}: not "Key: value": {line}')
            field_name = key.strip().lower().replace(" ", "_")
            found = fields.get(field_name)
            if found is None:
                raise Refusal(f"{where}: unknown key {key.strip()}")
            written[field_name] = _field_value(where, key.strip(), found.annotation, value.strip())
        for field_name, info in fields.items():
            if info.is_required() and field_name not in written:
                raise Refusal(f"{where}: missing {_key_label(field_name)}")
        try:
            blocks.append(parse(model, written))
        except Refusal as refused:
            raise Refusal(f"{where}: {refused}") from refused
    return tuple(blocks)


def block_fields(rows: Iterable[tuple[Slug, str, Iterable[BaseModel]]]) -> tuple[EditField, ...]:
    """One field per cast list an engine names: its id, its label, its blocks."""
    return tuple(
        EditField(
            id=field_id,
            label=label,
            text=blocks_text(block.model_dump() for block in blocks),
            rows=LIST_ROWS,
        )
        for field_id, label, blocks in rows
    )


def block_values[T: BaseModel](
    model: type[T], values: Mapping[str, str], keys: Iterable[Slug]
) -> dict[str, object]:
    return {key: parse_blocks(model, values[key]) for key in keys}


def head_values(values: Mapping[str, str]) -> dict[str, object]:
    return {
        "setting": values["setting"].strip(),
        "names": {kind: parse_list(values[kind]) for kind in NAME_LABELS},
        "rules": values["rules"].strip(),
    }


def body_values(values: Mapping[str, str]) -> dict[str, object]:
    return {
        "locations": parse_blocks(Location, values["locations"]),
        "seeds": parse_list(values["seeds"]),
    }


def check_lines(what: str, values: Iterable[str]) -> None:
    for value in values:
        if "\n" in value:
            raise ValueError(f"{what} runs over one line")


def check_items(what: str, values: Iterable[str]) -> None:
    check_lines(what, values)
    for value in values:
        if SEPARATOR in value:
            raise ValueError(f'{what} holds "{SEPARATOR}", which parts one item from the next')


def read_packs[P: Pack](
    engine: EngineId, shipped: Path, written: Path, model: type[P]
) -> PackSet[P]:
    """A shipped file that fails to parse is a bug; a written one is logged and skipped."""
    shipped_packs = {
        content_id(path.stem): read_model(path, model) for path in sorted(shipped.glob("*.json"))
    }
    written_packs: dict[Slug, P] = {}
    for path in sorted(written.glob("*.json")):
        try:
            pack_id = content_id(path.stem)
            pack = read_model(path, model)
        except Refusal as unreadable:
            LOGGER.warning("skipping pack %s for %r: %s", path.name, engine, unreadable)
            continue
        if pack_id in shipped_packs:
            LOGGER.warning(
                "skipping pack %s for %r: %r is a shipped pack", path.name, engine, pack_id
            )
            continue
        written_packs[pack_id] = pack
    return PackSet(engine, shipped_packs, written_packs)


def _blocks(text: str) -> Iterator[list[str]]:
    """The written lines of each block, blocks parted by a blank line."""
    block: list[str] = []
    for line in text.splitlines():
        if line.strip():
            block.append(line)
        elif block:
            yield block
            block = []
    if block:
        yield block


def _block_text(block: Mapping[str, object]) -> str:
    named, *rest = block.items()
    if not (name_line := _printed(*named)):
        raise ValueError(f"a block is named by its first field, and {named[0]} is empty")
    lines = [
        f"{_key_label(key)}: {written}" for key, value in rest if (written := _printed(key, value))
    ]
    return "\n".join((name_line, *lines))


def _printed(key: str, value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):  # before `int`: no key reads back as a truth value
        raise ValueError(f"{key} is neither text, a number nor a list of names")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        names = [item for item in items if isinstance(item, str)]
        if len(names) != len(items):
            raise ValueError(f"{key} holds something that is not a name")
        return SEPARATOR.join(names)
    raise ValueError(f"{key} is neither text, a number nor a list of names")


def _field_value(
    where: str, key: str, annotation: object, value: str
) -> str | int | tuple[str, ...]:
    if annotation is str:
        return value
    if annotation is int:
        try:
            return int(value)
        except ValueError as broken:
            raise Refusal(f"{where}: {key} is not a number") from broken
    if get_origin(annotation) is tuple:
        return tuple(item.strip() for item in value.split(SEPARATOR))
    raise ValueError(f"{key} is neither text, a number nor a list of names")


def _key_label(field_name: str) -> str:
    return field_name.replace("_", " ").capitalize()
