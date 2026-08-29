import re
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, JsonValue, ValidationError
from pypdf import PdfReader

from aidm.config import Settings
from aidm.content.io import load_character, source_file, write_scenario
from aidm.content.model import AuthoringBrief, Character, Scenario
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId, Exit, Frozen, Mutable, Slug
from aidm.state.facts import Fact
from aidm.state.model import Game, ScenarioMeta, Thread, WorldState
from aidm.world.topology import player_location


def _describe(item: Entity | Thread, verb: str) -> str:
    if isinstance(item, Entity):
        return f"{verb} {item.kind} {item.name}[{item.id}]"
    return f"{verb} thread {item.title}[{item.id}]"


class ScenarioPatch(Frozen):
    """One draft update. Set only the fields that change."""

    meta: ScenarioMeta | None = None
    player_parent_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] | None = None
    art_style: str | None = Field(
        default=None,
        description=(
            "One-line palette, medium, and mood for illustrations. Null uses the app default."
        ),
    )
    entities: tuple[Entity, ...] = ()
    threads: tuple[Thread, ...] = ()
    mechanics: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="This engine's own rules for the draft, merged over what it already holds.",
    )
    remove: tuple[str, ...] = ()

    def scenario_wide(self) -> list[str]:
        """What this patch sets for the scenario itself: optional here means leave it alone."""
        return [
            name
            for name, field in type(self).model_fields.items()
            if field.default is None and getattr(self, name) is not None
        ]


class ScenarioDraft(Mutable):
    art_style: str = ""
    meta: ScenarioMeta | None = None
    player_parent_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: dict[EntityId, Entity] = Field(default_factory=dict)
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    mechanics: dict[str, JsonValue] = Field(default_factory=dict)

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> "ScenarioDraft":
        return cls(
            art_style=scenario.art_style,
            meta=scenario.meta,
            player_parent_id=scenario.player_parent_id,
            starting_party=tuple(scenario.world.party),
            entities=deepcopy(scenario.world.entities),
            threads=deepcopy(scenario.world.threads),
            mechanics=deepcopy(scenario.world.mechanics),
        )

    @classmethod
    def from_game(cls, state: Game) -> "ScenarioDraft":
        """Exclude played-character state: `Scenario` refuses the reserved player id."""
        world = state.world
        played = {PLAYER_ID, state.player_id}
        return cls(
            meta=state.scenario,
            player_parent_id=player_location(state),
            starting_party=tuple(
                member
                for member in world.party
                if world.require(member).parent_id == player_location(state)
            ),
            entities={
                entity_id: deepcopy(entity)
                for entity_id, entity in world.entities.items()
                if played.isdisjoint({entity.id, entity.parent_id})
            },
            threads=deepcopy(world.threads),
            mechanics=deepcopy(world.mechanics),
        )

    def apply(self, patch: ScenarioPatch, engine: Engine) -> str:
        changed: list[str] = []
        for name in patch.scenario_wide():
            setattr(self, name, getattr(patch, name))
            changed.append(f"set {name}")
        for entity in patch.entities:
            verb = "modified" if entity.id in self.entities else "created"
            changed.append(_describe(entity, verb))
            self.entities[entity.id] = entity
        for thread in patch.threads:
            verb = "modified" if thread.id in self.threads else "created"
            changed.append(_describe(thread, verb))
            self.threads[thread.id] = thread
        if patch.mechanics:
            self.mechanics = engine.mechanics_merge(self.mechanics, patch.mechanics)
            changed.append("set mechanics")
        changed.extend(self._remove(target, engine) for target in patch.remove)
        return "\n".join(changed) if changed else "nothing to change"

    def _remove(self, target: str, engine: Engine) -> str:
        removed: Entity | Thread | None = self.entities.pop(EntityId(target), None)
        if removed is not None:
            self.mechanics = engine.mechanics_without(self.mechanics, EntityId(target))
        if removed is None:
            removed = self.threads.pop(target, None)
        if removed is None:
            raise ValueError(
                f"nothing in the draft has id {target!r}; read `scenario_so_far` and remove ids "
                "exactly as it spells them"
            )
        return _describe(removed, "deleted")

    def connect(
        self, from_id: EntityId, to_id: EntityId, known: bool, locked: bool, one_way: bool
    ) -> str:
        if from_id == to_id:
            raise ValueError(f"a way leads somewhere other than {from_id!r}")
        ends = {from_id: self._require_location(from_id), to_id: self._require_location(to_id)}
        ways = ((from_id, to_id),) if one_way else ((from_id, to_id), (to_id, from_id))
        # Appending to `exits` skips validation, so every refusal lands before the first append.
        for start, end in ways:
            if ends[start].exit_to(end) is not None:
                raise ValueError(f"a way already leads from {start!r} to {end!r}")
            if known and not (ends[start].known and ends[end].known):
                raise ValueError(
                    f"a known way from {start!r} to {end!r} names a place the player has not "
                    "met; leave it unknown until both ends are"
                )
        for start, end in ways:
            ends[start].exits.append(Exit(to=end, known=known, locked=locked))
        return f"joined {from_id} to {to_id} {'one way' if one_way else 'both ways'}"

    def _require_location(self, entity_id: EntityId) -> Entity:
        held = self.entities.get(entity_id)
        if held is None or held.kind != "location":
            raise ValueError(f"the draft holds no location {entity_id!r}")
        return held

    def as_patch(self) -> ScenarioPatch:
        """The one shape the model reads and writes, so the example never teaches a refusal."""
        return ScenarioPatch(
            meta=self.meta,
            player_parent_id=self.player_parent_id,
            starting_party=self.starting_party,
            art_style=self.art_style,
            entities=tuple(self.entities.values()),
            threads=tuple(self.threads.values()),
            mechanics=self.mechanics,
        )

    def as_json(self) -> str:
        return self.as_patch().model_dump_json(indent=2)

    def scenario(self, engine: EngineId, packs: tuple[Slug, ...], grows: bool = False) -> Scenario:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        if self.player_parent_id is None:
            raise ValueError(
                "the draft has no `player_parent_id` yet: say where the character starts"
            )
        return Scenario(
            meta=self.meta,
            grows=grows,
            engine=engine,
            packs=packs,
            art_style=self.art_style,
            player_parent_id=self.player_parent_id,
            world=WorldState(
                entities=dict(self.entities),
                threads=dict(self.threads),
                party=list(self.starting_party),
                mechanics=dict(self.mechanics),
            ),
        )


@dataclass(frozen=True, slots=True)
class PlaytestCheck:
    engine: Engine
    character: Character
    packs: tuple[Slug, ...]

    def __post_init__(self) -> None:
        if missing := sorted(set(self.packs) - set(self.engine.packs)):
            raise ValueError(f"packs not installed for {self.engine.id!r}: {missing}")

    def check(self, scenario: Scenario) -> None:
        # A playtest never saves, so the game's id is never read; any well-formed slug serves.
        _ = begin_game(self.engine, "draft", scenario, self.character)


def playtest_check(
    settings: Settings, engine: Engine, packs: tuple[Slug, ...] = ()
) -> PlaytestCheck:
    """An empty selection means the engine's first installed pack."""
    selected = packs or (next(iter(engine.packs)),)
    character = load_character(
        settings.characters_dir,
        settings.authoring.starter_character,
        engine.id,
        engine.character_mechanics,
    )
    return PlaytestCheck(engine=engine, character=character, packs=selected)


MIN_LOCATIONS = 4
MIN_ACTORS = 2


def _bar_unmet(scenario: Scenario) -> list[str]:
    unmet: list[str] = []
    entities, threads = scenario.world.entities.values(), scenario.world.threads
    locations = sorted(entity.id for entity in entities if entity.kind == "location")
    if len(locations) < MIN_LOCATIONS:
        unmet.append(f"four or more locations; the draft has {len(locations)}: {locations}")
    ways = [way for entity in entities for way in entity.exits]
    if all(way.known for way in ways):
        unmet.append("at least one exit starting `known: false` — a way to find")
    if not any(way.locked for way in ways):
        unmet.append("at least one exit starting `locked: true`")
    actors = [entity for entity in entities if entity.kind == "actor"]
    if len(actors) < MIN_ACTORS:
        actor_ids = sorted(actor.id for actor in actors)
        unmet.append(f"two or more actors; the draft has {len(actors)}: {actor_ids}")
    if all(actor.known for actor in actors):
        unmet.append("at least one actor starting `known: false`")
    if not any(entity.kind == "item" and not entity.known for entity in entities):
        unmet.append("at least one item starting `known: false` — a secret to find")
    if not threads:
        unmet.append("at least one thread")
    if not any(entity.when_reached and not entity.known for entity in entities):
        unmet.append("at least one unknown entity whose `when_reached` carries a consequence")
    return unmet


MIN_OPENING_ENTITIES = 2


def _opening_unmet(scenario: Scenario) -> list[str]:
    unmet: list[str] = []
    beyond = [
        entity_id for entity_id in scenario.world.entities if entity_id != scenario.player_parent_id
    ]
    if len(beyond) < MIN_OPENING_ENTITIES:
        unmet.append(
            f"two or three entities besides the starting location; the draft has {len(beyond)}"
        )
    if not scenario.world.threads:
        unmet.append("at least one thread")
    return unmet


WHOLE_SCENARIO = AuthoringBrief("scenario_bar.md", _bar_unmet)
# An opening slice is deliberately thin: the rest of the world is written during play.
OPENING_SLICE = AuthoringBrief("scenario_opening.md", _opening_unmet)


def extend_brief(before: WorldState) -> AuthoringBrief:
    held = set(before.entities)

    def unmet(scenario: Scenario) -> list[str]:
        added = {
            entity.id
            for entity in scenario.world.entities.values()
            if entity.kind == "location" and entity.id not in held
        }
        if not added:
            return ["at least one location the world did not already hold"]
        if not any(
            way.to in added
            for entity in scenario.world.entities.values()
            if entity.id in held and entity.known
            for way in entity.exits
        ):
            return [
                "at least one exit from a location the player already knows of into one of the "
                f"new ones: {sorted(added)}"
            ]
        return []

    return AuthoringBrief(
        "scenario_extend.md",
        unmet,
        settled=frozenset(held | set(before.threads)),
    )


def scenario_refusal(
    draft: ScenarioDraft, playing: PlaytestCheck, brief: AuthoringBrief = WHOLE_SCENARIO
) -> str | None:
    try:
        scenario = draft.scenario(playing.engine.id, playing.packs)
        playing.check(scenario)
    except ValidationError as broken:
        error = broken.errors()[0]
        where = ".".join(str(part) for part in error["loc"])
        return f"{where}: {error['msg']}" if where else str(error["msg"])
    except ValueError as refused:
        return str(refused)
    if unmet := brief.unmet(scenario):
        listed = "\n".join(f"- {item}" for item in unmet)
        return f"the draft plays, but it is under the bar. Still missing:\n{listed}"
    return None


def patch_refusal(patch: ScenarioPatch, settled: frozenset[str]) -> str | None:
    """A pass over a world in play only adds: the live game is already standing on the rest."""
    if not settled:
        return None
    if moved := patch.scenario_wide():
        return f"a scenario already in play keeps its {', '.join(moved)}"
    held = {item.id for item in (*patch.entities, *patch.threads)} | set(patch.remove)
    if taken := sorted(held & settled):
        return (
            f"the live game already holds {taken}, some of it beyond what `scenario_so_far` "
            "shows you. Write ids of your own, and reach what is already there with `connect`."
        )
    return None


def given_text(settings: Settings, premise: str, document: Path | None) -> str:
    if document is None:
        return f"PREMISE:\n{premise}"
    return f"SOURCE DOCUMENT:\n{whole_text(document, settings.authoring.source_max_chars)}"


def world_prompt(settings: Settings, slug: Slug, premise: str, document: Path | None) -> str:
    return f"{given_text(settings, premise, document)}\n\nWill be saved as: {slug!r}"


def check_new_scenario(settings: Settings, slug: Slug, premise: str, document: Path | None) -> None:
    if document is None and not premise:
        raise ValueError("give a premise, a document, or both: there is nothing to author from")
    if (settings.scenarios_dir / slug).exists():
        raise ValueError(f"scenario {slug!r} already exists")


def write_draft(
    settings: Settings,
    slug: Slug,
    draft: ScenarioDraft,
    engine: EngineId,
    packs: tuple[Slug, ...],
    grows: bool,
    source: Path | str,
) -> str:
    scenario = draft.scenario(engine, packs, grows)
    write_scenario(settings.scenarios_dir, slug, scenario, source)
    return summarize(scenario)


def summarize(scenario: Scenario) -> str:
    return (
        f"{scenario.meta.title}\n"
        f"{len(scenario.world.entities)} entities, {len(scenario.world.threads)} threads"
    )


class ExitLink(Frozen):
    location_id: EntityId
    to: EntityId
    locked: bool = False


class ExtensionPatch(Frozen):
    entities: tuple[Entity, ...] = ()
    exits: tuple[ExitLink, ...] = ()
    threads: tuple[Thread, ...] = ()


def extension_prompt(settings: Settings, state: Game) -> str:
    document = source_file(settings.scenarios_dir, state.scenario_id)
    given = given_text(settings, state.scenario.premise, document)
    packs = ", ".join(state.packs)
    return (
        f"{given}\n\nThis scenario is authored against these content packs: {packs}."
        "\n\nExtend the world `scenario_so_far` holds."
    )


def extension_patch(before: WorldState, after: ScenarioDraft) -> ExtensionPatch:
    held = before.entities
    return ExtensionPatch(
        entities=tuple(entity for entity in after.entities.values() if entity.id not in held),
        exits=tuple(
            ExitLink(location_id=entity.id, to=way.to, locked=way.locked)
            for entity in after.entities.values()
            if (was := held.get(entity.id)) is not None
            for way in entity.exits
            if was.exit_to(way.to) is None
        ),
        threads=tuple(
            thread for thread in after.threads.values() if thread.id not in before.threads
        ),
    )


def apply_patch(draft: Game, patch: ExtensionPatch) -> tuple[Fact, ...]:
    facts = [_added_entity(draft, entity) for entity in patch.entities]
    facts.extend(_added_exit(draft, link) for link in patch.exits)
    facts.extend(_opened(draft, thread) for thread in patch.threads)
    return tuple(facts)


def _added_entity(draft: Game, entity: Entity) -> Fact:
    # Copied, so the patch recorded in the trace is not the object the world goes on mutating.
    materialized = entity.model_copy(deep=True)
    materialized.known = False
    for way in materialized.exits:
        way.known = False
    return draft.add(materialized)


def _added_exit(draft: Game, link: ExitLink) -> Fact:
    here = draft.world.require_kind(link.location_id, "location")
    if here.exit_to(link.to) is not None:
        raise ValueError(f"a way already leads from {here.id!r} to {link.to!r}")
    here.exits.append(Exit(to=link.to, locked=link.locked))
    return _materialized(f"way from {here.id} to {link.to}")


def _opened(draft: Game, thread: Thread) -> Fact:
    if draft.world.thread(thread.id) is not None:
        raise ValueError(f"a thread {thread.id!r} already exists")
    draft.world.threads[thread.id] = thread.model_copy(deep=True)
    return _materialized(f"thread {thread.id}")


def _materialized(what: str) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}")


MIN_PASSAGE = 24
_BLANK_LINE = re.compile(r"\n\s*\n")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")


def whole_text(path: Path, max_chars: int) -> str:
    pages = (
        _pdf_pages(path) if path.suffix.lower() == ".pdf" else (path.read_text(encoding="utf-8"),)
    )
    text = "\n\n".join(passage for page in pages for passage in _passages(page))
    if not text:
        raise ValueError(f"{path.name} holds no readable text")
    if len(text) > max_chars:
        raise ValueError(
            f"{path.name} is {len(text)} characters, too large to hand to a model whole"
        )
    return text


def _pdf_pages(path: Path) -> tuple[str, ...]:
    # Layout mode interleaves columns and mangles letter-spaced display text.
    return tuple(page.extract_text() for page in PdfReader(path).pages)


def _passages(body: str) -> Iterator[str]:
    for block in _BLANK_LINE.split(body.strip()):
        text = " ".join(_LINE_BREAK_HYPHEN.sub(r"\1-\2", _unquoted(block)).split())
        # A page number or a running header is not a passage.
        if len(text) >= MIN_PASSAGE:
            yield text


def _unquoted(block: str) -> str:
    """A Markdown quote marker is punctuation around a line, not part of its text."""
    return "\n".join(line.strip().removeprefix(">").strip() for line in block.splitlines())
