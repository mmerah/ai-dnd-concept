import re
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, JsonValue, ValidationError
from pypdf import PdfReader

from aidm.config import Settings
from aidm.content.io import load_character, source_file, write_scenario
from aidm.content.model import AuthoringBrief, Character, Scenario, ScenarioPayload
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId, Frozen, Mutable, Slug
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


class Draft(Mutable):
    art_style: str = ""
    meta: ScenarioMeta | None = None
    player_parent_id: EntityId | None = None
    world: WorldState = Field(default_factory=WorldState)

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> "Draft":
        return cls(
            art_style=scenario.art_style,
            meta=scenario.meta,
            player_parent_id=scenario.player_parent_id,
            world=deepcopy(scenario.world),
        )

    @classmethod
    def from_game(cls, state: Game) -> "Draft":
        """Exclude played-character state: `Scenario` refuses the reserved player id."""
        world = state.world
        played = {PLAYER_ID, state.player_id}
        # Growth is rooms-only: an engine whose player stands nowhere cannot be extended.
        here = player_location(state)
        return cls(
            meta=state.scenario,
            player_parent_id=here,
            world=WorldState(
                entities={
                    entity_id: deepcopy(entity)
                    for entity_id, entity in world.entities.items()
                    if played.isdisjoint({entity.id, entity.parent_id})
                },
                threads=deepcopy(world.threads),
                party=[member for member in world.party if world.require(member).parent_id == here],
                mechanics=deepcopy(world.mechanics),
            ),
        )

    def apply(self, patch: ScenarioPatch, engine: Engine) -> str:
        # Every refusal runs before the first write, so a rejected patch leaves the draft whole.
        removing = [self._require_held(target) for target in patch.remove]
        gone = tuple(one.id for one in removing if isinstance(one, Entity))
        mechanics = engine.mechanics_patch(self.world.mechanics, patch.mechanics, gone)
        changed: list[str] = []
        party = patch.starting_party
        for name in patch.scenario_wide():
            if name == "starting_party" and party is not None:
                self.world.party = list(party)
            else:
                setattr(self, name, getattr(patch, name))
            changed.append(f"set {name}")
        for entity in patch.entities:
            verb = "modified" if entity.id in self.world.entities else "created"
            changed.append(_describe(entity, verb))
            self.world.entities[entity.id] = entity
        for thread in patch.threads:
            verb = "modified" if thread.id in self.world.threads else "created"
            changed.append(_describe(thread, verb))
            self.world.threads[thread.id] = thread
        if patch.mechanics:
            changed.append("set mechanics")
        if patch.mechanics or gone:
            self.world.mechanics = mechanics
        changed.extend(self._remove(one) for one in removing)
        return "\n".join(changed) if changed else "nothing to change"

    def _require_held(self, target: str) -> Entity | Thread:
        held: Entity | Thread | None = self.world.entities.get(EntityId(target))
        if held is None:
            held = self.world.threads.get(target)
        if held is None:
            raise ValueError(
                f"nothing in the draft has id {target!r}; read `scenario_so_far` and remove ids "
                "exactly as it spells them"
            )
        return held

    def _remove(self, held: Entity | Thread) -> str:
        if isinstance(held, Entity):
            _ = self.world.entities.pop(held.id, None)
        else:
            _ = self.world.threads.pop(held.id, None)
        return _describe(held, "deleted")

    def as_patch(self) -> ScenarioPatch:
        """The one shape the model reads and writes, so the example never teaches a refusal."""
        return ScenarioPatch(
            meta=self.meta,
            player_parent_id=self.player_parent_id,
            starting_party=tuple(self.world.party),
            art_style=self.art_style,
            entities=tuple(self.world.entities.values()),
            threads=tuple(self.world.threads.values()),
            mechanics=self.world.mechanics,
        )

    def as_json(self) -> str:
        return self.as_patch().model_dump_json(indent=2)

    def scenario(self, engine: EngineId, packs: tuple[Slug, ...], grows: bool = False) -> Scenario:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        return Scenario(
            meta=self.meta,
            grows=grows,
            engine=engine,
            packs=packs,
            art_style=self.art_style,
            payload=ScenarioPayload(
                player_parent_id=self.player_parent_id,
                # Dict writes on the draft's world skip validation; revalidating here is the gate.
                world=WorldState.model_validate(self.world.model_dump(round_trip=True)),
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
    selected = packs or (next(iter(engine.packs)),)
    character = load_character(
        settings.characters_dir, settings.authoring.starter_character, engine
    )
    return PlaytestCheck(engine=engine, character=character, packs=selected)


def scenario_refusal(draft: Draft, playing: PlaytestCheck, brief: AuthoringBrief) -> str | None:
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
    if whole := {key for key, value in patch.mechanics.items() if not isinstance(value, dict)}:
        return f"a scenario already in play keeps its {', '.join(sorted(whole))}"
    written = {
        name for value in patch.mechanics.values() if isinstance(value, dict) for name in value
    }
    held = {item.id for item in (*patch.entities, *patch.threads)} | set(patch.remove) | written
    if taken := sorted(held & settled):
        return (
            f"the live game already holds {taken}, some of it beyond what `scenario_so_far` "
            "shows you. Write ids of your own, and reach what is already there with your tools."
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
    draft: Draft,
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


def extension_prompt(settings: Settings, state: Game) -> str:
    document = source_file(settings.scenarios_dir, state.scenario_id)
    given = given_text(settings, state.scenario.premise, document)
    packs = ", ".join(state.packs)
    return (
        f"{given}\n\nThis scenario is authored against these content packs: {packs}."
        "\n\nExtend the world `scenario_so_far` holds."
    )


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
