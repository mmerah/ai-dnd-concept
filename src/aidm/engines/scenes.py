import json
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Any, Literal, Self, TypeIs

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import (
    CheckedEntityId,
    EngineId,
    EntityId,
    Frozen,
    Mutable,
    Slug,
    require_unique,
)
from aidm.core.facts import Fact, cards
from aidm.core.model import (
    AnyScenario,
    Game,
    Scenario,
    ScenarioKind,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import Exchange, SpokenLine
from aidm.core.tools import schema_of
from aidm.core.views import (
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Rows,
    Subject,
    sections,
    speaker_of,
)
from aidm.engines.core import (
    Entity,
    Person,
    check_filing,
    check_party,
    entity_fact,
    labeled,
    party_panel,
    reveal,
    sentence,
    told_tail,
)
from aidm.engines.hub import (
    BOARD_MAX,
    BOARD_MIN,
    CAMPAIGN_OPENING,
    GO_HOME,
    HOME_ROW,
    HUB_ROW,
    JOB_DONE,
    MIN_JOB,
    ONE_SHOT_OPENING,
    Debrief,
    Job,
    Offer,
    Stop,
    board_panel,
    check_board,
    check_kind,
    closed_jobs,
    heading,
    hub_sections,
    job_closed,
    job_start,
    job_titles,
    jobs_panel,
    place_unmet,
)

SCENE_TURN_CAP = 12
MIN_SITUATION = 80  # what the worldsmith owes a scene; an authored `Scene` is held to less
SPENT_NOTE = "This scene looks spent — {reason}. If its question is settled, call `next_scene`."
NEXT_SCENE = (
    "Say this scene's question is settled. The player is then asked what they want to pursue, "
    "and their own words build the next scene. Do not answer for them."
)
SCENE_SETTLED = Fact(
    kind="scene_settled",
    trace=(
        "this scene is settled. Bring it to a close, then ask the player what they want to "
        "pursue next — in the fiction, naming what the scene left open, never as a list of "
        "choices. They may also stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)
# The narrator's brief for a crossing; `{pursuit}` is what the player said they were going after.
CROSSING = (
    "The player is leaving WHAT THE PLAYER HAS READ for the place in SCENE. They asked for this: "
    '"{pursuit}"\n\n'
    "Write the crossing: a sentence of leaving, then the arrival. Cover the distance and the time "
    "in the fewest words that make it real, and end on what they see first. WHAT HAPPENED names "
    "anyone who travelled with them. They have not acted in the new place yet, so settle nothing."
)
SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
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
    debrief: Debrief | None = None  # the hub's word on the job just left; hub runs after the first
    job: str = ""  # the job as taken; on the scene that leaves the hub only


class SceneRun(Mutable):
    scene: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # The game master has called the question answered; the player may move on, or play on.
    settled: bool = False
    # Why the scene looks finished already, written by the rule that settled it.
    spent: str = ""
    # The master's word: settling this scene finished the job the player walked out on.
    job_done: bool = False


class NextScene(Frozen):
    job_done: bool = Field(
        default=False,
        description="A campaign only: settling this scene also finishes the job the player "
        "walked out on.",
    )


class SceneCanon[C: Person](Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, C] = Field(default_factory=dict)
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


class SceneScenario[C: Person](Mutable):
    world: SceneCanon[C]


class SceneWorld[C: Person, P: Person](Mutable):
    """The world as a sequence of scenes: the player is a sheet, never a cast entry."""

    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    cast: dict[EntityId, C] = Field(default_factory=dict)
    player: P
    party: list[EntityId] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_hub(self.hub, self.board, self.runs)
        check_filing(self.cast)
        check_named(self.run.present, self.run.hidden, self.cast)
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player.id in self.cast:
            raise ValueError("the player is in the cast")
        if self.player.id in (*self.run.present, *self.run.hidden):
            raise ValueError("the player is in every scene and is never listed in it")
        if self.player.id in self.party:
            raise ValueError("the player cannot travel with themselves")
        check_party(self.party, self.cast)
        if left := sorted(set(self.party) - set(self.run.present)):
            raise ValueError(f"the party is in every scene; {left} are not in this one")
        return self

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    @property
    def current(self) -> Scene:
        return self.run.scene

    @property
    def at_hub(self) -> bool:
        return self.hub is not None and self.current.place == self.hub

    @property
    def job_done(self) -> bool:
        """The master's verdict on the open job: read before a return is appended."""
        return any(run.job_done for run in self.job_runs())

    @property
    def job(self) -> str:
        """What the player walked out on, as the scene that left the hub wrote it."""
        return next((run.scene.job for run in self.job_runs() if run.scene.job), "")

    def stops(self) -> tuple[Stop, ...]:
        return tuple(
            Stop(place=run.scene.place, title=run.scene.title, debrief=run.scene.debrief)
            for run in self.runs
        )

    def job_runs(self) -> list[SceneRun]:
        return self.runs[job_start(self.stops()) :]

    def jobs(self) -> tuple[Job, ...]:
        return closed_jobs(self.hub, self.stops())

    def exchanges(self) -> tuple[Exchange, ...]:
        filed: list[Exchange] = []
        for run, job in zip(self.runs, job_titles(self.hub, self.stops()), strict=True):
            where = heading(job, run.scene.title)
            filed.extend(
                one if one.where else one.model_copy(update={"where": where})
                for one in run.exchanges
            )
        return tuple(filed)

    def last_seen(self, entity_id: EntityId) -> str:
        """The prompt's own line; scanning back keeps what the story dropped from being lost."""
        for run in reversed(self.runs):
            if entity_id in (*run.present, *run.hidden):
                return f"last seen in: {run.scene.title}"
        return ""

    def members(self) -> list[C]:
        return [self.cast[one] for one in self.party]

    def require(self, entity_id: EntityId) -> C | P:
        if entity_id == self.player.id:
            return self.player
        one = self.cast.get(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_here(self, entity_id: EntityId) -> C | P:
        one = self.require(entity_id)
        if one.id == self.player.id:
            return one
        if one.id not in self.run.present:
            raise ValueError(
                f"{one.name} is not here with the player, so nothing can happen to them"
            )
        return one

    def require_alive_here(self, entity_id: EntityId) -> C | P:
        one = self.require(entity_id)
        if not one.alive:
            raise ValueError(f"{one.name} is dead; they take no further part.")
        if one.id == self.player.id:
            return one
        if one.id not in self.run.present:
            raise ValueError(
                f"{entity_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return one

    def here(self) -> Iterator[C | P]:
        yield self.player
        for entity_id in self.run.present:
            yield self.cast[entity_id]

    def label(self, entity: Person) -> str:
        return labeled(entity, self.player.id)

    def reveal(self, entity: Person) -> list[Fact]:
        return reveal(entity, self.player.id)


class SceneState[C: Person, P: Person](Mutable):
    world: SceneWorld[C, P]


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


class Enter(Frozen):
    """Bring a cast member into the current scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """Take a cast member out of the current scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class Kill(Frozen):
    """Record that someone here has died."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of who here died.")


class SceneDraft[C: Person](Frozen):
    """What the worldsmith returns. Ids arrive as free text so a wrong one can be matched against
    a cast name before it is refused; code owns the scene id and never asks for the player."""

    place: Slug
    title: str
    question: str = Field(min_length=10)
    situation: str = Field(min_length=MIN_SITUATION)
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    secret: str = ""
    cast: dict[EntityId, C] = Field(default_factory=dict)


class JobDraft[C: Person](SceneDraft[C]):
    """The scene that leaves the hub."""

    job: str = Field(min_length=MIN_JOB)


class HubDraft[C: Person](SceneDraft[C]):
    """The campaign's opening: the hub and its board."""

    offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)


class ReturnDraft[C: Person](HubDraft[C]):
    """The return home: the debrief is the paragraph; the verdict is the master's."""

    debrief: str = Field(min_length=1)


def new_world[C: Person, P: Person](canon: SceneCanon[C], player: P) -> SceneWorld[C, P]:
    """The player is added by code and never authored, so no scenario can claim their id."""
    canon = deepcopy(canon)
    return SceneWorld(
        cast=canon.cast,
        player=player,
        runs=[
            SceneRun(scene=canon.opening, present=list(canon.present), hidden=list(canon.hidden))
        ],
        source=canon.source,
        hub=canon.hub,
        board=canon.board,
    )


def reveal_hidden[C: Person, P: Person](world: SceneWorld[C, P], entity_id: EntityId) -> list[Fact]:
    """The discovery itself, distinct from what `enter` tells about someone walking in."""
    one = world.require(entity_id)
    if entity_id not in world.run.hidden:
        raise ValueError(f"{entity_id!r} is not hidden here")
    world.run.hidden.remove(one.id)
    world.run.present.append(one.id)
    facts = world.reveal(one)
    if not facts:
        raise ValueError(f"the player has already met {one.name}")
    return [facts[0].model_copy(update={"card": sentence(f"{one.name} discovered")})]


def enter[C: Person, P: Person](world: SceneWorld[C, P], entity_id: EntityId) -> list[Fact]:
    if entity_id == world.player.id:
        raise ValueError("the player is in every scene; move the story on instead")
    one = world.require(entity_id)
    if one.id in world.run.present:
        raise ValueError(f"{one.name} is already here")
    if one.id in world.run.hidden:
        raise ValueError(f"{one.name} is hidden here; reveal them instead")
    world.run.present.append(one.id)
    trace = f"{world.label(one)} arrives"
    return [
        *world.reveal(one),
        entity_fact(one, "entity_entered", trace, card=f"{one.name} arrives"),
    ]


def leave[C: Person, P: Person](world: SceneWorld[C, P], entity_id: EntityId) -> list[Fact]:
    if entity_id == world.player.id:
        raise ValueError("the player is in every scene; move the story on instead")
    one = world.require_here(entity_id)
    if one.id in world.party:
        raise ValueError(f"{one.name} travels with the player and leaves through `leave_party`")
    world.run.present.remove(one.id)
    trace = f"{world.label(one)} leaves"
    return [entity_fact(one, "entity_left", trace, card=f"{one.name} leaves")]


def kill[C: Person, P: Person](world: SceneWorld[C, P], entity_id: EntityId) -> list[Fact]:
    one = world.require_here(entity_id)
    if not one.alive:
        raise ValueError(f"{one.name} is already dead")
    facts = world.reveal(one)
    if one.id in world.party:
        world.party.remove(one.id)
    one.alive = False
    card = "You are dead" if one.id == world.player.id else f"{one.name} is dead"
    facts.append(entity_fact(one, "actor_killed", f"{world.label(one)} is dead", card=card))
    return facts


def check_game[S: SceneState[Any, Any]](packs: Collection[str], state: Game[S]) -> None:
    if not state.packs:
        raise ValueError(f"a {state.engine!r} game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    check_kind(state.scenario.kind, state.payload.world.hub)


def known[S: SceneState[Any, Any]](state: Game[S], entity_id: EntityId) -> bool | None:
    world = state.payload.world
    if entity_id == world.player.id:
        return True
    one = world.cast.get(entity_id)
    return None if one is None else one.known


def record[S: SceneState[Any, Any]](
    state: Game[S], prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]
) -> tuple[str, ...]:
    world = state.payload.world
    return record_exchange(
        world,
        prompt,
        lines,
        facts,
        "" if state.pending is None else state.pending.prompt,
        someone_dead=any(not one.alive for one in world.here()),
    )


def history[S: SceneState[Any, Any]](state: Game[S]) -> tuple[Exchange, ...]:
    return state.payload.world.exchanges()


def way_open[S: SceneState[Any, Any]](state: Game[S]) -> bool:
    world = state.payload.world
    return world.run.settled or world.at_hub


def player_over[S: SceneState[Any, Any]](state: Game[S]) -> str | None:
    return "You died." if not state.payload.world.player.alive else None


def settle[C: Person, P: Person](world: SceneWorld[C, P], job_done: bool) -> tuple[Fact, ...]:
    if world.run.settled:
        raise ValueError("this scene is already settled; the player has the way on")
    if job_done and (world.hub is None or world.at_hub):
        raise ValueError("no job is open here")
    world.run.settled = True
    world.run.job_done = job_done
    return (SCENE_SETTLED, JOB_DONE) if job_done else (SCENE_SETTLED,)


def record_exchange[C: Person, P: Person](
    world: SceneWorld[C, P],
    prompt: str,
    lines: tuple[SpokenLine, ...],
    facts: Sequence[Fact],
    decision: str,
    *,
    someone_dead: bool,
) -> tuple[str, ...]:
    """Files the turn, then says whether the scene looks spent — deliberately blunt: the note
    catches only what no reading of the fiction can miss."""
    run = world.run
    run.exchanges.append(
        Exchange(prompt=prompt, lines=lines, facts=cards(facts), decision=decision)
    )
    if run.settled or world.at_hub or len(run.exchanges) <= 1:
        return ()
    capped = len(run.exchanges) >= SCENE_TURN_CAP
    reason = (
        run.spent
        or ("someone here is dead" if someone_dead else "")
        or (f"{SCENE_TURN_CAP} turns have passed here" if capped else "")
    )
    return (SPENT_NOTE.format(reason=reason),) if reason else ()


def worldsmith_prompt(
    role: str,
    *,
    source: str,
    history: str,
    cast: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
    hub: Rows = (),
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("SCENES SO FAR", history),
            *hub,
            ("THE WHOLE CAST", cast),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def hub_rows[C: Person, P: Person](world: SceneWorld[C, P], *, returning: bool) -> Rows:
    if world.hub is None:
        return ()
    return hub_sections(
        world.runs[0].scene.title,
        world.hub,
        world.board,
        world.jobs(),
        at_hub=world.at_hub,
        returning=returning,
        finished=world.job_done,
    )


def check_named(
    present: Sequence[EntityId], hidden: Sequence[EntityId], cast: Mapping[EntityId, Entity]
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


def arrival_brief(pursuit: str) -> str:
    return CROSSING.format(pursuit=pursuit)


def resolved_id(wanted: str, cast: Mapping[EntityId, Entity]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def resolve_ids(
    wanted: Iterable[str], cast: Mapping[EntityId, Entity], where: str
) -> list[EntityId]:
    found: list[EntityId] = []
    for one in wanted:
        matched = resolved_id(one, cast)
        if matched is None:
            raise ValueError(f"the scene lists {one!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found


def named_in(situation: str, hidden: Iterable[str], cast: Mapping[EntityId, Entity]) -> list[str]:
    """Multi-word names only: a prop called `Bell` shares its word with any bell tower."""
    said = situation.casefold()
    found = (cast[one] for wanted in hidden if (one := resolved_id(wanted, cast)) is not None)
    return [one.name for one in found if " " in one.name.strip() and one.name.casefold() in said]


def cast_unmet(
    others: Sequence[str],
    hidden: Sequence[str],
    situation: str,
    known: Mapping[EntityId, Entity],
    held: Mapping[EntityId, Entity],
    *,
    needs_return: bool,
) -> list[str]:
    """The cast a scene owes, whatever the engine's own people are made of."""
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if needs_return and not any(resolved_id(one, held) is not None for one in others):
        unmet.append("at least one existing cast member brought back")
    if stray := sorted(one for one in others if resolved_id(one, known) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    # `situation` is read to the player, so naming a hidden entity there hands them the find.
    if told := sorted(named_in(situation, hidden, known)):
        unmet.append(f"a situation that does not name what is hidden: {told}")
    return unmet


def hub_unmet(
    place: Slug,
    hub: Slug | None,
    *,
    debrief: str | None,
    held: Mapping[EntityId, Entity],
    known: Mapping[EntityId, Entity],
) -> list[str]:
    """A debrief means a return: it is home, and it is read to the player."""
    unmet: list[str] = []
    if (misplaced := place_unmet(place, hub, returning=debrief is not None)) is not None:
        unmet.append(misplaced)
    if debrief is not None:
        strangers = [eid for eid, one in held.items() if not one.known]
        if named := sorted(named_in(debrief, strangers, known)):
            unmet.append(f"a debrief that does not name what the player has not met: {named}")
    return unmet


def scene_history(runs: Sequence[SceneRun]) -> str:
    return "\n\n".join(
        "\n".join(
            (
                f"SCENE {number}: {run.scene.title} ({run.scene.place})",
                f"the question: {run.scene.question}",
                *([f"the job: {run.scene.job}"] if run.scene.job else []),
                run.scene.situation,
                "what happened: " + (told_tail(run.exchanges) or "(nothing yet)"),
            )
        )
        for number, run in enumerate(runs, start=1)
    )


def check_hub(hub: Slug | None, board: Sequence[Offer], runs: Sequence[SceneRun]) -> None:
    check_board(hub, board)
    for index, run in enumerate(runs):
        if run.job_done and (hub is None or run.scene.place == hub):
            raise ValueError(f"run {index} has a job done with no job open")
    if hub is None:
        for index, run in enumerate(runs):
            if run.scene.debrief is not None:
                raise ValueError(f"run {index} has a debrief with no hub")
        return
    first = runs[0].scene
    if first.place != hub or first.debrief is not None:
        raise ValueError(f"run 0 does not open at hub {hub!r} with no debrief")
    for index in range(1, len(runs)):
        scene = runs[index].scene
        at_hub = scene.place == hub
        if at_hub and scene.debrief is None:
            raise ValueError(f"run {index} is at the hub with no debrief")
        if not at_hub and scene.debrief is not None:
            raise ValueError(f"run {index} is away from the hub with a debrief")
        if at_hub and runs[index - 1].scene.place == hub:
            raise ValueError(f"run {index} is a hub run right after a hub run")


def scene_rows[C: Person, P: Person](world: SceneWorld[C, P]) -> tuple[PanelRow, ...]:
    rows = [PanelRow(label=world.current.question, detail="")]
    if world.at_hub:
        rows.append(HUB_ROW)
    elif world.run.settled:
        rows.append(
            PanelRow(label="Way on", detail="Keep playing, or name where you go and move on.")
        )
        if world.hub is not None:
            rows.append(HOME_ROW)
    return tuple(rows)


def trail_panel(runs: Sequence[SceneRun]) -> Panel:
    return Panel(
        title="Trail", rows=tuple(PanelRow(label=one.scene.title, detail="") for one in runs)
    )


def opening_draft[C: Person](cast_type: type[C], kind: ScenarioKind) -> type[SceneDraft[C]]:
    """Pydantic parametrizes the subscript at runtime, so `isinstance` still narrows the result."""
    return HubDraft[cast_type] if kind == "campaign" else SceneDraft[cast_type]


def scene_unmet[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None
) -> list[str]:
    """No world means the opening: nobody exists yet, and no id can be the player's."""
    held: Mapping[EntityId, C] = {} if world is None else world.cast
    everyone: Mapping[EntityId, Entity] = (
        dict(draft.cast) if world is None else {world.player.id: world.player, **held, **draft.cast}
    )
    followers = () if world is None else (world.player.id, *world.party)
    others = (*draft.present, *draft.hidden)
    unmet: list[str] = []
    if named := sorted(one for one in others if resolved_id(one, everyone) in followers):
        unmet.append(
            "a scene that does not list the player or the party; "
            f"they are put there by code: {named}"
        )
    # Nothing can be brought back once everyone left behind travels with the player.
    needs_return = world is not None and bool(set(world.cast) - set(world.party))
    unmet.extend(
        cast_unmet(others, draft.hidden, draft.situation, everyone, held, needs_return=needs_return)
    )
    if broken := [f"{eid}: {why}" for eid, one in draft.cast.items() if (why := one.unwritten())]:
        unmet.append(f"cast members as the worldsmith may write them: {broken}")
    unmet.extend(
        hub_unmet(
            draft.place,
            None if world is None else world.hub,
            debrief=draft.debrief if isinstance(draft, ReturnDraft) else None,
            held=held,
            known=everyone,
        )
    )
    return unmet


def scene_refusal[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None = None
) -> str | None:
    unmet = scene_unmet(draft, world)
    return None if not unmet else "the scene needs " + "; ".join(unmet)


def opening_canon[C: Person](draft: SceneDraft[C], source: str) -> SceneCanon[C]:
    cast = draft.cast
    present = resolve_ids(draft.present, cast, "present")
    for one in present:
        cast[one].known = True
    hub, board = (draft.place, draft.offers) if isinstance(draft, HubDraft) else (None, ())
    return SceneCanon(
        cast=cast,
        opening=_scene(draft, False),
        present=present,
        hidden=resolve_ids(draft.hidden, cast, "hidden"),
        source=source,
        hub=hub,
        board=board,
    )


def apply_scene[C: Person, P: Person](world: SceneWorld[C, P], draft: SceneDraft[C]) -> None:
    """Every refusal lands before the first write: a rejected scene leaves the world alone."""
    for one, held in draft.cast.items():
        if one == world.player.id:
            raise ValueError("the scene rewrites the player")
        if one in world.cast:
            raise ValueError(f"the scene rewrites {one!r}, who is already in the cast")
        if one != held.id:
            raise ValueError(f"entity {held.id!r} is filed under {one!r}")
    cast: dict[EntityId, C] = {**world.cast, **draft.cast}
    everyone: Mapping[EntityId, Entity] = {world.player.id: world.player, **cast}
    followers = (world.player.id, *world.party)
    present = resolve_ids(draft.present, everyone, "present")
    hidden = resolve_ids(draft.hidden, everyone, "hidden")
    if named := sorted(one for one in (*present, *hidden) if one in followers):
        raise ValueError(
            f"the scene lists {named}, who are in every scene and are put there by code"
        )
    if overlap := sorted(set(present) & set(hidden)):
        raise ValueError(f"the scene lists {overlap} as both present and hidden")
    if met := sorted(one for one in hidden if cast[one].known):
        raise ValueError(f"the scene hides {met}, whom the player has already met")
    finished = world.job_done  # the master's verdict on the job the return is closing
    world.cast = cast
    for one in present:
        cast[one].known = True
    world.runs.append(
        SceneRun(scene=_scene(draft, finished), present=[*world.party, *present], hidden=hidden)
    )


async def write_next[C: Person, P: Person](
    world: SceneWorld[C, P],
    intent: str,
    answer: WorldsmithAnswer,
    *,
    cast_type: type[C],
    role: str,
    guidance: str,
) -> BaseModel:
    returning = world.hub is not None and not world.at_hub and intent == GO_HOME
    model: type[SceneDraft[C]] = (
        ReturnDraft[cast_type]
        if returning
        else JobDraft[cast_type]
        if world.at_hub
        else SceneDraft[cast_type]
    )

    def refusal(written: BaseModel) -> str | None:
        if not _is_draft(written, model):
            raise ValueError("the worldsmith returned an incompatible scene")
        return scene_refusal(written, world)

    prompt = render_worldsmith(world, intent, guidance, model, role=role)
    return await answer(prompt, model, refusal)


def install_scene[S: SceneState[Any, Any]](
    state: Game[S], written: BaseModel, *, finished_note: str
) -> tuple[Fact, ...]:
    if not _is_draft(written, SceneDraft[Any]):
        raise ValueError(f"{state.engine!r} received an incompatible scene")
    world = state.payload.world
    apply_scene(world, written.model_copy(deep=True))
    trace = f"the story moves to {written.title}"
    if came := [one.name for one in world.members()]:
        trace += f", the player travelling with {', '.join(came)}"
    label = "Home" if isinstance(written, ReturnDraft) else "New scene"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"{label}: {written.title}")
    if isinstance(written, ReturnDraft):
        world.board = written.offers
        job = world.jobs()[-1]
        if job.debrief.finished and finished_note:
            state.notes = (*state.notes, finished_note.format(title=job.title))
        return (job_closed(job), opened)
    return (opened,)


def render_worldsmith[C: Person, P: Person](
    world: SceneWorld[C, P], intent: str, guidance: str, answer: type[SceneDraft[C]], *, role: str
) -> str:
    # The worldsmith must know who follows the player out of the scene.
    cast = "\n".join(
        (
            entity_line(world.player, detail=world.last_seen(world.player.id)),
            *(
                entity_line(
                    one,
                    detail="travels with the player"
                    if one.id in world.party
                    else world.last_seen(one.id),
                )
                for one in world.cast.values()
            ),
        )
    )
    return worldsmith_prompt(
        role,
        source=world.source,
        history=scene_history(world.job_runs()),
        cast=cast,
        guidance=guidance,
        intent=intent,
        answer=answer,
        hub=hub_rows(world, returning=issubclass(answer, ReturnDraft)),
    )


def render_opening[C: Person](
    cast_type: type[C], role: str, source: str, guidance: str, kind: ScenarioKind, hub_phrase: str
) -> str:
    return worldsmith_prompt(
        role,
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        guidance=guidance,
        intent=CAMPAIGN_OPENING.format(hub=hub_phrase) if kind == "campaign" else ONE_SHOT_OPENING,
        answer=opening_draft(cast_type, kind),
    )


def build_scenario[C: Person](
    file_type: type[Scenario[SceneScenario[C]]],
    engine_id: EngineId,
    cast_type: type[C],
    title: str,
    premise: str,
    packs: tuple[Slug, ...],
    written: BaseModel,
    source: str,
    kind: ScenarioKind,
) -> AnyScenario:
    if not _is_draft(written, SceneDraft[cast_type]):
        raise ValueError(f"{engine_id} received an incompatible scene")
    if (refused := scene_refusal(written)) is not None:
        raise ValueError(refused)
    return file_type(
        meta=ScenarioMeta(title=title, premise=premise or written.situation, kind=kind),
        engine=engine_id,
        packs=packs,
        payload=SceneScenario(world=opening_canon(written, source)),
    )


def entity_line(one: Person, *, detail: str = "") -> str:
    line = f"- {one.name}[{one.id}] — {one.brief}"
    if not one.alive:
        line += " (dead)"
    parts = [line]
    if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in one.rows()):
        parts.append(f"  {sheet}")
    if detail:
        parts.append(f"  {detail}")
    return "\n".join(parts)


def here_lines[C: Person, P: Person](world: SceneWorld[C, P]) -> str:
    lines = "\n".join(entity_line(one) for one in world.here() if one.id != world.player.id)
    return lines or "- (none)"


def hidden_lines[C: Person, P: Person](world: SceneWorld[C, P]) -> str:
    return "\n".join(entity_line(world.require(one)) for one in world.run.hidden) or "- (none)"


def narrator_view[S: SceneState[Any, Any]](state: Game[S]) -> NarratorView:
    world = state.payload.world
    scene = world.current
    here = [one for one in world.here() if one.known]
    return NarratorView(
        place=scene.place,
        title=scene.title,
        focus=scene.question,
        situation=scene.situation,
        art_prompt="\n".join(
            (
                f"The place: {scene.title} — {scene.situation}",
                *(f"Present: {one.name} — {one.brief}" for one in here),
            )
        ),
        subjects=tuple(_subject_of(one) for one in here),
        speakers=tuple(speaker_of(_subject_of(one)) for one in here),
    )


def player_view[S: SceneState[Any, Any]](
    state: Game[S], extra: tuple[Panel, ...] = ()
) -> PlayerView:
    world = state.payload.world
    player = world.player
    here_rows = (
        PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id),
        *(
            PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
            for one in world.here()
            if one.known and one.id != player.id
        ),
    )
    return PlayerView(
        player=_subject_of(player),
        panels=(
            Panel(
                title="Character",
                rows=tuple(PanelRow(label=label, detail=detail) for label, detail in player.rows()),
            ),
            *extra,
            Panel(title="This scene", rows=scene_rows(world)),
            *board_panel(world.at_hub, world.board),
            *party_panel(world.members()),
            Panel(title="Here", rows=here_rows),
            trail_panel(world.job_runs()),
            *jobs_panel(world.jobs()),
        ),
        prompt=state.pending,
        over=player_over(state),
    )


def _is_draft[C: Person](written: BaseModel, model: type[SceneDraft[C]]) -> TypeIs[SceneDraft[C]]:
    """`isinstance` takes no parametrized class, and pydantic parametrizes by copying, not
    subclassing, so the check is against the origin the type argument was applied to."""
    origin = model.__pydantic_generic_metadata__["origin"] or model
    return issubclass(type(written), origin)


def _subject_of(one: Person) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def _scene[C: Person](draft: SceneDraft[C], finished: bool) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
        job=draft.job if isinstance(draft, JobDraft) else "",
        debrief=Debrief(text=draft.debrief, finished=finished)
        if isinstance(draft, ReturnDraft)
        else None,
    )
