from collections.abc import Iterator, Sequence
from functools import partial
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Mutable, require_unique
from aidm.core.facts import Fact, cards
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import Exchange, SpokenLine
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Counter, check_filing, labeled, pool, reveal
from aidm.engines.scenes import SPENT_NOTE, Scene, SceneRun, check_named, scene_spent

LUCK_MAX = 6
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
TIES_PER_TWIST = 3

TagKind = Literal["skill", "frailty", "gear", "condition"]


class LonerCharacter(Mutable):
    """SRD "Everything is a Character": a person, an object, a vehicle or a curse alike."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    # Living characters only; the SRD gives none to an object, a vehicle or a curse.
    goal: str = ""
    motive: str = ""
    nemesis: str = ""
    luck: Counter = Field(default_factory=partial(Counter, current=LUCK_MAX, maximum=LUCK_MAX))
    alive: bool = True

    def rows(self) -> Rows:
        return tuple(
            (label, value)
            for label, value in (
                ("Concept", self.concept),
                ("Skills", ", ".join(self.skills)),
                ("Frailties", ", ".join(self.frailties)),
                ("Gear", ", ".join(self.gear)),
                ("Conditions", ", ".join(self.conditions)),
                ("Goal", self.goal),
                ("Motive", self.motive),
                ("Nemesis", self.nemesis),
                ("Luck", pool(self.luck)),
            )
            if value
        )


class SceneCanon(Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, LonerCharacter] = Field(default_factory=dict)
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    source: str = ""

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        check_named(self.present, self.hidden, self.cast)
        return self


class LonerWorld(Mutable):
    """The world as a sequence of scenes: the cast persists, the scene is what is happening."""

    cast: dict[EntityId, LonerCharacter] = Field(default_factory=dict)
    runs: list[SceneRun] = Field(min_length=1)
    companions: list[EntityId] = Field(default_factory=list)
    player_id: EntityId
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.cast)
        check_named(self.run.present, self.run.hidden, self.cast)
        if self.player_id not in self.cast:
            raise ValueError("the player is not in the cast")
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player_id not in self.run.present:
            raise ValueError("the player is not in their own scene")
        if self.player_id in self.companions:
            raise ValueError("the player cannot travel with themselves")
        require_unique("companions", self.companions)
        for member_id in self.companions:
            if not self.require(member_id).alive:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
        return self

    def require(self, entity_id: EntityId) -> LonerCharacter:
        one = self.cast.get(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_here(self, entity_id: EntityId) -> LonerCharacter:
        one = self.require(entity_id)
        if one.id not in self.run.present:
            raise ValueError(
                f"{one.name} is not here with the player, so nothing can happen to them"
            )
        return one

    def require_alive_here(self, entity_id: EntityId) -> LonerCharacter:
        one = self.require(entity_id)
        if not one.alive:
            raise ValueError(f"{one.name} is dead; they take no further part.")
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

    @property
    def player(self) -> LonerCharacter:
        return self.require(self.player_id)

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(
            one if one.where else one.model_copy(update={"where": run.scene.title})
            for run in self.runs
            for one in run.exchanges
        )

    def here(self) -> Iterator[LonerCharacter]:
        return (self.require(one) for one in self.run.present)

    def label(self, entity: LonerCharacter) -> str:
        return labeled(entity, self.player_id)

    def reveal(self, entity: LonerCharacter) -> list[Fact]:
        return reveal(entity, self.player_id)

    def last_seen(self, entity_id: EntityId) -> str:
        """Scan backwards for the scene that held them, so nothing the story dropped is lost."""
        for run in reversed(self.runs):
            if entity_id in (*run.present, *run.hidden):
                return run.scene.title
        return ""


class Loner3eState(Mutable):
    """The save payload: the scene world, plus the two counters the SRD keeps beside it."""

    world: LonerWorld
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Field(default_factory=partial(Counter, current=0, maximum=TIES_PER_TWIST))


class Loner3eScenario(Mutable):
    world: SceneCanon


class Loner3eCharacter(Mutable):
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    goal: str = ""
    motive: str = ""


class Loner3eGame(Game[Loner3eState]):
    pass


class Loner3eScenarioFile(Scenario[Loner3eScenario]):
    pass


class Loner3eCharacterFile(Character[Loner3eCharacter]):
    pass


def known(state: Loner3eGame, entity_id: EntityId) -> bool | None:
    one = state.payload.world.cast.get(entity_id)
    return None if one is None else one.known


def record(
    state: Loner3eGame, prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]
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


def history(state: Loner3eGame) -> tuple[Exchange, ...]:
    return state.payload.world.exchanges()


def settled(state: Loner3eGame) -> bool:
    return state.payload.world.run.settled


def player_over(state: Loner3eGame) -> str | None:
    return "You died." if not state.payload.world.player.alive else None


def player_character(character: Loner3eCharacterFile) -> LonerCharacter:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    return LonerCharacter(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        concept=payload.concept,
        skills=payload.skills,
        frailties=payload.frailties,
        gear=payload.gear,
        goal=payload.goal,
        motive=payload.motive,
    )


def tags_of(one: LonerCharacter, kind: TagKind) -> tuple[str, ...]:
    match kind:
        case "skill":
            return one.skills
        case "frailty":
            return one.frailties
        case "gear":
            return one.gear
        case "condition":
            return one.conditions


def set_tags(one: LonerCharacter, kind: TagKind, tags: tuple[str, ...]) -> None:
    match kind:
        case "skill":
            one.skills = tags
        case "frailty":
            one.frailties = tags
        case "gear":
            one.gear = tags
        case "condition":
            one.conditions = tags
