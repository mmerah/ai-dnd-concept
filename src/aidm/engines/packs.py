import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, JsonValue, model_validator

from aidm.core.entities import EngineId, Frozen, Refusal, Slug, content_id, parse, parse_json, slug
from aidm.core.io import decode, read_model
from aidm.core.model import WorldsmithAnswer
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, section_if, sections
from aidm.core.tools import schema_text

LOGGER = logging.getLogger(__name__)

DASH = " — "  # parts a name from its brief (`Named`, `Pack.sections`); inside neither
SEPARATOR = ", "  # parts one name from the next in the NAMES line; nowhere inside a name
PROVENANCE = frozenset(("name", "source", "license"))  # the pack's own; no box edits it
SRD_PACK: Slug = "srd"
PACK_SO_FAR = "THE PACK SO FAR"
SOURCELESS = "(none — write from what is below)"
SCOPELESS = "(none — this is a pack, not a scenario: a genre kit, not one adventure)"
SOURCE_BOUND = (
    "Everything comes from SOURCE MATERIAL, its premise and, when it holds one, its document; "
    "nothing outside it."
)
HEAD_ASK = (
    "Write the head of a pack for this setting. A pack is a genre kit the worldsmith reads when "
    "it writes scenarios in this setting. `setting` is a few paragraphs on what this world is "
    "and what a story in it is about. The creation tables are the names a player picks from, "
    "each with a one-line `brief` only where the name does not explain itself. The name lists "
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
        for kind, values in self.listed():
            check_items(kind, values)
        return self


class Named(Frozen):
    """One row of a creation table as the worldsmith writes it, before code makes its id."""

    name: str = Field(min_length=1, max_length=60)
    brief: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _reads_as_one_table_line(self) -> Self:
        check_lines("a table entry", (self.name, self.brief))
        if DASH in self.name or DASH in self.brief:
            raise ValueError(f'a table entry holds "{DASH}", which parts a name from its brief')
        return self


class Location(Frozen):
    name: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    encounters: str = ""  # the SRD's "Possible encounters" line, names the worldsmith may use

    @model_validator(mode="after")
    def _reads_in_a_block(self) -> Self:
        check_lines("a location", (self.name, self.brief, self.encounters))
        return self


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

    def counts(self) -> tuple[tuple[str, int], ...]:
        """What the home page counts; an engine puts its tables before the kit's."""
        return (("locations", len(self.locations)), ("seeds", len(self.seeds)))

    def summary(self) -> str:
        return " · ".join(f"{count} {what}" for what, count in self.counts() if count)

    def sections(self, *, opening: bool) -> Sections:
        """Setting, names, locations always; seeds at the opening only; an engine adds its own."""
        name_lines = "\n".join(
            f"{kind}: {SEPARATOR.join(values)}" for kind, values in self.names.listed() if values
        )
        location_lines: list[str] = []
        for location in self.locations:
            location_lines.append(f"- {location.name} — {location.brief}")
            if location.encounters:
                location_lines.append(f"  encounters: {location.encounters}")
        return (
            *section_if("SETTING", self.setting),
            *section_if("NAMES", name_lines),
            *section_if("LOCATIONS", "\n".join(location_lines)),
            *(bullets("ADVENTURE SEEDS", self.seeds) if opening else ()),
        )

    def boxes(self) -> dict[str, str]:
        """Every field but its provenance as JSON text: one textarea on the pack page each."""
        dumped: dict[str, JsonValue] = self.model_dump(mode="json")
        return {
            field_id: json.dumps(value, indent=2, ensure_ascii=False)
            for field_id, value in dumped.items()
            if field_id not in PROVENANCE
        }


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

    @property
    def installed(self) -> Mapping[Slug, K]:
        return {**self.shipped, **self.written}

    def srd(self) -> K:
        found = self.installed.get(SRD_PACK)
        if found is None:
            raise ValueError(f"the {self.engine!r} engine ships no {SRD_PACK!r} pack")
        return found

    def require(self, pack_id: Slug) -> K:
        found = self.installed.get(pack_id)
        if found is None:
            raise Refusal(f"pack {pack_id!r} is not installed for {self.engine!r}")
        return found

    def played(self, pack_id: Slug) -> tuple[K, ...]:
        """The packs a creation table is read from: the SRD, then the chosen pack; the SRD once."""
        srd = self.srd()
        return (srd,) if pack_id == SRD_PACK else (srd, self.require(pack_id))

    def options(self) -> tuple[DecisionOption, ...]:
        """The SRD first, then the rest of `installed` in order; id and `pack.name`."""
        rest = tuple(
            DecisionOption(id=pack_id, name=pack.name)
            for pack_id, pack in self.installed.items()
            if pack_id != SRD_PACK
        )
        return (DecisionOption(id=SRD_PACK, name=self.srd().name), *rest)

    def installing(self, pack_id: Slug, pack: K) -> "PackSet[K]":
        """A new set: the same shipped packs, `written` with this one added or replaced."""
        return PackSet(self.engine, self.shipped, {**self.written, pack_id: pack})

    def guidance(self, pack_id: Slug, *, opening: bool) -> str:
        """One `PACK:` block for `require(pack_id)`, or "" when it has no sections."""
        pack = self.require(pack_id)
        parts = pack.sections(opening=opening)
        return f"PACK: {pack.name}\n\n{sections(parts)}" if parts else ""

    def rules_section(self, pack_id: Slug) -> Sections:
        pack = self.require(pack_id)
        return ((f"SPECIAL RULES: {pack.name}", pack.rules),) if pack.rules else ()


@dataclass(frozen=True, slots=True)
class PackAuthor[K: Pack]:
    pack_model: type[K]
    head_model: type[PackHead]
    body_model: type[PackBody]
    authoring: str
    role: str  # the family's worldsmith.md, for render_worldsmith

    async def author(
        self, *, name: str, source: str, origin: str, license: str, worldsmith: WorldsmithAnswer
    ) -> K:
        """Head, then body; each checked by building the pack; nothing is written here."""

        def built(from_head: PackHead, from_body: PackBody | None) -> K:
            return parse(
                self.pack_model,
                {
                    "name": name,
                    # The pack's `source` is its provenance; the material it was
                    # written from is not kept.
                    "source": origin,
                    "license": license,
                    **from_head.pack_fields(),
                    **({} if from_body is None else from_body.model_dump()),
                },
            )

        def check_head(answer: PackHead) -> None:
            built(answer, None)

        def asked(intent: str, world_sections: Sections, answer_model: type[BaseModel]) -> str:
            return render_worldsmith(
                self.role,
                source=source,
                scope="",
                world_sections=world_sections,
                intent=intent,
                guidance=self.authoring,
                answer_model=answer_model,
            )

        head = await worldsmith(asked(HEAD_ASK, (), self.head_model), self.head_model, check_head)
        so_far = ((PACK_SO_FAR, sections(built(head, None).sections(opening=True))),)

        def check_body(answer: PackBody) -> None:
            built(head, answer)

        body = await worldsmith(
            asked(BODY_ASK, so_far, self.body_model), self.body_model, check_body
        )
        return built(head, body)

    def edited(self, pack: K, values: Mapping[str, str]) -> K:
        """The boxes decoded over the pack's own dump; a field no box holds keeps its value."""
        dumped: dict[str, JsonValue] = pack.model_dump(mode="json")
        for field_id, box in values.items():
            if field_id in PROVENANCE:
                raise Refusal(f"{field_id} is the pack's own and is not edited here")
            try:
                dumped[field_id] = decode(box)
            except Refusal as refused:
                raise Refusal(f"{field_id}: {refused}") from refused
        # Through JSON, not `parse`: strict mode reads a tuple field from a JSON array alone.
        return parse_json(self.pack_model, json.dumps(dumped))


def render_worldsmith(
    role: str,
    *,
    source: str,
    scope: str,
    world_sections: Sections,
    intent: str,
    guidance: str,
    answer_model: type[BaseModel],
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or SOURCELESS),
            ("THE SCOPE OF PLAY", scope or SCOPELESS),
            *world_sections,
            ("WHAT COMES NEXT", intent),
            ("ENGINE GUIDANCE", guidance),
            ("ANSWER WITH", schema_text(answer_model)),
        )
    )


def block_line(name: str, brief: str, *fields: tuple[str, str]) -> str:
    """`name — brief; key: value; …`, empty values dropped: how a cast block reads in a prompt."""
    return "; ".join((f"{name} — {brief}", *(f"{key}: {value}" for key, value in fields if value)))


def with_ids(rows: Iterable[Named], taken: list[Slug]) -> tuple[DecisionOption, ...]:
    """Ids from names; `taken` grows so the ids stay unique across a pack's tables."""
    made: list[DecisionOption] = []
    for entry in rows:
        made.append(DecisionOption(id=slug(entry.name, taken), name=entry.name, brief=entry.brief))
        taken.append(made[-1].id)
    return tuple(made)


def bullets(title: str, lines: Iterable[str]) -> Sections:
    return section_if(title, "\n".join(f"- {line}" for line in lines))


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
