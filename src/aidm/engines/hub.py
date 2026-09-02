from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from aidm.core.entities import Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.model import ScenarioKind
from aidm.core.views import PanelRow, Rows

BOARD_MIN, BOARD_MAX = 2, 3
GO_HOME = "Go home."
OPEN_SUFFIX = " (left open)"
HOME_ROW = PanelRow(
    label="Go home", detail="Back to base; the job closes on a card.", intent=GO_HOME
)
HUB_ROW = PanelRow(label="Take a job from the board, or name where you go.", detail="")
type Moment = Literal["taking", "away", "returning"]  # where the worldsmith writes from
TAKE_JOB = 'I take the job "{title}".'  # what an offer's button plays
HUB_QUESTION = (
    "The hub's `question` is what keeps the player coming back, never something to settle."
)
JOB_ASK = "who wants what done, what done looks like, what it pays"
TAKE_BRIEF = (
    "The player is leaving {title} ({place}) on a job. WHAT COMES NEXT is the job they take: an "
    "offer by its title, whose pitch THE BOARD holds, or their own words. Write the job's first "
    f"scene away from {{place}}, titled after the offer, and its `job`: {JOB_ASK}. Anyone from "
    "the hub's cast the player names is present. An offer taken before opens at the place its "
    "JOBS SO FAR line names, with its cast."
)
AWAY_BRIEF = (
    "The hub is {title} ({place}). Never place a scene at {place}: home is reached by going home."
)
# Shared by the scene engines and Tunnel Goons; `hub_sections` prepends the scene sentence.
RETURN_BRIEF = (
    "The player is home at {title} ({place}). `debrief.text` is one paragraph on the job they "
    "just left, written for the player; `debrief.finished` is true only when that job was "
    "completed. Return the whole board in `offers`: keep, drop or add, two or three in all. A job "
    "left open normally stays on the board, so the player can take it again. A new offer may grow "
    "from JOBS SO FAR: a debt, a job left open, someone met."
)
WRITE_HUB_SCENE = "Write the hub scene there. " + HUB_QUESTION + " "
BRIEFS: dict[Moment, str] = {
    "taking": TAKE_BRIEF,
    "away": AWAY_BRIEF,
    "returning": WRITE_HUB_SCENE + RETURN_BRIEF,
}


class Offer(Frozen):
    title: str = Field(min_length=1)
    pitch: str = Field(min_length=1)  # the board's words, as the fixer posts it


class Debrief(Frozen):
    text: str = Field(min_length=1)
    finished: bool


class Stop(Frozen):
    """One run or visit, as the job walk reads it; the engine maps its own shape to this."""

    place: Slug
    title: str
    debrief: Debrief | None = None


class Job(Frozen):
    title: str
    place: Slug
    debrief: Debrief


def check_kind(kind: ScenarioKind, hub: Slug | None) -> None:
    if (kind == "campaign") != (hub is not None):
        raise ValueError(f"a {kind} scenario with hub {hub!r}")


def check_board(hub: Slug | None, board: Sequence[Offer]) -> None:
    if hub is None:
        if board:
            raise ValueError("a board with no hub")
    elif not BOARD_MIN <= len(board) <= BOARD_MAX:
        raise ValueError(f"a board of {len(board)} offers at hub {hub!r}")


def job_titles(hub: Slug | None, stops: Sequence[Stop]) -> tuple[str, ...]:
    titles: list[str] = []
    since = ""
    for stop in stops:
        since = "" if hub is None or stop.place == hub else since or stop.title
        titles.append(since)
    return tuple(titles)


def job_start(hub: Slug | None, stops: Sequence[Stop]) -> int:
    debriefed = [index for index, stop in enumerate(stops) if stop.debrief is not None]
    return debriefed[-1] if debriefed else 0


def open_job(hub: Slug | None, stops: Sequence[Stop]) -> str | None:
    titles = job_titles(hub, stops)
    tail = titles[job_start(hub, stops) + 1 :]
    return next((title for title in reversed(tail) if title), None)


def closed_jobs(hub: Slug | None, stops: Sequence[Stop]) -> tuple[Job, ...]:
    titles = job_titles(hub, stops)
    jobs: list[Job] = []
    since_debrief = -1
    for index, stop in enumerate(stops):
        if stop.debrief is None:
            continue
        job_stop = next((step for step in range(since_debrief + 1, index) if titles[step]), None)
        if job_stop is None:
            raise ValueError("a debrief with no job before it")
        jobs.append(Job(title=titles[job_stop], place=stops[job_stop].place, debrief=stop.debrief))
        since_debrief = index
    return tuple(jobs)


def board_rows(board: Sequence[Offer]) -> tuple[PanelRow, ...]:
    return tuple(
        PanelRow(label=offer.title, detail=offer.pitch, intent=TAKE_JOB.format(title=offer.title))
        for offer in board
    )


def board_lines(board: Sequence[Offer]) -> str:
    return "\n".join(f"- {offer.title}: {offer.pitch}" for offer in board)


def jobs_rows(jobs: Sequence[Job]) -> tuple[PanelRow, ...]:
    return tuple(
        PanelRow(
            label=job.title + ("" if job.debrief.finished else OPEN_SUFFIX), detail=job.debrief.text
        )
        for job in jobs
    )


def ledger(jobs: Sequence[Job]) -> str:
    if not jobs:
        return "(none yet)"
    return "\n".join(
        f"- {job.title} ({job.place}): {job.debrief.text}"
        + ("" if job.debrief.finished else OPEN_SUFFIX)
        for job in jobs
    )


def hub_sections(
    hub_title: str, hub: Slug, board: Sequence[Offer], jobs: Sequence[Job], *, moment: Moment
) -> Rows:
    brief = BRIEFS[moment].format(title=hub_title, place=hub)
    return (
        ("JOBS SO FAR", ledger(jobs)),
        ("THE BOARD", board_lines(board)),
        ("THE HUB", brief),
    )


def job_closed(job: Job) -> Fact:
    title, text = job.title, job.debrief.text
    label = "done" if job.debrief.finished else "left open"
    return Fact(
        kind="job_closed",
        told=True,
        card=f"Job {label}: {title}\n{text}",
        trace=f"the job {title} closed ({label}): {text}",
    )
