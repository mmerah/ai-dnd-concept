import re
from collections.abc import Iterable, Sequence
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Mutable, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import ScenarioKind
from aidm.core.play import ChapterRecord, HistoryRecord, SceneRecord
from aidm.core.views import WHOLE_SCENES, Panel, PanelRow, Sections
from aidm.engines.base import Thing

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
# Shared by the scene engines and the room engine.
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


class Attempt(Mutable):
    """One walk out on a job; a job left open and taken again has several."""

    started: int | None = None  # index of the first run or visit away from the hub
    returned: int | None = None  # index of the hub run or visit that closed it

    @model_validator(mode="after")
    def _returns_only_what_started(self) -> Self:
        if self.returned is not None and (self.started is None or self.returned <= self.started):
            raise ValueError("an attempt can only be returned after it started")
        return self


class Job(Mutable):
    title: str
    place: Slug
    terms: str = ""  # as the scene that left the hub wrote them; empty for a room engine
    attempts: list[Attempt] = Field(default_factory=list)
    finished: bool = False  # the master's verdict
    debrief: str = ""  # the last return's card, kept on a reopen
    summary: str = ""  # the worldsmith's, for the master and itself

    @property
    def open(self) -> bool:
        return bool(self.attempts) and self.attempts[-1].returned is None

    @property
    def walking(self) -> bool:
        return self.open and self.attempts[-1].started is not None

    def start(self) -> int:
        started = self.attempts[-1].started if self.open else None
        if started is None:
            raise Refusal(f"job {self.title!r} is not being walked")
        return started

    def begin(self, started: int | None) -> None:
        self.attempts.append(Attempt(started=started))

    def walk(self, index: int) -> None:
        if self.attempts[-1].started is not None:
            raise Refusal(f"job {self.title!r} is not waiting to be walked")
        self.attempts[-1].started = index

    def close(self, returned: int, debrief: str, summary: str) -> None:
        self.attempts[-1].returned = returned
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
        for index, job in enumerate(self.jobs):
            if index < len(self.jobs) - 1 and job.open:
                raise ValueError(f"job {index} is open and is not the last")
            if (job.finished or job.debrief) and not any(
                attempt.started is not None for attempt in job.attempts
            ):
                raise ValueError(f"job {index} is closed or finished before it was walked")
            for attempt_index, attempt in enumerate(job.attempts):
                if attempt_index < len(job.attempts) - 1 and attempt.returned is None:
                    raise ValueError(f"job {index} has an attempt other than the last unreturned")
        return self

    def check_spans(self, places: Sequence[Slug]) -> None:
        """Every `started` is a run or visit away from the hub, every `returned` one at it."""
        for index, job in enumerate(self.jobs):
            for attempt in job.attempts:
                if attempt.started is not None:
                    if attempt.started >= len(places):
                        raise Refusal(f"job {index} started past the walk")
                    if places[attempt.started] == self.place:
                        raise Refusal(f"job {index} started at the hub")
                if attempt.returned is not None:
                    if attempt.returned >= len(places):
                        raise Refusal(f"job {index} returned past the walk")
                    if places[attempt.returned] != self.place:
                        raise Refusal(f"job {index} returned away from the hub")

    def open_job(self) -> Job | None:
        last = self.jobs[-1] if self.jobs else None
        return last if last is not None and last.open else None

    def closed_jobs(self) -> tuple[Job, ...]:
        return tuple(job for job in self.jobs if not job.open)

    @property
    def finished(self) -> bool:
        job = self.open_job()
        return job is not None and job.finished

    def terms(self) -> str:
        job = self.open_job()
        return job.terms if job is not None else ""

    def since_start[T](self, walked: list[T]) -> list[T]:
        """The walking job's attempt; the hub's last when none is walking."""
        job = self.open_job()
        if job is not None and job.walking:
            return walked[job.start() :]
        return walked[-1:]

    def returns(self) -> int:
        return sum(attempt.returned is not None for job in self.jobs for attempt in job.attempts)

    def records_of(self, job: Job, records: Sequence[SceneRecord]) -> tuple[SceneRecord, ...]:
        spans: list[SceneRecord] = []
        for attempt in job.attempts:
            if attempt.started is None:
                continue
            end = attempt.returned if attempt.returned is not None else len(records)
            spans.extend(records[attempt.started : end])
        return tuple(spans)

    def job_records(self, records: Sequence[SceneRecord]) -> tuple[SceneRecord, ...]:
        job = self.open_job()
        return self.records_of(job, records) if job is not None else ()

    def history(self, records: Sequence[SceneRecord]) -> tuple[HistoryRecord, ...]:
        total = len(records)
        chapters = {
            attempt.started: (job, attempt, attempt.returned)
            for job in self.jobs
            for attempt in job.attempts
            if attempt.started is not None
            and attempt.returned is not None
            and attempt.returned <= total - WHOLE_SCENES
        }
        result: list[HistoryRecord] = []
        index = 0
        while index < total:
            found = chapters.get(index)
            if found is None:
                result.append(records[index])
                index += 1
                continue
            job, attempt, end = found
            span = records[index:end]
            verdict = "done" if attempt is job.attempts[-1] and job.finished else "left open"
            result.append(
                ChapterRecord(
                    title=job.title,
                    verdict=verdict,
                    summary=job.summary,
                    scenes=tuple(record.title for record in span),
                )
            )
            index = end
        return tuple(result)

    def taken(self, intent: str) -> Job | None:
        """The left-open job whose `TAKE_JOB` line the intent is."""
        matches = [
            job
            for job in self.jobs
            if self._left_open(job)
            and intent.casefold() == TAKE_JOB.format(title=job.title).casefold()
        ]
        return matches[-1] if matches else None

    def left_open(self, title: str) -> Job | None:
        matches = [
            job
            for job in self.jobs
            if self._left_open(job) and job.title.casefold() == title.casefold()
        ]
        return matches[-1] if matches else None

    def _left_open(self, job: Job) -> bool:
        return not job.open and not job.finished

    def reopen(self, job: Job, started: int | None) -> None:
        self.jobs.remove(job)
        self.jobs.append(job)
        job.finished = False
        job.begin(started)

    def swap_out(self) -> None:
        job = self.open_job()
        if job is None or job.walking:
            raise Refusal("no unwalked job is open to swap out")
        job.attempts.pop()
        if not job.attempts:
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

    def sections(self, hub_title: str, *, at_hub: bool, returning: bool) -> Sections:
        brief = (
            WRITE_HUB_SCENE + RETURN_BRIEF if returning else TAKE_BRIEF if at_hub else AWAY_BRIEF
        )
        return (
            *self.job_row(),
            ("JOBS SO FAR", self.ledger()),
            ("THE BOARD", self.board_lines()),
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

    def board_panel(self, *, at_hub: bool) -> tuple[Panel, ...]:
        return (Panel(title="Board", rows=self.board_rows()),) if at_hub else ()

    def jobs_panel(self) -> tuple[Panel, ...]:
        rows = tuple(
            PanelRow(label=job.title + ("" if job.finished else OPEN_SUFFIX), detail=job.debrief)
            for job in self.closed_jobs()
        )
        return (Panel(title="Jobs", rows=rows),) if rows else ()


def named_unmet(text: str, entities: Iterable[Thing]) -> list[str]:
    """A multi-word name or a bare id: a prop called `Bell` shares its word with any bell tower."""
    folded = text.casefold()
    return [
        entity.name
        for entity in entities
        if (" " in entity.name.strip() and entity.name.casefold() in folded)
        or re.search(rf"\b{re.escape(entity.id)}\b", text) is not None
    ]


def check_kind(kind: ScenarioKind, campaign: Campaign | None) -> None:
    if (kind == "campaign") != (campaign is not None):
        raise Refusal(f"a {kind} scenario {'with' if campaign else 'without'} a hub")


def place_unmet(place: Slug, hub: Slug | None, *, returning: bool) -> str | None:
    if returning:
        return None if place == hub else f"the hub's place {hub!r}: this scene is home"
    if hub is not None and place == hub:
        return "a place away from the hub: home is reached by going home"
    return None


def question_heading(at_hub: bool) -> str:
    return "WHAT THIS PLACE IS ABOUT" if at_hub else "THE QUESTION THIS SCENE SETTLES"
