from collections.abc import Sequence

from pydantic import Field

from aidm.core.entities import Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.model import ScenarioKind
from aidm.core.views import Panel, PanelRow, Rows

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


class Debrief(Frozen):
    text: str = Field(min_length=1)
    finished: bool


class Stop(Frozen):
    """One run or visit, as the job walk reads it; the engine maps its own shape to this."""

    place: Slug
    title: str
    debrief: Debrief | None = None
    job: str = ""  # the terms as the scene that left the hub wrote them; empty for Tunnel Goons


class Job(Frozen):
    title: str
    place: Slug
    debrief: Debrief
    job: str = ""


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


def job_start(stops: Sequence[Stop]) -> int:
    debriefed = [index for index, stop in enumerate(stops) if stop.debrief is not None]
    return debriefed[-1] if debriefed else 0


def heading(job: str, title: str) -> str:
    """The exchange's `where`: the scene's title, headed by its job's."""
    return title if job in ("", title) else f"{job} — {title}"


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
        jobs.append(
            Job(
                title=titles[job_stop],
                place=stops[job_stop].place,
                debrief=stop.debrief,
                job=stops[job_stop].job,
            )
        )
        since_debrief = index
    return tuple(jobs)


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
        open_suffix = "" if job.debrief.finished else OPEN_SUFFIX
        lines.append(f"- {job.title} ({job.place}): {job.debrief.text}{open_suffix}")
        if open_suffix and job.job:
            lines.append(f"  the job: {job.job}")
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
) -> Rows:
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
    hub: Slug | None, at_hub: bool, board: Sequence[Offer], jobs: Sequence[Job], job: str
) -> Rows:
    return (
        *((("THE JOB", job),) if job else ()),
        *((("JOBS SO FAR", ledger(jobs)),) if hub is not None else ()),
        *((("THE BOARD", board_lines(board)),) if at_hub else ()),
    )


def board_panel(at_hub: bool, board: Sequence[Offer]) -> tuple[Panel, ...]:
    return (Panel(title="Board", rows=board_rows(board)),) if at_hub else ()


def jobs_panel(jobs: Sequence[Job]) -> tuple[Panel, ...]:
    rows = tuple(
        PanelRow(
            label=job.title + ("" if job.debrief.finished else OPEN_SUFFIX), detail=job.debrief.text
        )
        for job in jobs
    )
    return (Panel(title="Jobs", rows=rows),) if jobs else ()


def job_closed(job: Job) -> Fact:
    title, text = job.title, job.debrief.text
    label = "done" if job.debrief.finished else "left open"
    return Fact(
        kind="job_closed",
        told=True,
        card=f"Job {label}: {title}\n{text}",
        trace=f"the job {title} closed ({label})",
    )
