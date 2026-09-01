from collections.abc import Iterator, Sequence
from functools import partial
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Slug, require_unique
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import Exchange, SpokenLine
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Counter, pool

LUCK_MAX = 6
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
TIES_PER_TWIST = 3
SCENE_TURN_CAP = 12

TagKind = Literal["skill", "frailty", "gear", "condition"]

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
    advances_owed: int = Field(default=0, ge=0)

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

    cast: dict[EntityId, LonerCharacter] = Field(default_factory=dict)
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    source: str = ""

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        _check_named(self.present, self.hidden, self.cast)
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
        _check_named(self.run.present, self.run.hidden, self.cast)
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

    engine: Literal["loner3e"] = "loner3e"
    world: LonerWorld
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Field(default_factory=partial(Counter, current=0, maximum=TIES_PER_TWIST))
    twist_pack: Slug


class Loner3eScenario(Mutable):
    engine: Literal["loner3e"] = "loner3e"
    world: SceneCanon


class Loner3eCharacter(Mutable):
    engine: Literal["loner3e"] = "loner3e"
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    goal: str = ""
    motive: str = ""
    twist_pack: Slug


class Loner3eGame(Game[Loner3eState]):
    pass


class Loner3eScenarioFile(Scenario[Loner3eScenario]):
    pass


class Loner3eCharacterFile(Character[Loner3eCharacter]):
    pass


def scene_spent(world: LonerWorld) -> str | None:
    """Deliberately blunt: catches only what no reading of the fiction can miss."""
    run = world.run
    if run.spent:
        return run.spent
    if any(not one.alive for one in world.here()):
        return "someone here is dead"
    if len(run.exchanges) >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None


def labeled(entity: LonerCharacter, player_id: EntityId) -> str:
    """A trace names an entity by name and exact id, so the model can reuse the id."""
    if entity.id == player_id:
        return f"the player {entity.name}[{entity.id}]"
    return f"{entity.name}[{entity.id}]"


def entity_fact(
    entity: LonerCharacter,
    kind: str,
    trace: str,
    *,
    narrate: bool = True,
    card: str = "",
    dice: tuple[DiceEvent, ...] = (),
) -> Fact:
    """A character the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind,
        trace=trace,
        told=narrate and entity.known,
        entity_id=entity.id,
        card=card,
        dice=dice,
    )


def reveal(entity: LonerCharacter, player_id: EntityId) -> list[Fact]:
    """Leave cards to the containing action or the standalone reveal arm."""
    if entity.known:
        return []
    entity.known = True
    return [entity_fact(entity, "entity_discovered", f"learned of {labeled(entity, player_id)}")]


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
    reason = scene_spent(world)
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


def check_filing(cast: dict[EntityId, LonerCharacter]) -> None:
    for key, one in cast.items():
        if key != one.id:
            raise ValueError(f"entity {one.id!r} is filed under {key!r}")


def _check_named(
    present: Sequence[EntityId], hidden: Sequence[EntityId], cast: dict[EntityId, LonerCharacter]
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
