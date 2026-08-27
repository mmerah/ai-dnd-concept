from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from pydantic import Field, JsonValue, ValidationError

from aidm.config import Settings
from aidm.content.io import (
    load_character,
    load_scenario,
    scenario_packs,
    source_file,
    whole_text,
    write_scenario,
)
from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engine
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId, Exit, Frozen, Mutable, Slug
from aidm.state.facts import Fact
from aidm.state.model import Game, ScenarioMeta, Thread, WorldState


def _index[T: Entity | Thread](kept: list[T], target: str) -> int | None:
    return next((index for index, held in enumerate(kept) if held.id == target), None)


def _describe(item: Entity | Thread, verb: str) -> str:
    if isinstance(item, Entity):
        return f"{verb} {item.kind} {item.name}[{item.id}]"
    return f"{verb} thread {item.title}[{item.id}]"


def _upsert[T: Entity | Thread](kept: list[T], written: Iterable[T]) -> list[str]:
    lines: list[str] = []
    for one in written:
        found = _index(kept, one.id)
        if found is None:
            kept.append(one)
            lines.append(_describe(one, "created"))
        else:
            kept[found] = one
            lines.append(_describe(one, "modified"))
    return lines


def _drop[T: Entity | Thread](kept: list[T], target: str) -> T | None:
    found = _index(kept, target)
    if found is None:
        return None
    return kept.pop(found)


class ScenarioPatch(Frozen):
    """One draft update. Set only the fields that change."""

    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] | None = None
    art_style: str | None = Field(
        default=None,
        description=(
            "One-line palette, medium, and mood for illustrations. Null uses the app default."
        ),
    )
    entities: tuple[Entity, ...] = ()
    threads: tuple[Thread, ...] = ()
    remove: tuple[str, ...] = ()

    def scenario_wide(self) -> list[str]:
        """What this patch sets for the scenario itself: optional here means leave it alone."""
        return [
            name
            for name, field in type(self).model_fields.items()
            if field.default is None and getattr(self, name) is not None
        ]


# Read back but never written by `write`: the run settles `grows`, and `write_pack` owns `packs`.
NOT_PATCHED = {"grows", "packs"}


class ScenarioDraft(Mutable):
    grows: bool = False
    art_style: str = ""
    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)
    # Content packs this draft ships with; they reach disk beside the world it writes.
    packs: dict[Slug, JsonValue] = Field(default_factory=dict)

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> "ScenarioDraft":
        return cls(
            grows=scenario.grows,
            art_style=scenario.art_style,
            meta=scenario.meta,
            starting_location_id=scenario.starting_location_id,
            starting_party=tuple(scenario.world.party),
            entities=[entity.model_copy(deep=True) for entity in scenario.world.entities],
            threads=[thread.model_copy(deep=True) for thread in scenario.world.threads],
        )

    @classmethod
    def from_game(cls, state: Game) -> "ScenarioDraft":
        """Exclude played-character state: `Scenario` refuses the reserved player id."""
        world = state.world
        played = {PLAYER_ID, state.player_id}
        return cls(
            meta=state.scenario,
            starting_location_id=state.player_location,
            starting_party=tuple(
                member
                for member in world.party
                if world.require(member).parent_id == state.player_location
            ),
            entities=[
                entity.model_copy(deep=True)
                for entity in world.entities
                if played.isdisjoint({entity.id, entity.parent_id})
            ],
            threads=[thread.model_copy(deep=True) for thread in world.threads],
        )

    def apply(self, patch: ScenarioPatch) -> str:
        changed: list[str] = []
        for name in patch.scenario_wide():
            setattr(self, name, getattr(patch, name))
            changed.append(f"set {name}")
        changed.extend(_upsert(self.entities, patch.entities))
        changed.extend(_upsert(self.threads, patch.threads))
        changed.extend(self._remove(target) for target in patch.remove)
        return "\n".join(changed) if changed else "nothing to change"

    def _remove(self, target: str) -> str:
        removed = _drop(self.entities, target)
        if removed is None:
            removed = _drop(self.threads, target)
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
        found = _index(self.entities, entity_id)
        held = None if found is None else self.entities[found]
        if held is None or held.kind != "location":
            raise ValueError(f"the draft holds no location {entity_id!r}")
        return held

    def write_pack(self, pack_id: Slug, content: dict[str, JsonValue]) -> str:
        wrote = "rewrote" if pack_id in self.packs else "wrote"
        self.packs[pack_id] = content
        return f"{wrote} content pack {pack_id}"

    def as_json(self) -> str:
        return self.model_dump_json(indent=2, exclude=NOT_PATCHED)

    def scenario(self, engine: EngineId, packs: tuple[Slug, ...] = ("srd",)) -> Scenario:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        if self.starting_location_id is None:
            raise ValueError("the draft has no `starting_location_id` yet")
        return Scenario(
            meta=self.meta,
            grows=self.grows,
            engine=engine,
            packs=(*packs, *self.packs),
            art_style=self.art_style,
            starting_location_id=self.starting_location_id,
            world=WorldState(
                entities=list(self.entities),
                threads=list(self.threads),
                party=list(self.starting_party),
            ),
        )


@dataclass(frozen=True, slots=True)
class PlaytestCheck:
    engine: Engine
    character: Character
    packs: tuple[Slug, ...]
    sources: PackSources = SHIPPED_PACKS

    def check(self, scenario: Scenario) -> None:
        # A playtest never saves, so the game's id is never read; any well-formed slug serves.
        _ = begin_game(self.engine, "draft", scenario, self.character)

    def shipping(self, drafted: Mapping[Slug, JsonValue]) -> "PlaytestCheck":
        """This check under an engine that also holds the packs a draft has written itself."""
        if not drafted:
            return self
        return replace(
            self, engine=build_engine(self.engine.id, replace(self.sources, drafted=drafted))
        )


def engine_packs(
    settings: Settings, engine_id: EngineId, scenario_id: Slug | None = None
) -> PackSources:
    """Installed user packs, then the packs one scenario ships; a run's own drafts join later."""
    beside = () if scenario_id is None else (scenario_packs(settings.scenarios_dir, scenario_id),)
    return PackSources((settings.packs_dir / engine_id, *beside))


def selected_packs(engine: Engine, packs: tuple[Slug, ...]) -> tuple[Slug, ...]:
    if "srd" not in packs:
        raise ValueError("scenario packs must include 'srd'")
    if len(packs) != len(set(packs)):
        raise ValueError("scenario pack ids must be unique")
    if missing := sorted(set(packs) - set(engine.pack_ids)):
        raise ValueError(f"packs not installed for {engine.id!r}: {missing}")
    return packs


def installed_pack_ids(settings: Settings, engine_id: EngineId) -> tuple[Slug, ...]:
    return build_engine(engine_id, engine_packs(settings, engine_id)).pack_ids


def playtest_check(
    settings: Settings, engine_id: EngineId, packs: tuple[Slug, ...] = ("srd",)
) -> PlaytestCheck:
    sources = engine_packs(settings, engine_id)
    engine = build_engine(engine_id, sources)
    chosen = selected_packs(engine, packs)
    character = load_character(
        settings.characters_dir,
        settings.authoring.starter_character,
        engine.id,
        engine.check_overlay,
    )
    return PlaytestCheck(engine=engine, character=character, packs=chosen, sources=sources)


MIN_LOCATIONS = 4
MIN_ACTORS = 2


def _bar_unmet(scenario: Scenario) -> list[str]:
    unmet: list[str] = []
    entities, threads = scenario.world.entities, scenario.world.threads
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
    if not any(
        entity.detail is not None and entity.detail.when_reached and not entity.known
        for entity in entities
    ):
        unmet.append(
            "at least one unknown entity whose `detail.when_reached` carries a consequence"
        )
    return unmet


MIN_OPENING_ENTITIES = 2


def _opening_unmet(scenario: Scenario) -> list[str]:
    unmet: list[str] = []
    beyond = [
        entity for entity in scenario.world.entities if entity.id != scenario.starting_location_id
    ]
    if len(beyond) < MIN_OPENING_ENTITIES:
        unmet.append(
            f"two or three entities besides the starting location; the draft has {len(beyond)}"
        )
    if not scenario.world.threads:
        unmet.append("at least one thread")
    return unmet


@dataclass(frozen=True, slots=True)
class AuthoringBrief:
    bar_prompt: str
    unmet: Callable[[Scenario], list[str]]
    label: str = ""
    settled: frozenset[str] = frozenset()
    # A pack ships in a scenario's own directory, which a world grown mid-game no longer writes.
    writes_packs: bool = True


WHOLE_SCENARIO = AuthoringBrief("scenario_bar.md", _bar_unmet, label="a whole scenario")
# An opening slice is deliberately thin: the rest of the world is written during play.
OPENING_SLICE = AuthoringBrief(
    "scenario_opening.md", _opening_unmet, label="an opening slice, grown in play"
)

BRIEFS: tuple[AuthoringBrief, ...] = (WHOLE_SCENARIO, OPENING_SLICE)


def brief_named(label: str) -> AuthoringBrief:
    return next(one for one in BRIEFS if one.label == label)


def extend_brief(before: WorldState) -> AuthoringBrief:
    held = {entity.id for entity in before.entities}

    def unmet(scenario: Scenario) -> list[str]:
        added = {
            entity.id
            for entity in scenario.world.entities
            if entity.kind == "location" and entity.id not in held
        }
        if not added:
            return ["at least one location the world did not already hold"]
        if not any(
            way.to in added
            for entity in scenario.world.entities
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
        settled=frozenset(held | {thread.id for thread in before.threads}),
        writes_packs=False,
    )


def scenario_refusal(
    draft: ScenarioDraft, playing: PlaytestCheck | None, brief: AuthoringBrief = WHOLE_SCENARIO
) -> str | None:
    if playing is None:
        return "no engine is loaded to play this draft against"
    try:
        playing = playing.shipping(draft.packs)
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


def pack_refusal(
    draft: ScenarioDraft,
    playing: PlaytestCheck,
    brief: AuthoringBrief,
    pack_id: Slug,
    content: dict[str, JsonValue],
) -> str | None:
    """Refused before the draft holds it, so a pack that cannot be played never lands."""
    if not brief.writes_packs:
        return (
            "a world grown in play cannot ship a content pack: the game is already running on "
            "the packs its scenario named. Write what this pass needs as entities, traits and "
            "threads instead."
        )
    if pack_id in playing.engine.pack_ids:
        return (
            f"{pack_id!r} is already installed for {playing.engine.id!r}. Give a pack of your own "
            "an id of its own, and write only what the selected packs lack."
        )
    try:
        _ = playing.engine.pack_type.model_validate(content)
        # Rebuilt whole, so a pack colliding with an installed one is refused here and not later.
        _ = playing.shipping({**draft.packs, pack_id: content})
    except ValueError as broken:
        return str(broken)
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
    source: Path | str,
) -> str:
    scenario = draft.scenario(engine, packs)
    write_scenario(settings.scenarios_dir, slug, scenario, draft.packs, source)
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
    scenario = load_scenario(settings.scenarios_dir, state.scenario_id)
    document = source_file(settings.scenarios_dir, state.scenario_id)
    given = given_text(settings, state.scenario.premise, document)
    packs = ", ".join(scenario.packs)
    return (
        f"{given}\n\nThis scenario is authored against these content packs: {packs}."
        "\n\nExtend the world `scenario_so_far` holds."
    )


def extension_patch(before: WorldState, after: ScenarioDraft) -> ExtensionPatch:
    held = {entity.id: entity for entity in before.entities}
    opened = {thread.id for thread in before.threads}
    return ExtensionPatch(
        entities=tuple(entity for entity in after.entities if entity.id not in held),
        exits=tuple(
            ExitLink(location_id=entity.id, to=way.to, locked=way.locked)
            for entity in after.entities
            if (was := held.get(entity.id)) is not None
            for way in entity.exits
            if was.exit_to(way.to) is None
        ),
        threads=tuple(thread for thread in after.threads if thread.id not in opened),
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
    draft.world.threads.append(thread.model_copy(deep=True))
    return _materialized(f"thread {thread.id}")


def _materialized(what: str) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}")
