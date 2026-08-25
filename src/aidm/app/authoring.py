from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import Field, ValidationError
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


class ScenarioDraft(Mutable):
    """The scenario under authorship, flat in `ScenarioPatch` vocabulary until `scenario()`."""

    grows: bool = False
    art_style: str = ""
    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)

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
        """Exclude player-owned state because `Scenario` refuses it."""
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


_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True, slots=True)
class PlaytestCheck:
    engine: Engine
    character: Character

    def check(self, scenario: Scenario) -> None:
        # A playtest never saves, so the game's id is never read; any well-formed slug serves.
        _ = begin_game(self.engine, "draft", scenario, self.character)


def playtest_checks(settings: Settings, engines: Sequence[EngineId]) -> tuple[PlaytestCheck, ...]:
    built: list[PlaytestCheck] = []
    for engine_id in engines:
        engine = build_engine(engine_id)
        character = load_character(
            settings.characters_dir,
            settings.authoring.starter_character,
            engine.id,
            engine.check_overlay,
        )
        built.append(PlaytestCheck(engine=engine, character=character))
    return tuple(built)


MIN_LOCATIONS = 4
MIN_ACTORS = 2


def _bar_unmet(scenario: Scenario) -> list[str]:
    """The bar the instructions set, checked mechanically — every unmet item found at once."""
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
    """An opening slice's bar: what the first scene needs, since the rest materializes in play."""
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
    """How much world one run authors: the bar it is held to, and the canon it may not rewrite."""

    bar_prompt: str
    unmet: Callable[[Scenario], list[str]]
    settled: frozenset[str] = frozenset()


WHOLE_SCENARIO = AuthoringBrief("scenario_bar.md", _bar_unmet)
# An opening slice is deliberately thin: the rest of the world is written during play.
OPENING_SLICE = AuthoringBrief("scenario_opening.md", _opening_unmet)


def extend_brief(before: WorldState) -> AuthoringBrief:
    """Bind the extension bar to what the world already contains."""
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
        "scenario_extend.md", unmet, frozenset(held | {thread.id for thread in before.threads})
    )


def _instructions(settings: Settings, brief: AuthoringBrief) -> str:
    """The worked example rides in the prompt, so reading it costs no tool call."""
    example = ScenarioDraft.from_scenario(
        load_scenario(settings.scenarios_dir, settings.authoring.worked_example)
    ).as_json()
    return "\n\n".join(
        (
            engine_text(_PROMPTS_DIR / "scenario_world.md"),
            engine_text(_PROMPTS_DIR / brief.bar_prompt),
            engine_text(_PROMPTS_DIR / "scenario_example.md"),
            f"```json\n{example}\n```",
        )
    )


def scenario_refusal(
    draft: ScenarioDraft, playing: Sequence[PlaytestCheck], brief: AuthoringBrief = WHOLE_SCENARIO
) -> str | None:
    """The exact reason the draft will not play, or None; ValidationError counts as ValueError."""
    try:
        scenario = draft.scenario(tuple(playtest.engine.id for playtest in playing))
        for playtest in playing:
            playtest.check(scenario)
    except ValidationError as broken:
        return str(broken.errors()[0]["msg"])
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


def authoring_toolset(
    playing: Sequence[PlaytestCheck],
    brief: AuthoringBrief = WHOLE_SCENARIO,
) -> FunctionToolset[ScenarioDraft]:
    def answer(draft: ScenarioDraft, changed: str) -> str:
        standing = scenario_refusal(draft, playing, brief) or (
            "it plays. Read it back and judge it as a thing to play before you finish."
        )
        return f"{changed}\n\nDRAFT: {standing}"

    def scenario_so_far(ctx: RunContext[ScenarioDraft]) -> str:
        """Read the complete current draft as formatted JSON."""
        return ctx.deps.as_json()

    def write(ctx: RunContext[ScenarioDraft], patch: ScenarioPatch) -> str:
        """Apply one update and return the changes plus what the draft still needs."""
        if refused := patch_refusal(patch, brief.settled):
            raise ModelRetry(refused)
        try:
            return answer(ctx.deps, ctx.deps.apply(patch))
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def connect(
        ctx: RunContext[ScenarioDraft],
        from_id: EntityId,
        to_id: EntityId,
        known: bool = False,
        locked: bool = False,
        one_way: bool = False,
    ) -> str:
        """Connect two locations already in the draft.

        Args:
            from_id: Exact id of the first location.
            to_id: Exact id of the second location.
            known: Whether the player knows this route at the start.
            locked: Whether the route starts locked.
            one_way: Whether the route goes only from the first location to the second.
        """
        if {from_id, to_id} <= brief.settled:
            raise ModelRetry(
                f"{from_id!r} and {to_id!r} are both the live game's, and nothing here can take "
                "a way between them back. Join one of them to a location this pass wrote."
            )
        try:
            return answer(ctx.deps, ctx.deps.connect(from_id, to_id, known, locked, one_way))
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    return FunctionToolset(tools=[scenario_so_far, write, connect])


def scenario_agent(
    playing: Sequence[PlaytestCheck],
    settings: Settings,
    brief: AuthoringBrief = WHOLE_SCENARIO,
) -> Agent[ScenarioDraft, str]:
    """Ends on the `finish` tool, not bare text: a tool-only author would never end its own turn."""

    def playable(ctx: RunContext[ScenarioDraft], summary: str) -> str:
        if reason := scenario_refusal(ctx.deps, playing, brief):
            raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")
        return summary

    return build_agent(
        "scenario_creator",
        settings,
        instructions=_instructions(settings, brief),
        output_type=ToolOutput(
            str,
            name="finish",
            description="Finish a playable draft with a 2-3 sentence summary.",
        ),
        deps_type=ScenarioDraft,
        toolsets=[authoring_toolset(playing, brief)],
        validator=playable,
    )


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
    engines: tuple[EngineId, ...],
    source: Path | str,
) -> str:
    scenario = draft.scenario(engines)
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
    return f"{given}\n\nExtend the world `scenario_so_far` holds."


async def author_extension(
    settings: Settings,
    engine: Engine,
    character: Character,
    state: Game,
) -> ExtensionPatch:
    """Run once because `finish` retries unplayable drafts inside the agent run."""
    draft = ScenarioDraft.from_game(state)
    playing = (PlaytestCheck(engine=engine, character=character),)
    agent = scenario_agent(playing, settings, extend_brief(state.world))
    _ = await agent.run(
        extension_prompt(settings, state),
        deps=draft,
        usage_limits=UsageLimits(request_limit=settings.authoring.request_limit),
    )
    return extension_patch(state.world, draft)


def extension_patch(before: WorldState, after: ScenarioDraft) -> ExtensionPatch:
    """What the live world takes from the grown draft: new entities, new ways in, new threads."""
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
    """Materialize additions as unknown canon and refuse existing ids."""
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


@dataclass
class AuthoringSession:
    """One scenario under authorship across many agent runs; only `write` reaches disk."""

    slug: Slug
    premise: str
    settings: Settings
    grows: bool
    engines: tuple[EngineId, ...]
    art_style: str = ""
    document: Path | None = None
    brief: AuthoringBrief = WHOLE_SCENARIO
    history: list[ModelMessage] = field(default_factory=list)
    busy: bool = False
    playing: tuple[PlaytestCheck, ...] = field(init=False)
    agent: Agent[ScenarioDraft, str] = field(init=False)
    draft: ScenarioDraft = field(init=False)
    opening_prompt: str = field(init=False)

    def __post_init__(self) -> None:
        check_new_scenario(self.settings, self.slug, self.premise, self.document)
        self.playing = playtest_checks(self.settings, self.engines)
        self.agent = scenario_agent(self.playing, self.settings, self.brief)
        self.draft = ScenarioDraft(grows=self.grows)
        self.opening_prompt = world_prompt(self.settings, self.slug, self.premise, self.document)

    async def send(self, instruction: str) -> str:
        """One agent turn against the same draft and the same history."""
        result = await self.agent.run(
            instruction,
            deps=self.draft,
            message_history=self.history,
            usage_limits=UsageLimits(request_limit=self.settings.authoring.request_limit),
        )
        self.history = list(result.all_messages())
        return result.output

    def refusal(self) -> str | None:
        return scenario_refusal(self.draft, self.playing, self.brief)

    async def write(self) -> str:
        """Revalidates the draft — the agent's 'ok' is never trusted — before it reaches disk."""
        if reason := self.refusal():
            raise ValueError(f"the draft does not play: {reason}")
        # The form's style overrides whatever the author wrote from the source's own tone.
        self.draft.art_style = self.art_style or self.draft.art_style
        return write_draft(
            self.settings, self.slug, self.draft, self.engines, self.document or self.premise
        )


@dataclass
class AuthoringRun:
    """One draft under authorship in the MCP server, held between tool calls."""

    draft: ScenarioDraft
    playing: tuple[PlaytestCheck, ...]
    brief: AuthoringBrief
    toolset: FunctionToolset[ScenarioDraft]

    def refusal(self) -> str | None:
        return scenario_refusal(self.draft, self.playing, self.brief)


@dataclass
class GrowthRun(AuthoringRun):
    """Grows a world in play; `base` is the state the finished draft is diffed against."""

    base: Game

    def patch(self) -> ExtensionPatch:
        return extension_patch(self.base.world, self.draft)


@dataclass
class ScenarioRun(AuthoringRun):
    """Writes a whole new scenario; needs no open game."""

    settings: Settings
    slug: Slug
    premise: str
    document: Path | None
    engines: tuple[EngineId, ...]

    def write(self) -> str:
        return write_draft(
            self.settings, self.slug, self.draft, self.engines, self.document or self.premise
        )


_HOW_TO_WORK = (
    "Write with `write`, join locations with `connect`, and read the whole draft back with "
    "`scenario_so_far` whenever you have lost track of it. Each answer ends with what the draft "
    "still needs. Call `{finish}` with a two or three sentence summary once it plays."
)


def _briefing(settings: Settings, brief: AuthoringBrief, prompt: str, finish: str) -> str:
    return "\n\n".join((_instructions(settings, brief), prompt, _HOW_TO_WORK.format(finish=finish)))


def growth_run(
    settings: Settings, engine: Engine, character: Character, state: Game
) -> tuple[GrowthRun, str]:
    brief = extend_brief(state.world)
    playing = (PlaytestCheck(engine=engine, character=character),)
    run = GrowthRun(
        draft=ScenarioDraft.from_game(state),
        playing=playing,
        brief=brief,
        toolset=authoring_toolset(playing, brief),
        base=state,
    )
    return run, _briefing(settings, brief, extension_prompt(settings, state), "finish_growth")


def scenario_run(
    settings: Settings,
    slug: Slug,
    premise: str,
    grows: bool,
    engines: Sequence[EngineId],
    document: Path | None,
) -> tuple[ScenarioRun, str]:
    check_new_scenario(settings, slug, premise, document)
    brief = OPENING_SLICE if grows else WHOLE_SCENARIO
    playing = playtest_checks(settings, engines)
    run = ScenarioRun(
        draft=ScenarioDraft(grows=grows),
        playing=playing,
        brief=brief,
        toolset=authoring_toolset(playing, brief),
        settings=settings,
        slug=slug,
        premise=premise,
        document=document,
        engines=tuple(engines),
    )
    prompt = world_prompt(settings, slug, premise, document)
    return run, _briefing(settings, brief, prompt, "finish_scenario")
