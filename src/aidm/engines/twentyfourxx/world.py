from collections.abc import Iterator, Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Slug, slug
from aidm.core.facts import Fact, cards
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import Exchange, SpokenLine
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, check_filing, labeled, reveal
from aidm.engines.hub import Job, Offer, Stop, closed_jobs, job_start, job_titles
from aidm.engines.scenes import (
    SPENT_NOTE,
    Scene,
    SceneRun,
    check_hub,
    check_named,
    scene_spent,
    stops_of,
)

type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)
DEFAULT_DIE = 6  # a skill not on the sheet
HINDERED_DIE = 4
HELP_DIE = 6
STARTING_CREDITS = 2
MAIMED = "Maimed"


class Kit(Frozen):
    """An item as a pack or a character file names it."""

    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)


class Item(Mutable):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)  # a vest breaks once; battle armor "up to 3x"
    broken_times: int = Field(default=0, ge=0)

    @property
    def broken(self) -> bool:
        return self.broken_times >= self.breaks


class Operator(Mutable):
    """The played character: the only one with dice, credits and hindrances."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = True
    specialty: str
    origin: str
    traits: tuple[str, ...] = ()  # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)  # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
    items: dict[EntityId, Item] = Field(default_factory=dict)
    hindrances: tuple[str, ...] = ()  # the SRD's word: injuries and the like
    alive: bool = True

    def die(self, skill: str) -> int:
        return self.skills.get(skill, DEFAULT_DIE)

    def rows(self) -> Rows:
        skills = ", ".join(f"{skill} d{die}" for skill, die in self.skills.items())
        return tuple(
            (label, value)
            for label, value in (
                ("Specialty", self.specialty),
                ("Origin", self.origin),
                ("Traits", ", ".join(self.traits)),
                ("Skills", skills),
                ("Credits", f"₡{self.credits}"),
                ("Hindrances", ", ".join(self.hindrances)),
            )
            if value
        )


class Npc(Mutable):
    """Everyone else, exactly as the SRD leaves them: no dice."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    alive: bool = True


class SceneCanon(Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, Npc] = Field(default_factory=dict)
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        check_named(self.present, self.hidden, self.cast)
        check_hub(self.hub, self.board, (SceneRun(scene=self.opening),))
        return self


class TwentyfourxxWorld(Mutable):
    """The world as a sequence of scenes: the player is a sheet, never a cast entry."""

    cast: dict[EntityId, Npc] = Field(default_factory=dict)
    player: Operator
    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.cast)
        check_named(self.run.present, self.run.hidden, self.cast)
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player.id != PLAYER_ID:
            raise ValueError(f"the player must be filed as {PLAYER_ID!r}")
        if PLAYER_ID in (*self.run.present, *self.run.hidden):
            raise ValueError("the player is in every scene and is never listed in it")
        check_hub(self.hub, self.board, self.runs)
        return self

    @property
    def at_hub(self) -> bool:
        return self.hub is not None and self.current.place == self.hub

    def stops(self) -> tuple[Stop, ...]:
        return stops_of(self.runs)

    def job_runs(self) -> list[SceneRun]:
        return self.runs[job_start(self.hub, self.stops()) :]

    def jobs(self) -> tuple[Job, ...]:
        return closed_jobs(self.hub, self.stops())

    def require(self, entity_id: EntityId) -> Operator | Npc:
        if entity_id == PLAYER_ID:
            return self.player
        one = self.cast.get(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_here(self, entity_id: EntityId) -> Operator | Npc:
        one = self.require(entity_id)
        if one.id == PLAYER_ID:
            return one
        if one.id not in self.run.present:
            raise ValueError(
                f"{one.name} is not here with the player, so nothing can happen to them"
            )
        return one

    def require_alive_here(self, entity_id: EntityId) -> Operator | Npc:
        one = self.require(entity_id)
        if not one.alive:
            raise ValueError(f"{one.name} is dead; they take no further part.")
        if one.id == PLAYER_ID:
            return one
        if one.id not in self.run.present:
            raise ValueError(
                f"{entity_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return one

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    @property
    def current(self) -> Scene:
        return self.run.scene

    def exchanges(self) -> tuple[Exchange, ...]:
        filed: list[Exchange] = []
        for run, job in zip(self.runs, job_titles(self.hub, self.stops()), strict=True):
            where = (
                run.scene.title if job in ("", run.scene.title) else f"{job} — {run.scene.title}"
            )
            filed.extend(
                one if one.where else one.model_copy(update={"where": where})
                for one in run.exchanges
            )
        return tuple(filed)

    def here(self) -> Iterator[Operator | Npc]:
        yield self.player
        for entity_id in self.run.present:
            yield self.cast[entity_id]

    def label(self, entity: Operator | Npc) -> str:
        return labeled(entity, PLAYER_ID)

    def reveal(self, entity: Operator | Npc) -> list[Fact]:
        return reveal(entity, PLAYER_ID)

    def last_seen(self, entity_id: EntityId) -> str:
        """Scan backwards for the scene that held them, so nothing the story dropped is lost."""
        for run in reversed(self.runs):
            if entity_id in (*run.present, *run.hidden):
                return run.scene.title
        return ""


class TwentyfourxxCharacter(Mutable):
    specialty: str
    origin: str
    traits: tuple[str, ...] = ()
    skills: dict[str, SkillDie]
    items: tuple[Kit, ...]  # the comm, the specialty kit, Muscle's weapon


class TwentyfourxxState(Mutable):
    world: TwentyfourxxWorld


class TwentyfourxxScenario(Mutable):
    world: SceneCanon


class TwentyfourxxGame(Game[TwentyfourxxState]):
    pass


class TwentyfourxxScenarioFile(Scenario[TwentyfourxxScenario]):
    pass


class TwentyfourxxCharacterFile(Character[TwentyfourxxCharacter]):
    pass


def raised(current: SkillDie | None) -> SkillDie:
    """The SRD's advancement ladder: none -> d8 -> d10 -> d12."""
    if current is None:
        return LADDER[0]
    if current == LADDER[-1]:
        raise ValueError("the skill is already at d12")
    return LADDER[LADDER.index(current) + 1]


def known(state: TwentyfourxxGame, entity_id: EntityId) -> bool | None:
    if entity_id == PLAYER_ID:
        return True
    one = state.payload.world.cast.get(entity_id)
    return None if one is None else one.known


def record(
    state: TwentyfourxxGame, prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]
) -> tuple[str, ...]:
    world = state.payload.world
    world.run.exchanges.append(
        Exchange(
            prompt=prompt,
            lines=lines,
            facts=cards(facts),
            decision="" if state.pending is None else state.pending.prompt,
        )
    )
    if world.run.settled or world.at_hub or len(world.run.exchanges) <= 1:
        return ()
    reason = scene_spent(world.run, any(not one.alive for one in world.here()))
    return () if reason is None else (SPENT_NOTE.format(reason=reason),)


def history(state: TwentyfourxxGame) -> tuple[Exchange, ...]:
    return state.payload.world.exchanges()


def way_open(state: TwentyfourxxGame) -> bool:
    world = state.payload.world
    return world.run.settled or world.at_hub


def player_over(state: TwentyfourxxGame) -> str | None:
    return "You died." if not state.payload.world.player.alive else None


def player_operator(character: TwentyfourxxCharacterFile) -> Operator:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    taken: list[str] = []
    items: dict[EntityId, Item] = {}
    for kit in payload.items:
        key = slug(kit.name, taken)
        taken.append(key)
        items[EntityId(key)] = Item(name=kit.name, bulky=kit.bulky, breaks=kit.breaks)
    return Operator(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        specialty=payload.specialty,
        origin=payload.origin,
        traits=payload.traits,
        skills=payload.skills,
        items=items,
    )
