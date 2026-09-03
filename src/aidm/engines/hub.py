from collections.abc import Sequence
from typing import Annotated

from pydantic import Field

from aidm.core.entities import Frozen, Mutable, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import ScenarioKind
from aidm.core.views import Panel, PanelRow, Sections

BOARD_MIN, BOARD_MAX = 2, 3
MIN_JOB = 80
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
    "`hidden` is for something worth finding here; it is not required."
)
CAMPAIGN_OPENING = (  # one template; `{hub}` is the engine's own phrase for its home base
    "Write the opening of this campaign: the hub the player keeps coming back to — one place, "
    "{hub} — and a board of two or three `offers`; "
    + OFFER_ASK
    + ". Nothing has happened yet. "
    + HUB_QUESTION
)
TAKE_BRIEF = (
    "The player is leaving {title} ({place}) on a job. WHAT COMES NEXT is the job they take: an "
    "offer by its title, whose pitch THE BOARD holds, or their own words. Write the job's first "
    "scene away from {place}, titled after the offer, and its `job`: who wants what done, what "
    "done looks like, what it pays. Anyone from the hub's cast the player names is present. An "
    "offer taken before opens at the place its JOBS SO FAR line names, with its cast and its terms."
)
AWAY_BRIEF = (
    "The hub is {title} ({place}). Never place a scene at {place}: home is reached by going home."
)
# Shared by the scene engines and Tunnel Goons; `hub_sections` prepends the scene sentence.
RETURN_BRIEF = (
    "The player is home at {title} ({place}). `debrief` is one paragraph on the job they just "
    "left, in the second person and the present tense, as the narrator writes; THE VERDICT says "
    "whether it was finished. Return the whole board in `offers`: keep, drop or add, two or three "
    "in all; " + OFFER_ASK + ". A job left open normally stays on the board, so the player can "
    "take it again. A new offer may grow from JOBS SO FAR: a debt, a job left open, someone met."
)
WRITE_HUB_SCENE = "Write the hub scene there. " + HUB_QUESTION + " "
JOB_DONE = Fact(kind="job_done", told=True, trace="the job is done; the way home is open")


class Offer(Frozen):
    title: str = Field(min_length=1)
    pitch: str = Field(min_length=1)  # the board's words, as the fixer posts it


type Board = Annotated[tuple[Offer, ...], Field(min_length=BOARD_MIN, max_length=BOARD_MAX)]


class Job(Mutable):
    title: str
    place: Slug
    terms: str = ""  # as the scene that left the hub wrote them; empty for Tunnel Goons
    started: int | None = None  # index of the first run or visit away from the hub
    finished: bool = False  # the master's verdict
    debrief: str | None = None  # the hub's word on the return; the job is closed once set


def check_kind(kind: ScenarioKind, hub: Slug | None) -> None:
    if (kind == "campaign") != (hub is not None):
        raise Refusal(f"a {kind} scenario with hub {hub!r}")


def check_board(hub: Slug | None, board: Sequence[Offer]) -> None:
    if hub is None and board:
        raise Refusal("a board with no hub")


def check_jobs(hub: Slug | None, jobs: Sequence[Job], walked: int) -> None:
    if hub is None and jobs:
        raise Refusal("a job with no hub")
    for index, job in enumerate(jobs):
        if index < len(jobs) - 1 and job.debrief is None:
            raise Refusal(f"job {index} has no debrief and is not the last")
        if (job.debrief is not None or job.finished) and job.started is None:
            raise Refusal(f"job {index} is closed or finished before it was walked")
        if job.started is not None and job.started >= walked:
            raise Refusal(f"job {index} started past the walk")


def open_job_of(jobs: Sequence[Job]) -> Job | None:
    """The last job while its `debrief` is `None`."""
    last = jobs[-1] if jobs else None
    return last if last is not None and last.debrief is None else None


def closed_jobs_of(jobs: Sequence[Job]) -> tuple[Job, ...]:
    return tuple(job for job in jobs if job.debrief is not None)


def since_start[T](walked: list[T], job: Job | None, *, campaign: bool) -> list[T]:
    """The open job's runs or visits; all of a one-shot's; the hub's last when none is open."""
    if job is not None and job.started is not None:
        return walked[job.started :]
    return walked[-1:] if campaign else walked


def board_rows(board: Sequence[Offer]) -> tuple[PanelRow, ...]:
    return tuple(
        PanelRow(label=offer.title, detail=offer.pitch, intent=TAKE_JOB.format(title=offer.title))
        for offer in board
    )


def board_lines(board: Sequence[Offer]) -> str:
    return "\n".join(f"- {offer.title}: {offer.pitch}" for offer in board)


def ledger(jobs: Sequence[Job]) -> str:
    if not jobs:
        return "(none yet)"
    lines: list[str] = []
    for job in jobs:
        open_suffix = "" if job.finished else OPEN_SUFFIX
        lines.append(f"- {job.title} ({job.place}): {job.debrief or ''}{open_suffix}")
        if open_suffix and job.terms:
            lines.append(f"  the job: {job.terms}")
    return "\n".join(lines)


def hub_sections(
    hub_title: str,
    hub: Slug,
    board: Sequence[Offer],
    jobs: Sequence[Job],
    *,
    at_hub: bool,
    returning: bool,
    finished: bool,
) -> Sections:
    brief = WRITE_HUB_SCENE + RETURN_BRIEF if returning else TAKE_BRIEF if at_hub else AWAY_BRIEF
    return (
        ("JOBS SO FAR", ledger(jobs)),
        ("THE BOARD", board_lines(board)),
        ("THE HUB", brief.format(title=hub_title, place=hub)),
        *((("THE VERDICT", "finished" if finished else "left open"),) if returning else ()),
    )


def place_unmet(place: Slug, hub: Slug | None, *, returning: bool) -> str | None:
    if returning:
        return None if place == hub else f"the hub's place {hub!r}: this scene is home"
    if hub is not None and place == hub:
        return "a place away from the hub: home is reached by going home"
    return None


def question_heading(at_hub: bool) -> str:
    return "WHAT THIS PLACE IS ABOUT" if at_hub else "THE QUESTION THIS SCENE SETTLES"


def master_tail(
    hub: Slug | None,
    at_hub: bool,
    board: Sequence[Offer],
    jobs: Sequence[Job],
    open_job: Job | None,
) -> Sections:
    return (
        *((("THE JOB", open_job.terms),) if open_job is not None and open_job.terms else ()),
        *((("JOBS SO FAR", ledger(jobs)),) if hub is not None else ()),
        *((("THE BOARD", board_lines(board)),) if at_hub else ()),
    )


def board_panel(at_hub: bool, board: Sequence[Offer]) -> tuple[Panel, ...]:
    return (Panel(title="Board", rows=board_rows(board)),) if at_hub else ()


def jobs_panel(jobs: Sequence[Job]) -> tuple[Panel, ...]:
    rows = tuple(
        PanelRow(label=job.title + ("" if job.finished else OPEN_SUFFIX), detail=job.debrief or "")
        for job in jobs
    )
    return (Panel(title="Jobs", rows=rows),) if jobs else ()


def job_closed(job: Job) -> Fact:
    title, text = job.title, job.debrief or ""
    label = "done" if job.finished else "left open"
    return Fact(
        kind="job_closed",
        told=True,
        card=f"Job {label}: {title}\n{text}",
        trace=f"the job {title} closed ({label})",
    )
