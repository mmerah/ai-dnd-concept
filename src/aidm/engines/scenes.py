import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Slug, require_unique
from aidm.core.facts import Fact, cards
from aidm.core.play import Exchange, SpokenLine
from aidm.core.tools import schema_of
from aidm.core.views import Panel, PanelRow, Rows, sections
from aidm.engines.core import Entity
from aidm.engines.hub import (
    HOME_ROW,
    HUB_ROW,
    JOB_DONE,
    Debrief,
    Job,
    Offer,
    Stop,
    check_board,
    closed_jobs,
    heading,
    hub_sections,
    job_start,
    job_titles,
    place_unmet,
)

SCENE_TURN_CAP = 12
TAIL_EXCHANGES = 3
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


class SceneWorld(Mutable):
    """What the three scene worlds share; each engine adds its cast, its player and its checks."""

    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()

    @model_validator(mode="after")
    def _hub_consistent(self) -> Self:
        check_hub(self.hub, self.board, self.runs)
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


def settle(world: SceneWorld, job_done: bool) -> tuple[Fact, ...]:
    if world.run.settled:
        raise ValueError("this scene is already settled; the player has the way on")
    if job_done and (world.hub is None or world.at_hub):
        raise ValueError("no job is open here")
    world.run.settled = True
    world.run.job_done = job_done
    return (SCENE_SETTLED, JOB_DONE) if job_done else (SCENE_SETTLED,)


def record_exchange(
    world: SceneWorld,
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


def hub_rows(world: SceneWorld, *, returning: bool) -> Rows:
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
    opening: bool,
) -> list[str]:
    """The cast a scene owes, whatever the engine's own people are made of."""
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if not opening and not any(resolved_id(one, held) is not None for one in others):
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
                "what happened: " + (told_tail(run) or "(nothing yet)"),
            )
        )
        for number, run in enumerate(runs, start=1)
    )


def told_tail(run: SceneRun) -> str:
    return "\n".join(f"> {one.prompt}\n{one.narration}" for one in run.exchanges[-TAIL_EXCHANGES:])


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


def scene_rows(world: SceneWorld) -> tuple[PanelRow, ...]:
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
