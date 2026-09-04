from dataclasses import dataclass

from aidm.core.entities import EntityId
from aidm.engines.hub import Campaign, Job, Offer
from aidm.engines.scenes.world import SceneRun


@dataclass(frozen=True, slots=True)
class HubNames:
    """What one engine's hub world is called: the hub run, the job run, the job's terms."""

    hub_place: str
    hub_title: str
    hub_question: str
    hub_situation: str
    job_place: str
    job_title: str
    job_question: str
    job_situation: str
    terms: str


BOARD = (
    Offer(title="Job One", pitch="I take job one."),
    Offer(title="Job Two", pitch="I take job two."),
)


def hub_runs(names: HubNames, *, keeper: EntityId) -> list[SceneRun]:
    return [
        SceneRun(
            place=names.hub_place,
            title=names.hub_title,
            question=names.hub_question,
            situation=names.hub_situation,
            here=[keeper],
        ),
        SceneRun(
            place=names.job_place,
            title=names.job_title,
            question=names.job_question,
            situation=names.job_situation,
            job=names.job_title,
        ),
    ]


def hub_campaign(names: HubNames) -> Campaign:
    return Campaign(
        place=names.hub_place,
        board=BOARD,
        jobs=[
            Job(
                title=names.job_title,
                place=names.job_place,
                terms=names.terms,
                open=True,
            )
        ],
    )
