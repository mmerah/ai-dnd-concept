from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import Field, JsonValue
from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput, UsageLimits
from pydantic_ai.messages import ModelMessage
from pydantic_ai.toolsets import FunctionToolset

from aidm.app.launch import begin_game, build_engine
from aidm.config import Settings
from aidm.content.io import (
    engine_text,
    load_character,
    load_scenario,
    source_file,
    whole_text,
    write_scenario,
)
from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine
from aidm.llm import build_agent
from aidm.state.model import (
    PLAYER_ID,
    EngineId,
    Entity,
    EntityId,
    Exit,
    Fact,
    Frozen,
    Game,
    Mutable,
    ScenarioMeta,
    Slug,
    Thread,
    WorldState,
)


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
    """One pass over the draft. A set field replaces its value; an element whose id the draft
    already holds is replaced whole; `remove` drops ids from whichever collection holds them."""

    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] | None = None
    art_style: str | None = Field(
        default=None,
        description=(
            "One line of visual direction for this scenario's illustrations — palette, medium "
            "and mood, written from the tone of the source or premise. Left unset, the app's "
            "default style is used."
        ),
    )
    entities: tuple[Entity, ...] = ()
    threads: tuple[Thread, ...] = ()
    remove: tuple[str, ...] = ()


class WorldDraft(Mutable):
    """The scenario under authorship, flat in `ScenarioPatch` vocabulary until `scenario()`."""

    grows: bool = False
    art_style: str = ""
    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)

    @classmethod
    def of(cls, scenario: Scenario) -> "WorldDraft":
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
    def of_game(cls, state: Game) -> "WorldDraft":
        """The live world as a draft, minus the player, what they carry, and any party member
        play has sent away from their side — all things a `Scenario` refuses."""
        world = state.world
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
                if PLAYER_ID not in (entity.id, entity.parent_id)
            ],
            threads=[thread.model_copy(deep=True) for thread in world.threads],
        )

    def apply(self, patch: ScenarioPatch) -> str:
        changed: list[str] = []
        if patch.meta is not None:
            self.meta = patch.meta
            changed.append("set meta")
        if patch.starting_location_id is not None:
            self.starting_location_id = patch.starting_location_id
            changed.append("set starting_location_id")
        if patch.starting_party is not None:
            self.starting_party = patch.starting_party
            changed.append("set starting_party")
        if patch.art_style is not None:
            self.art_style = patch.art_style
            changed.append("set art_style")
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

    def as_json(self) -> str:
        return self.model_dump_json(indent=2, exclude={"grows"})

    def scenario(self, engines: tuple[EngineId, ...]) -> Scenario:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        if self.starting_location_id is None:
            raise ValueError("the draft has no `starting_location_id` yet")
        return Scenario(
            meta=self.meta,
            grows=self.grows,
            engines=engines,
            art_style=self.art_style,
            starting_location_id=self.starting_location_id,
            world=WorldState(
                entities=list(self.entities),
                threads=list(self.threads),
                party=list(self.starting_party),
            ),
        )


# Every generated scenario must be playable by the character the app ships with.
STARTER = "kael"

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_BASE_INSTRUCTIONS = engine_text(_PROMPTS_DIR / "scenario_world.md")


def _instructions(bar: str) -> str:
    return f"{_BASE_INSTRUCTIONS}\n\n{engine_text(_PROMPTS_DIR / bar)}"


@dataclass(frozen=True, slots=True)
class Playtest:
    engine: Engine
    character: Character

    def check(self, scenario: Scenario) -> None:
        # A playtest never saves, so the game's id is never read; any well-formed slug serves.
        _ = begin_game(self.engine, "draft", scenario, self.character)


def playtests(config: Settings, engines: Sequence[EngineId]) -> tuple[Playtest, ...]:
    built: list[Playtest] = []
    for engine_id in engines:
        engine = build_engine(engine_id)
        character = load_character(config.characters_dir, STARTER, engine.id, engine.check_overlay)
        built.append(Playtest(engine=engine, character=character))
    return tuple(built)


def _bar_unmet(scenario: Scenario) -> list[str]:
    """The bar the instructions set, checked mechanically — every unmet item found at once."""
    unmet: list[str] = []
    entities, threads = scenario.world.entities, scenario.world.threads
    locations = sorted(entity.id for entity in entities if entity.kind == "location")
    if len(locations) < 4:
        unmet.append(f"four or more locations; the draft has {len(locations)}: {locations}")
    ways = [way for entity in entities for way in entity.exits]
    if all(way.known for way in ways):
        unmet.append("at least one exit starting `known: false` — a way to find")
    if not any(way.locked for way in ways):
        unmet.append("at least one exit starting `locked: true`")
    actors = [entity for entity in entities if entity.kind == "actor"]
    if len(actors) < 2:
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


def _opening_unmet(scenario: Scenario) -> list[str]:
    """An opening slice's bar: what the first scene needs, since the rest materializes in play."""
    unmet: list[str] = []
    beyond = [
        entity for entity in scenario.world.entities if entity.id != scenario.starting_location_id
    ]
    if len(beyond) < 2:
        unmet.append(
            f"two or three entities besides the starting location; the draft has {len(beyond)}"
        )
    if not scenario.world.threads:
        unmet.append("at least one thread")
    return unmet


@dataclass(frozen=True, slots=True)
class Brief:
    """How much world one run authors: the instructions it works from and the bar it is held to."""

    instructions: str
    unmet: Callable[[Scenario], list[str]]


FULL = Brief(_instructions("scenario_bar.md"), _bar_unmet)
# An opening slice is deliberately thin: the rest of the world is written during play.
OPENING = Brief(_instructions("scenario_opening.md"), _opening_unmet)


def extend_brief(before: WorldState) -> Brief:
    """A brief bound to the world it extends: what counts as new is only meaningful against what
    already existed."""
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

    return Brief(_instructions("scenario_extend.md"), unmet)


def playability(draft: WorldDraft, playing: Sequence[Playtest], brief: Brief = FULL) -> str | None:
    """The exact reason the draft will not play, or None; ValidationError counts as ValueError."""
    try:
        scenario = draft.scenario(tuple(playtest.engine.id for playtest in playing))
        for playtest in playing:
            playtest.check(scenario)
    except ValueError as refused:
        return str(refused)
    if unmet := brief.unmet(scenario):
        listed = "\n".join(f"- {item}" for item in unmet)
        return f"the draft plays, but it is under the bar. Still missing:\n{listed}"
    return None


# An author works in passes; past REQUEST_LIMIT calls the run is spinning, not authoring.
REQUEST_LIMIT = 40
WORKED_EXAMPLE = "whispering-vault"


def authoring_toolset(
    playing: Sequence[Playtest],
    config: Settings,
    brief: Brief = FULL,
) -> FunctionToolset[WorldDraft]:
    def worked_example() -> str:
        """The shipped scenario in the draft shape patches are written in: the bar to match."""
        return WorldDraft.of(load_scenario(config.scenarios_dir, WORKED_EXAMPLE)).as_json()

    def scenario_so_far(ctx: RunContext[WorldDraft]) -> str:
        """The whole draft as it stands, as pretty JSON: read it back before modifying or
        removing anything, so every id you name is one it actually holds."""
        return ctx.deps.as_json()

    def write(ctx: RunContext[WorldDraft], patch: ScenarioPatch) -> str:
        """Apply one patch to the draft. An element whose id the draft already holds is replaced
        whole, so send the complete element when modifying one; `remove` drops ids from whichever
        collection holds them. Returns each change as `created|modified|deleted kind name[id]`."""
        try:
            return ctx.deps.apply(patch)
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def validate_scenario(ctx: RunContext[WorldDraft]) -> str:
        """Whether the draft plays: 'ok', or the exact reason it will not. Fix what it names and
        call it again; the scenario is only done once it answers 'ok'."""
        return playability(ctx.deps, playing, brief) or "ok"

    return FunctionToolset(tools=[worked_example, scenario_so_far, write, validate_scenario])


def world_agent(
    playing: Sequence[Playtest],
    config: Settings,
    brief: Brief = FULL,
) -> Agent[WorldDraft, str]:
    """Ends on the `finish` tool, not bare text: a tool-only author would never end its own turn."""

    def playable(ctx: RunContext[WorldDraft], summary: str) -> str:
        if reason := playability(ctx.deps, playing, brief):
            raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")
        return summary

    return build_agent(
        "scenario_creator",
        config,
        instructions=brief.instructions,
        output_type=ToolOutput(
            str,
            name="finish",
            description=(
                "End authorship. Call this only once `validate_scenario` answers ok; its argument "
                "is two or three sentences on what you authored."
            ),
        ),
        deps_type=WorldDraft,
        toolsets=[authoring_toolset(playing, config, brief)],
        validator=playable,
    )


def world_prompt(slug: Slug, premise: str, sourced: bool) -> str:
    heading = "SOURCE DOCUMENT:" if sourced else "PREMISE:"
    return f"{heading}\n{premise}\n\nWill be saved as: {slug!r}"


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


async def author_extension(
    config: Settings,
    engine: Engine,
    character: Character,
    state: Game,
) -> ExtensionPatch:
    """One authoring run against the live world, answered as the canon it added. The `finish`
    validator refuses an unplayable draft inside the run, so there is no outer retry loop."""
    document = source_file(config.scenarios_dir, state.scenario_id)
    draft = WorldDraft.of_game(state)
    playing = (Playtest(engine=engine, character=character),)
    agent = world_agent(playing, config, extend_brief(state.world))
    given = state.scenario.premise if document is None else whole_text(document)
    heading = "PREMISE:" if document is None else "SOURCE DOCUMENT:"
    _ = await agent.run(
        f"{heading}\n{given}\n\nExtend the world `scenario_so_far` holds.",
        deps=draft,
        usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
    )
    return delta(state.world, draft)


def delta(before: WorldState, after: WorldDraft) -> ExtensionPatch:
    """What an extension pass added. Add-only: a change to canon that already existed is ignored,
    except a new way out of it, which is how new canon is reached at all."""
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
    """The one place a patch reaches the world: add-only, unknown, and refused whole on any id the
    draft already holds."""
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
    return _materialized(
        f"way from {here.id} to {link.to}", {"location_id": here.id, "to_id": link.to}
    )


def _opened(draft: Game, thread: Thread) -> Fact:
    if draft.world.thread(thread.id) is not None:
        raise ValueError(f"a thread {thread.id!r} already exists")
    draft.world.threads.append(thread.model_copy(deep=True))
    return _materialized(f"thread {thread.id}", {"thread_id": thread.id})


def _materialized(what: str, data: dict[str, JsonValue]) -> Fact:
    """Private canon coming into being is not a fictional event, so it narrates nothing."""
    return Fact(kind="canon_materialized", trace=f"materialized {what}", data=data)


@dataclass
class AuthoringSession:
    """One scenario under authorship across many agent runs; only `write` reaches disk."""

    slug: Slug
    premise: str
    config: Settings
    grows: bool
    engines: tuple[EngineId, ...]
    art_style: str = ""
    document: Path | None = None
    brief: Brief = FULL
    history: list[ModelMessage] = field(default_factory=list)
    busy: bool = False
    playing: tuple[Playtest, ...] = field(init=False)
    agent: Agent[WorldDraft, str] = field(init=False)
    draft: WorldDraft = field(init=False)
    opening_prompt: str = field(init=False)

    def __post_init__(self) -> None:
        if self.document is None and not self.premise:
            raise ValueError("give a premise, a document, or both: there is nothing to author from")
        if (self.config.scenarios_dir / self.slug).exists():
            raise ValueError(f"scenario {self.slug!r} already exists")
        self.playing = playtests(self.config, self.engines)
        self.agent = world_agent(self.playing, self.config, self.brief)
        self.draft = WorldDraft(grows=self.grows)
        given = self.premise if self.document is None else whole_text(self.document)
        self.opening_prompt = world_prompt(self.slug, given, self.document is not None)

    async def send(self, instruction: str) -> str:
        """One agent turn against the same draft and the same history."""
        result = await self.agent.run(
            instruction,
            deps=self.draft,
            message_history=self.history,
            usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
        )
        self.history = list(result.all_messages())
        return result.output

    def refusal(self) -> str | None:
        return playability(self.draft, self.playing, self.brief)

    async def write(self) -> str:
        """Revalidates the draft — the agent's 'ok' is never trusted — before it reaches disk."""
        if reason := self.refusal():
            raise ValueError(f"the draft does not play: {reason}")
        # The form's style overrides whatever the author wrote from the source's own tone.
        self.draft.art_style = self.art_style or self.draft.art_style
        scenario = self.draft.scenario(self.engines)
        write_scenario(
            self.config.scenarios_dir, self.slug, scenario, self.document or self.premise
        )
        return summarize(scenario)
