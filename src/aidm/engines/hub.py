import re
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Mutable, Refusal, Slug, require_unique
from aidm.core.facts import Fact
from aidm.core.model import ScenarioKind
from aidm.core.play import ChapterRecord, Exchange, HistoryRecord, SceneRecord
from aidm.core.views import WHOLE_SCENES, Panel, PanelRow, Sections, render_whole
from aidm.engines.base import Person, Thing

BOARD_MIN, BOARD_MAX = 2, 3
MIN_JOB = 80
MIN_RECAP = 60
MIN_SUMMARY = 120
GO_HOME = "Go home."
OPEN_SUFFIX = " (left open)"
HOME_ROW = PanelRow(
    label="Go home", detail="Back to base; the job closes on a card.", intent=GO_HOME
)
HUB_ROW = PanelRow(label="Take a job from the board, or name where you go.", detail="")
TAKE_JOB = 'I take the job "{title}".'  # what an offer's button plays
HUB_QUESTION = (
    "The hub's `question` is the standing pressure at home, one sentence the player reads as "
    "the scene's headline: what is owed, who is watching, what runs out. Never something a "
    "scene settles."
)
OFFER_ASK = (
    "an offer is a `title` and a `pitch` as the board posts it — 'Crates off Deck 9, no "
    "manifest, half up front.' — enough to walk out on"
)
ONE_SHOT_OPENING = (
    "Write the opening scene of this adventure: the one place the player starts in, who is "
    "there, and a `question` that settles in that place. A scene ends when the player leaves "
    "it, so a question about somewhere farther on belongs to a later scene. `cast` is the "
    "adventure's people and things, not the scene's: write who is met here and who the player "
    "will meet farther in, and list under `present` and `hidden` only who is here now. "
    "`hidden` is for something worth finding here; it is not required. The opening also writes "
    "`arc`, a few lines on what lies beyond this scene, for the game master and the worldsmith, "
    "never the player."
)
CAMPAIGN_OPENING = (  # one template; `{hub}` is the engine's own phrase for its home base
    "Write the opening of this campaign: the hub the player keeps coming back to — one place, "
    "{hub} — and a board of two or three `offers`; "
    + OFFER_ASK
    + ". Nothing has happened yet. "
    + HUB_QUESTION
)
TAKE_BRIEF = (
    "The player is leaving {title} ({place}) on a job, the first of several scenes it will take. "
    "WHAT COMES NEXT is the job they take: an "
    "offer by its title, whose pitch THE BOARD holds, or their own words. Write the job's first "
    "scene away from {place}, titled after the offer, and its `job`: who wants what done, what "
    "done looks like, what it pays. Anyone from the hub's cast the player names is present. An "
    'offer marked "(left open)" is a job taken before: title the scene exactly as the offer, '
    "open it where the job stands, with its cast and its terms, its JOBS SO FAR line holds its "
    "summary; restate its `job`, and write its `arc` from what is still undone."
)
AWAY_BRIEF = (
    "The hub is {title} ({place}). Never place a scene at {place}: home is reached by going home."
)
RETURN_BRIEF = (
    "The player is home at {title} ({place}). `debrief` is one paragraph on the job they just "
    "left, in the second person and the present tense, as the narrator writes; THE VERDICT says "
    "whether it was finished. Return the whole board in `offers`: keep, drop or add, two or three "
    "in all; " + OFFER_ASK + ". A job left open normally stays on the board, so the player can "
    "take it again. A new offer may grow from JOBS SO FAR: a debt, a job left open, someone met. "
    "THIS JOB is the whole job, hidden facts included; `summary` and the recap fields are written "
    "from it for the game master, `debrief` for the player."
)
WRITE_HUB_SCENE = "Write the hub scene there. " + HUB_QUESTION + " "
JOB_DONE = Fact(kind="job_done", told=True, trace="the job is done; the way home is open")


class Offer(Frozen):
    title: str = Field(min_length=1)
    pitch: str = Field(min_length=1)  # the board's words, as the fixer posts it


type Board = Annotated[tuple[Offer, ...], Field(min_length=BOARD_MIN, max_length=BOARD_MAX)]


class Job(Mutable):
    """A run or visit walking it carries its title; a job taken again has several spans."""

    title: str = Field(min_length=1)  # a run's empty tag is the hub, so a job's is never empty
    place: Slug
    terms: str = ""  # as the scene that left the hub wrote them; empty for a room engine
    open: bool = False
    finished: bool = False  # the master's verdict
    debrief: str = ""  # the last return's card, kept on a reopen
    summary: str = ""  # the worldsmith's, for the master and itself

    def close(self, debrief: str, summary: str) -> None:
        self.open = False
        self.debrief = debrief
        self.summary = summary

    def closed(self) -> Fact:
        label = "done" if self.finished else "left open"
        return Fact(
            kind="job_closed",
            told=True,
            card=f"Job {label}: {self.title}\n{self.debrief}",
            trace=f"the job {self.title} closed ({label})",
        )


class Campaign(Mutable):
    place: Slug
    board: Board
    jobs: list[Job] = Field(default_factory=list)

    @model_validator(mode="after")
    def _jobs_in_order(self) -> Self:
        require_unique("job titles", (job.title.casefold() for job in self.jobs))
        for index, job in enumerate(self.jobs):
            if index < len(self.jobs) - 1 and job.open:
                raise ValueError(f"job {index} is open and is not the last")
        return self

    def check_walk(self, places: Sequence[Slug], walked: Sequence[str]) -> None:
        """`walked` is the job each run or visit carries; the hub and a wander carry none."""
        titles = {job.title for job in self.jobs}
        for index, (place, title) in enumerate(zip(places, walked, strict=True)):
            if not title:
                if index and walked[index - 1] and place != self.place:
                    raise Refusal(
                        f"run {index} returns from {walked[index - 1]!r} away from the hub"
                    )
                continue
            if title not in titles:
                raise Refusal(f"run {index} walks a job the campaign never took: {title!r}")
            if place == self.place and (index == 0 or walked[index - 1] != title):
                raise Refusal(f"run {index} takes {title!r} at the hub")
        open_job = self.open_job()
        if walked and walked[-1] and (open_job is None or open_job.title != walked[-1]):
            raise Refusal(f"the last run walks {walked[-1]!r}, which is not open")
        for job in self.jobs:
            if (job.finished or job.debrief) and job.title not in walked:
                raise Refusal(f"job {job.title!r} is closed or finished before it was walked")

    def open_job(self) -> Job | None:
        return self.jobs[-1] if self.jobs and self.jobs[-1].open else None

    def closed_jobs(self) -> tuple[Job, ...]:
        return tuple(job for job in self.jobs if not job.open)

    @property
    def finished(self) -> bool:
        job = self.open_job()
        return job is not None and job.finished

    def terms(self) -> str:
        job = self.open_job()
        return job.terms if job is not None else ""

    def records_of(self, job: Job, records: Sequence[SceneRecord]) -> tuple[SceneRecord, ...]:
        return tuple(record for record in records if record.job == job.title)

    def job_records(self, records: Sequence[SceneRecord]) -> tuple[SceneRecord, ...]:
        job = self.open_job()
        return self.records_of(job, records) if job is not None else ()

    def history(self, records: Sequence[SceneRecord]) -> tuple[HistoryRecord, ...]:
        """A span walked whole and returned before the last two scenes is bound as a chapter."""
        total = len(records)
        result: list[HistoryRecord] = []
        index = 0
        while index < total:
            title = records[index].job
            end = index + 1
            while end < total and records[end].job == title:
                end += 1
            job = self.titled(title) if title else None
            if job is None or end > total - WHOLE_SCENES:
                result.extend(records[index:end])
            else:
                last = not any(record.job == title for record in records[end:])
                result.append(
                    ChapterRecord(
                        title=job.title,
                        verdict="done" if last and job.finished else "left open",
                        summary=job.summary,
                        scenes=tuple(record.title for record in records[index:end]),
                    )
                )
            index = end
        return tuple(result)

    def taken(self, intent: str) -> Job | None:
        title = job_title(intent)
        return None if title is None else self.left_open(title)

    def titled(self, title: str) -> Job | None:
        folded = title.casefold()
        return next((job for job in self.jobs if job.title.casefold() == folded), None)

    def left_open(self, title: str) -> Job | None:
        job = self.titled(title)
        return job if job is not None and not job.open and not job.finished else None

    def reopen(self, job: Job) -> None:
        self.jobs.remove(job)
        self.jobs.append(job)
        job.finished = False
        job.open = True

    def swap_out(self, walked: Sequence[str]) -> None:
        """A job taken at the hub and never walked leaves no trace; one walked before stays."""
        job = self.open_job()
        if job is None or (walked and walked[-1] == job.title):
            raise Refusal("no unwalked job is open to swap out")
        job.open = False
        if job.title not in walked:
            self.jobs.remove(job)

    def ledger(self) -> str:
        closed = self.closed_jobs()
        if not closed:
            return "(none yet)"
        lines: list[str] = []
        for job in closed:
            open_suffix = "" if job.finished else OPEN_SUFFIX
            lines.append(f"- {job.title} ({job.place}): {job.summary}{open_suffix}")
            if open_suffix and job.terms:
                lines.append(f"  the job: {job.terms}")
        return "\n".join(lines)

    def board_rows(self) -> tuple[PanelRow, ...]:
        return tuple(
            PanelRow(
                label=offer.title + (OPEN_SUFFIX if self.left_open(offer.title) else ""),
                detail=offer.pitch,
                intent=TAKE_JOB.format(title=offer.title),
            )
            for offer in self.board
        )

    def board_lines(self) -> str:
        return "\n".join(
            f"- {offer.title}{OPEN_SUFFIX if self.left_open(offer.title) else ''}: {offer.pitch}"
            for offer in self.board
        )

    def hub_block(
        self,
        hub_title: str,
        brief: str,
        records: Sequence[SceneRecord],
        *,
        returning: bool,
        reopening: Job | None,
    ) -> Sections:
        this_job = (("THIS JOB", render_whole(self.job_records(records))),) if returning else ()
        before = (
            ()
            if reopening is None
            else (("THE JOB BEFORE", render_whole(self.records_of(reopening, records))),)
        )
        return (*this_job, *before, *self.sections(hub_title, brief, returning=returning))

    def sections(self, hub_title: str, brief: str, *, returning: bool) -> Sections:
        return (
            *self.tail(at_hub=True),
            ("THE HUB", brief.format(title=hub_title, place=self.place)),
            *(
                (("THE VERDICT", "finished" if self.finished else "left open"),)
                if returning
                else ()
            ),
        )

    def job_row(self) -> Sections:
        job = self.open_job()
        if job is None or not job.terms:
            return ()
        body = job.terms + (f"\nso far: {job.summary}" if job.summary else "")
        return (("THE JOB", body),)

    def tail(self, *, at_hub: bool) -> Sections:
        return (
            *self.job_row(),
            ("JOBS SO FAR", self.ledger()),
            *((("THE BOARD", self.board_lines()),) if at_hub else ()),
        )

    def board_panel(self, *, at_hub: bool, reporting: PanelRow | None = None) -> tuple[Panel, ...]:
        """`reporting` is the one row a walked job leaves on the board."""
        if not at_hub:
            return ()
        rows = self.board_rows() if reporting is None else (reporting,)
        return (Panel(title="Board", rows=rows),)

    def jobs_panel(self) -> tuple[Panel, ...]:
        rows = tuple(
            PanelRow(label=job.title + ("" if job.finished else OPEN_SUFFIX), detail=job.debrief)
            for job in self.closed_jobs()
        )
        return (Panel(title="Jobs", rows=rows),) if rows else ()


class World[P: Person](Mutable):
    """What both families' worlds share; the sequence of places is each family's own."""

    player: P
    source: str = ""
    campaign: Campaign | None = None

    @property
    @abstractmethod
    def at_hub(self) -> bool: ...
    @abstractmethod
    def records(self) -> tuple[SceneRecord, ...]: ...
    @abstractmethod
    def record(self, exchange: Exchange) -> None: ...

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(exchange for record in self.records() for exchange in record.exchanges)

    def scenes(self) -> tuple[HistoryRecord, ...]:
        records = self.records()
        return records if self.campaign is None else self.campaign.history(records)


def walk_start(walked: Sequence[str]) -> int:
    """Where the current span began: the last run or visit, when it walks no job."""
    index = max(len(walked) - 1, 0)
    while index > 0 and walked[-1] and walked[index - 1] == walked[-1]:
        index -= 1
    return index


def named_unmet(text: str, entities: Iterable[Thing]) -> list[str]:
    """A multi-word name or a bare id: a prop called `Bell` shares its word with any bell tower."""
    folded = text.casefold()
    return [
        entity.name
        for entity in entities
        if (" " in entity.name.strip() and entity.name.casefold() in folded)
        or re.search(rf"\b{re.escape(entity.id)}\b", text) is not None
    ]


def job_title(intent: str) -> str | None:
    """The title inside the board's own `TAKE_JOB` line; None for any other words."""
    prefix, suffix = TAKE_JOB.split("{title}")
    folded = intent.casefold()
    if not folded.startswith(prefix.casefold()) or not folded.endswith(suffix.casefold()):
        return None
    return intent[len(prefix) : len(intent) - len(suffix)]


def check_kind(kind: ScenarioKind, campaign: Campaign | None) -> None:
    if (kind == "campaign") != (campaign is not None):
        raise Refusal(f"a {kind} scenario {'with' if campaign else 'without'} a hub")


def place_unmet(place: Slug, hub: Slug | None, *, returning: bool) -> str | None:
    if returning:
        return None if place == hub else f"the hub's place {hub!r}: this scene is home"
    if hub is not None and place == hub:
        return "a place away from the hub: home is reached by going home"
    return None


def title_unmet(title: str, campaign: Campaign, reopening: Job | None) -> list[str]:
    """Runs carry their job by title, so a job taken before is reopened, never taken twice."""
    taken = campaign.titled(title)
    if taken is None or (reopening is not None and taken.title == reopening.title):
        return []
    return [f"a title no job on JOBS SO FAR carries: {taken.title!r} was taken before"]


def question_heading(at_hub: bool) -> str:
    return "WHAT THIS PLACE IS ABOUT" if at_hub else "THE QUESTION THIS SCENE SETTLES"
