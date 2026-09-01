from collections.abc import Iterator, Sequence
from functools import partial
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import (
    CheckedEntityId,
    EntityId,
    Frozen,
    Mutable,
    Slug,
    require_unique,
    slug,
)
from aidm.core.facts import Fact, cards
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import Exchange, SpokenLine
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Counter, check_filing, labeled, pool, reveal

type Die = Literal[4, 6, 8, 10, 12]
LADDER: tuple[Die, ...] = (4, 6, 8, 10, 12)
type Skill = Literal["bash", "dash", "sneak", "shoot", "think", "sway"]
SKILLS: tuple[Skill, ...] = ("bash", "dash", "sneak", "shoot", "think", "sway")
STRESS_MAX = 4  # vulnerable at 4
CARRY = 3  # items beside the med kit
LOOT_START: Die = 12
STUNT_DIE: Die = 12
STARTING_ITEM: Die = 10
MED_KIT_CLEARS = 2
SCENE_TURN_CAP = 12

SPENT_NOTE = "This scene looks spent — {reason}. If its question is settled, call `next_scene`."
SCENE_SETTLED = Fact(
    kind="scene_settled",
    trace=(
        "this scene is settled. Bring it to a close, then ask the player what they want to "
        "pursue next — in the fiction, naming what the scene left open, never as a list of "
        "choices. They may also stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)


class Item(Mutable):
    name: str
    die: Die


class Survivor(Mutable):
    """The played character: the only one with dice."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = True
    pronouns: str = ""
    job: str = ""
    skills: dict[Skill, Die] = Field(default_factory=dict)  # as created
    worn: dict[Skill, Die] = Field(default_factory=dict)  # where each stands now
    items: dict[EntityId, Item] = Field(default_factory=dict)  # the backpack
    med_kit: bool = False
    loot: Die = LOOT_START
    stress: Counter = Field(default_factory=partial(Counter, current=0, maximum=STRESS_MAX))
    stunted: bool = False
    alive: bool = True

    @model_validator(mode="after")
    def _filled_out(self) -> Self:
        for skill in SKILLS:
            self.skills.setdefault(skill, 4)
        for skill in SKILLS:
            self.worn.setdefault(skill, self.skills[skill])
        return self

    @property
    def vulnerable(self) -> bool:
        return self.stress.current >= STRESS_MAX

    def rows(self) -> Rows:
        skills = ", ".join(
            f"{skill.capitalize()} d{self.worn[skill]}"
            + ("" if self.worn[skill] == self.skills[skill] else f" (rated d{self.skills[skill]})")
            for skill in SKILLS
        )
        return tuple(
            (label, value)
            for label, value in (
                ("Pronouns", self.pronouns),
                ("Job", self.job),
                ("Skills", skills),
                ("Loot die", f"d{self.loot}"),
                ("Stress", pool(self.stress) + (", vulnerable" if self.vulnerable else "")),
                ("Stunt", "spent" if self.stunted else ""),
                ("Med kit", "yes" if self.med_kit else ""),
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


class Scene(Frozen):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    # Public: the player reads it; settling it ends the scene.
    question: str = Field(min_length=10)
    situation: str = Field(min_length=40)
    # What `question` does not say: never narrated, never in a view.
    secret: str = ""


class SceneRun(Mutable):
    scene: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # The game master has called the question answered; the player may move on, or play on.
    settled: bool = False
    # Why the scene looks finished already, written by the rule that settled it.
    spent: str = ""


class SceneCanon(Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, Npc] = Field(default_factory=dict)
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    source: str = ""

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        _check_named(self.present, self.hidden, self.cast)
        return self


class BreathlessWorld(Mutable):
    """The world as a sequence of scenes: the player is a sheet, never a cast entry."""

    cast: dict[EntityId, Npc] = Field(default_factory=dict)
    player: Survivor
    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.cast)
        _check_named(self.run.present, self.run.hidden, self.cast)
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player.id != PLAYER_ID:
            raise ValueError(f"the player must be filed as {PLAYER_ID!r}")
        if PLAYER_ID in (*self.run.present, *self.run.hidden):
            raise ValueError("the player is in every scene and is never listed in it")
        return self

    def require(self, entity_id: EntityId) -> Survivor | Npc:
        if entity_id == PLAYER_ID:
            return self.player
        one = self.cast.get(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_here(self, entity_id: EntityId) -> Survivor | Npc:
        one = self.require(entity_id)
        if one.id == PLAYER_ID:
            return one
        if one.id not in self.run.present:
            raise ValueError(
                f"{one.name} is not here with the player, so nothing can happen to them"
            )
        return one

    def require_alive_here(self, entity_id: EntityId) -> Survivor | Npc:
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
        return tuple(
            one if one.where else one.model_copy(update={"where": run.scene.title})
            for run in self.runs
            for one in run.exchanges
        )

    def here(self) -> Iterator[Survivor | Npc]:
        yield self.player
        for entity_id in self.run.present:
            yield self.cast[entity_id]

    def label(self, entity: Survivor | Npc) -> str:
        return labeled(entity, PLAYER_ID)

    def reveal(self, entity: Survivor | Npc) -> list[Fact]:
        return reveal(entity, PLAYER_ID)

    def last_seen(self, entity_id: EntityId) -> str:
        """Scan backwards for the scene that held them, so nothing the story dropped is lost."""
        for run in reversed(self.runs):
            if entity_id in (*run.present, *run.hidden):
                return run.scene.title
        return ""


class BreathlessState(Mutable):
    world: BreathlessWorld


class BreathlessScenario(Mutable):
    world: SceneCanon


class BreathlessCharacter(Mutable):
    pronouns: str
    job: str
    skills: dict[Skill, Die]
    item: str  # the one starting d10 item

    @model_validator(mode="after")
    def _three_skills(self) -> Self:
        if len(self.skills) != 3 or sorted(self.skills.values()) != [6, 8, 10]:
            raise ValueError("three skills: one d10, one d8, one d6")
        return self


class BreathlessGame(Game[BreathlessState]):
    pass


class BreathlessScenarioFile(Scenario[BreathlessScenario]):
    pass


class BreathlessCharacterFile(Character[BreathlessCharacter]):
    pass


def stepped(die: Die) -> Die:
    """One step down the ladder, floored at d4."""
    return LADDER[max(LADDER.index(die) - 1, 0)]


def scene_spent(run: SceneRun, someone_dead: bool) -> str | None:
    """Deliberately blunt: catches only what no reading of the fiction can miss."""
    if run.spent:
        return run.spent
    if someone_dead:
        return "someone here is dead"
    if len(run.exchanges) >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None


def known(state: BreathlessGame, entity_id: EntityId) -> bool | None:
    if entity_id == PLAYER_ID:
        return True
    one = state.payload.world.cast.get(entity_id)
    return None if one is None else one.known


def record(
    state: BreathlessGame, prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]
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
    if world.run.settled or len(world.run.exchanges) <= 1:
        return ()
    reason = scene_spent(world.run, any(not one.alive for one in world.here()))
    return () if reason is None else (SPENT_NOTE.format(reason=reason),)


def history(state: BreathlessGame) -> tuple[Exchange, ...]:
    return state.payload.world.exchanges()


def settled(state: BreathlessGame) -> bool:
    return state.payload.world.run.settled


def player_over(state: BreathlessGame) -> str | None:
    return "You died." if not state.payload.world.player.alive else None


def player_survivor(character: BreathlessCharacterFile) -> Survivor:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    return Survivor(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        pronouns=payload.pronouns,
        job=payload.job,
        skills=payload.skills,
        items={EntityId(slug(payload.item, ())): Item(name=payload.item, die=STARTING_ITEM)},
    )


def _check_named(
    present: Sequence[EntityId], hidden: Sequence[EntityId], cast: dict[EntityId, Npc]
) -> None:
    require_unique("ids in the scene", (*present, *hidden))
    for who in (*present, *hidden):
        if who not in cast:
            raise ValueError(f"scene names {who!r}, who is not in the cast")
    for who in hidden:
        if cast[who].known:
            raise ValueError(f"{who!r} is hidden here but the player has already met them")
    for who in present:
        if not cast[who].known:
            raise ValueError(f"{who!r} is here but the player has not met them")
