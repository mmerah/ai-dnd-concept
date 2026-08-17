import asyncio
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import NoneType

from pydantic import Field, JsonValue
from pydantic_ai import (
    ModelRetry,
    NativeOutput,
    RunContext,
    ToolOutput,
    UnexpectedModelBehavior,
    UsageLimits,
)
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.toolsets import FunctionToolset

from aidm.config import Settings, load_settings
from aidm.content.authored import (
    Character,
    Scenario,
    ScenarioOverlay,
    ScenarioWorld,
    check_hooks,
)
from aidm.content.store import ENCODING, WORLD_FILE, engine_text, load_character, write_scenario
from aidm.engines.loader import Engine, engine_ids
from aidm.engines.sheets import SheetBase
from aidm.engines.vocabulary import WORLD_CALLS, card
from aidm.state.base import EngineId, Entity, EntityId, Frozen, RelationId, Slug, content_id
from aidm.state.world import CONNECTED, LOCKED_TAG, Hook, Memory, Relation, ScenarioMeta, Thread
from aidm.turn.roles import Stage

from .session import begin_game, build_engine

ROUNDS = 3
# An author works in passes: example, several writes, read-backs, validation fixes. This is room
# for all of that; past it the run is spinning, not authoring.
REQUEST_LIMIT = 40
WORKED_EXAMPLE = "whispering-vault"
# Every generated scenario must be playable by the character the app ships with.
STARTER = "kael"
HOOK_EFFECTS_CARD = (
    "What a hook's `effects` may name, and the `args` each one takes. A hook writes only these: "
    "one `world.json` is loaded by every ruleset, so an effect belonging to one engine would "
    "refuse the others."
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

WORLD_INSTRUCTIONS = (
    f"{engine_text(_PROMPTS_DIR / 'scenario_world.md')}\n\n"
    f"{card('Hook effects', HOOK_EFFECTS_CARD, WORLD_CALLS)}"
)
OVERLAY_INSTRUCTIONS = engine_text(_PROMPTS_DIR / "scenario_overlay.md")


class TypedOverlay[S: SheetBase](Frozen):
    entities: dict[EntityId, S] = Field(default_factory=dict)


class ScenarioPatch(Frozen):
    """One pass over the draft. A set field replaces its value; an element whose id the draft
    already holds is replaced whole; `remove` drops ids from whichever collection holds them."""

    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] | None = None
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    threads: tuple[Thread, ...] = ()
    memories: tuple[Memory, ...] = ()
    hooks: tuple[Hook, ...] = ()
    remove: tuple[str, ...] = ()


@dataclass
class WorldDraft:
    """The scenario under authorship: mutated only by `apply`, judged only by `world()`."""

    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: dict[EntityId, Entity] = field(default_factory=dict)
    relations: dict[RelationId, Relation] = field(default_factory=dict)
    threads: dict[Slug, Thread] = field(default_factory=dict)
    memories: dict[Slug, Memory] = field(default_factory=dict)
    hooks: dict[Slug, Hook] = field(default_factory=dict)

    def apply(self, patch: ScenarioPatch) -> str:
        changed: list[str] = []
        if patch.meta is not None:
            self.meta = patch.meta
            changed.append("meta")
        if patch.starting_location_id is not None:
            self.starting_location_id = patch.starting_location_id
            changed.append("starting_location_id")
        if patch.starting_party is not None:
            self.starting_party = patch.starting_party
            changed.append("starting_party")
        for entity in patch.entities:
            self.entities[entity.id] = entity
        for relation in patch.relations:
            self.relations[relation.id] = relation
        for thread in patch.threads:
            self.threads[thread.id] = thread
        for memory in patch.memories:
            self.memories[memory.id] = memory
        for hook in patch.hooks:
            self.hooks[hook.id] = hook
        counts = {
            "entities": len(patch.entities),
            "relations": len(patch.relations),
            "threads": len(patch.threads),
            "memories": len(patch.memories),
            "hooks": len(patch.hooks),
        }
        changed.extend(f"{count} {what}" for what, count in counts.items() if count)
        for target in patch.remove:
            self._remove(target)
        if patch.remove:
            changed.append(f"removed {len(patch.remove)}")
        return f"wrote: {', '.join(changed)}" if changed else "nothing to change"

    def _remove(self, target: str) -> None:
        if target in self.entities:
            del self.entities[EntityId(target)]
        elif target in self.relations:
            del self.relations[RelationId(target)]
        elif target in self.threads:
            del self.threads[target]
        elif target in self.memories:
            del self.memories[target]
        elif target in self.hooks:
            del self.hooks[target]
        else:
            raise ValueError(
                f"nothing in the draft has id {target!r}; read `scenario_so_far` and remove ids "
                "exactly as it spells them"
            )

    def world(self) -> ScenarioWorld:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        if self.starting_location_id is None:
            raise ValueError("the draft has no `starting_location_id` yet")
        return ScenarioWorld(
            meta=self.meta,
            starting_location_id=self.starting_location_id,
            starting_party=self.starting_party,
            entities=tuple(self.entities.values()),
            relations=tuple(self.relations.values()),
            threads=tuple(self.threads.values()),
            memories=tuple(self.memories.values()),
            hooks=tuple(self.hooks.values()),
        )

    def pretty(self) -> str:
        # Not `world()`: a draft mid-authorship is legitimately incomplete, and reading it back is
        # most needed exactly when it will not yet build.
        body: dict[str, JsonValue] = {
            "meta": None if self.meta is None else self.meta.model_dump(mode="json"),
            "starting_location_id": self.starting_location_id,
            "starting_party": list(self.starting_party),
            "entities": [entity.model_dump(mode="json") for entity in self.entities.values()],
            "relations": [relation.model_dump(mode="json") for relation in self.relations.values()],
            "threads": [thread.model_dump(mode="json") for thread in self.threads.values()],
            "memories": [memory.model_dump(mode="json") for memory in self.memories.values()],
            "hooks": [hook.model_dump(mode="json") for hook in self.hooks.values()],
        }
        return json.dumps(body, indent=2)


@dataclass(frozen=True, slots=True)
class Playtest:
    engine: Engine[SheetBase]
    character: Character

    def check(self, slug: Slug, world: ScenarioWorld, overlay: ScenarioOverlay) -> None:
        scenario = Scenario(id=slug, engine=self.engine.id, world=world, overlay=overlay)
        check_hooks(world, self.engine.binding())
        self.engine.check_overlay(overlay.entities.values())
        _ = begin_game(self.engine, scenario, self.character)


def playtests(config: Settings) -> tuple[Playtest, ...]:
    built: list[Playtest] = []
    for engine_id in engine_ids():
        engine = build_engine(engine_id)
        character = load_character(config.characters_dir, STARTER, engine.binding())
        built.append(Playtest(engine=engine, character=character))
    return tuple(built)


def _advances_on_discovery(hook: Hook) -> bool:
    return hook.match.kind == "entity_discovered" and any(
        isinstance(effect, dict) and effect.get("name") == "advance-thread"
        for effect in hook.effects
    )


def _bar_unmet(world: ScenarioWorld) -> list[str]:
    """The bar the instructions set, checked mechanically — every unmet item at once, so the
    author fixes them in one pass instead of one refusal each."""
    unmet: list[str] = []
    locations = sorted(entity.id for entity in world.entities if entity.kind == "location")
    if len(locations) < 4:
        unmet.append(f"four or more locations; the draft has {len(locations)}: {locations}")
    ways = [relation for relation in world.relations if relation.kind == CONNECTED]
    if all(way.known for way in ways):
        unmet.append("at least one `connected` relation starting `known: false` — a way to find")
    if not any(LOCKED_TAG in way.tags for way in ways):
        unmet.append(f"at least one `connected` relation tagged {LOCKED_TAG!r}")
    actors = [entity for entity in world.entities if entity.kind == "actor"]
    if len(actors) < 2:
        actor_ids = sorted(actor.id for actor in actors)
        unmet.append(f"two or more actors; the draft has {len(actors)}: {actor_ids}")
    if all(actor.known for actor in actors):
        unmet.append("at least one actor starting `known: false`")
    if not any(entity.kind == "item" and not entity.known for entity in world.entities):
        unmet.append("at least one item starting `known: false` — a secret to find")
    if not world.threads:
        unmet.append("at least one thread")
    if not any(_advances_on_discovery(hook) for hook in world.hooks):
        unmet.append("at least one hook that advances a thread on an `entity_discovered` fact")
    return unmet


def playability(draft: WorldDraft, slug: Slug, playing: Sequence[Playtest]) -> str | None:
    """The exact reason the draft will not play, or None. Building the `ScenarioWorld` is the
    structural check; pydantic's ValidationError is a ValueError, so one except covers both."""
    try:
        world = draft.world()
        for playtest in playing:
            playtest.check(slug, world, ScenarioOverlay())
    except ValueError as refused:
        return str(refused)
    if unmet := _bar_unmet(world):
        listed = "\n".join(f"- {item}" for item in unmet)
        return f"the draft plays, but it is under the bar. Still missing:\n{listed}"
    return None


async def ask_until_playable[T](
    stage: Stage[NoneType, T], prompt: str, check: Callable[[T], None]
) -> T:
    """`check` raises ValueError; the reason goes back to the author, up to ROUNDS times."""
    history: list[ModelMessage] = []
    ask = prompt
    reason = ""
    for _ in range(ROUNDS):
        result = await stage.agent.run(ask, deps=None, message_history=history)
        try:
            check(result.output)
        except ValueError as refused:
            reason = str(refused)
            history = list(result.all_messages())
            ask = f"That will not play:\n\n{reason}\n\nWrite the whole answer again, fixed."
            continue
        return result.output
    raise ValueError(f"no playable answer in {ROUNDS} rounds. Last refusal: {reason}")


def authoring_toolset(
    slug: Slug, playing: Sequence[Playtest], config: Settings
) -> FunctionToolset[WorldDraft]:
    def worked_example() -> str:
        """The shipped scenario's world.json: the format and the quality bar to match."""
        return (config.scenarios_dir / WORKED_EXAMPLE / WORLD_FILE).read_text(encoding=ENCODING)

    def scenario_so_far(ctx: RunContext[WorldDraft]) -> str:
        """The whole draft as it stands, as pretty JSON: read it back before modifying or
        removing anything, so every id you name is one it actually holds."""
        return ctx.deps.pretty()

    def write(ctx: RunContext[WorldDraft], patch: ScenarioPatch) -> str:
        """Apply one patch to the draft. An element whose id the draft already holds is replaced
        whole, so send the complete element when modifying one; `remove` drops ids from whichever
        collection holds them. Returns a short summary of what changed."""
        try:
            return ctx.deps.apply(patch)
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def validate_scenario(ctx: RunContext[WorldDraft]) -> str:
        """Whether the draft plays: 'ok', or the exact reason it will not. Fix what it names and
        call it again; the scenario is only done once it answers 'ok'."""
        return playability(ctx.deps, slug, playing) or "ok"

    return FunctionToolset(tools=[worked_example, scenario_so_far, write, validate_scenario])


def world_stage(
    slug: Slug, playing: Sequence[Playtest], config: Settings
) -> Stage[WorldDraft, str]:
    """The run ends on the `finish` tool, not on bare text: an author that only ever calls tools
    would otherwise never end its own turn."""

    def playable(ctx: RunContext[WorldDraft], summary: str) -> str:
        if reason := playability(ctx.deps, slug, playing):
            raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")
        return summary

    return Stage.of(
        "scenario_creator",
        config,
        instructions=WORLD_INSTRUCTIONS,
        output_type=ToolOutput(
            str,
            name="finish",
            description=(
                "End authorship. Call this only once `validate_scenario` answers ok; its argument "
                "is two or three sentences on what you authored."
            ),
        ),
        deps_type=WorldDraft,
        toolsets=[authoring_toolset(slug, playing, config)],
        validator=playable,
    )


def overlay_stage(
    engine: Engine[SheetBase], config: Settings
) -> Stage[NoneType, TypedOverlay[SheetBase]]:
    model = TypedOverlay[engine.sheet_type]  # pyright: ignore[reportUnknownVariableType]
    return Stage.of(
        "scenario_creator",
        config,
        instructions=OVERLAY_INSTRUCTIONS,
        output_type=NativeOutput(model),
        deps_type=NoneType,
    )


def _world_prompt(slug: Slug, premise: str) -> str:
    return f"PREMISE:\n{premise}\n\nWill be saved as: {slug!r}"


async def authored_world(
    stage: Stage[WorldDraft, str], slug: Slug, premise: str, playing: Sequence[Playtest]
) -> ScenarioWorld:
    """The agent authors into the draft; the draft, revalidated here, is the deliverable —
    the agent saying 'ok' is never trusted."""
    draft = WorldDraft()
    _ = await stage.agent.run(
        _world_prompt(slug, premise),
        deps=draft,
        usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
    )
    if reason := playability(draft, slug, playing):
        raise ValueError(f"the author stopped on an unplayable draft: {reason}")
    return draft.world()


def _overlay_prompt(engine: Engine[SheetBase], world: ScenarioWorld, config: Settings) -> str:
    example = engine_text(config.scenarios_dir / WORKED_EXAMPLE / f"{engine.id}.json")
    return (
        f"ENGINE:\n{engine.id}\n\n"
        f"WORLD:\n{world.model_dump_json(indent=2)}\n\n"
        f"WORKED EXAMPLE:\n{example}"
    )


def _as_overlay(typed: TypedOverlay[SheetBase]) -> ScenarioOverlay:
    return ScenarioOverlay(
        entities={
            entity_id: sheet.model_dump(mode="json", exclude_defaults=True)
            for entity_id, sheet in typed.entities.items()
        }
    )


async def _authored_overlay(
    playtest: Playtest, slug: Slug, world: ScenarioWorld, config: Settings
) -> ScenarioOverlay:
    engine = playtest.engine

    def check(typed: TypedOverlay[SheetBase]) -> None:
        playtest.check(slug, world, _as_overlay(typed))

    typed = await ask_until_playable(
        overlay_stage(engine, config), _overlay_prompt(engine, world, config), check
    )
    return _as_overlay(typed)


async def author_scenario(
    slug: Slug, premise: str, config: Settings
) -> tuple[ScenarioWorld, dict[EngineId, ScenarioOverlay]]:
    playing = playtests(config)
    world = await authored_world(world_stage(slug, playing, config), slug, premise, playing)
    overlays = {
        playtest.engine.id: await _authored_overlay(playtest, slug, world, config)
        for playtest in playing
    }
    return world, overlays


def summarize(world: ScenarioWorld, overlays: Mapping[EngineId, ScenarioOverlay]) -> str:
    lines = [
        world.meta.title,
        f"{len(world.entities)} entities, {len(world.relations)} relations, "
        f"{len(world.threads)} threads, {len(world.hooks)} hooks",
    ]
    for engine_id, overlay in overlays.items():
        lines.append(f"{engine_id}: {len(overlay.entities)} entities with mechanics")
    return "\n".join(lines)


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 2:
        raise SystemExit('usage: create_scenario.py <slug> "<premise>"')
    try:
        slug = content_id(args[0])
        config = load_settings()
        world, overlays = asyncio.run(author_scenario(slug, args[1], config))
        write_scenario(config.scenarios_dir, slug, world, overlays)
    except (ValueError, UnexpectedModelBehavior, UsageLimitExceeded) as refused:
        raise SystemExit(f"scenario not created: {refused}") from refused
    print(summarize(world, overlays))
