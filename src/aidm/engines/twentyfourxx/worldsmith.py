from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.core.entities import Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import ScenarioKind, WorldsmithAnswer
from aidm.engines import scenes
from aidm.engines.core import Person
from aidm.engines.twentyfourxx.creation import Pack, guidance
from aidm.engines.twentyfourxx.world import TwentyfourxxGame

HUB_PHRASE = "the fixer and the regulars"  # what `CAMPAIGN_OPENING` asks this engine's hub to be
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
BOARD_GUIDANCE = (
    "The SRD's job-finding setup is the board's range, not a recipe: 1–2 nothing, owe somebody to "
    "get in on a job; 3–4 found a job, but something seems off; 5–6 a choice between two jobs."
)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
JOB_DONE_NOTE = (
    "The job {title} is closed and was completed. The SRD's after-a-job step applies: call "
    "`job_done` once, with the skill the player names, else the skill the job called on."
)


async def write_next(
    packs: Mapping[str, Pack], state: TwentyfourxxGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    world = state.payload.world
    told = guidance(packs, state.packs)
    if world.hub is not None:  # the board's range on every campaign write
        told = "\n\n".join((told, BOARD_GUIDANCE))
    return await scenes.write_next(
        world, intent, answer, cast_type=Person, role=WORLDSMITH, guidance=told
    )


def install_scene(state: TwentyfourxxGame, written: BaseModel) -> tuple[Fact, ...]:
    return scenes.install_scene(state, written, finished_note=JOB_DONE_NOTE)


def render_opening(
    packs: Mapping[str, Pack], source: str, picks: Sequence[Slug], kind: ScenarioKind
) -> str:
    told = guidance(packs, picks)
    if kind == "campaign":
        told = "\n\n".join((told, BOARD_GUIDANCE))
    return scenes.render_opening(Person, WORLDSMITH, source, told, kind, HUB_PHRASE)
