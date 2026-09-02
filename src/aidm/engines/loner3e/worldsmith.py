from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.core.entities import Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import ScenarioKind, WorldsmithAnswer
from aidm.engines import scenes
from aidm.engines.loner3e.creation import Pack, guidance
from aidm.engines.loner3e.tools import close_conflicts
from aidm.engines.loner3e.world import Loner3eGame, LonerCharacter

# What `CAMPAIGN_OPENING` asks this engine's hub to be.
HUB_PHRASE = "a guild hall or a ship, whoever keeps it and the regulars"
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
GROWTH_NOTE = (
    "The job {title} is closed and was completed. The adventure's end applies: ask what the "
    "character learned if the player has not said, then write it once with `change_tags` and "
    "`drive`."
)


async def write_next(
    packs: Mapping[str, Pack], state: Loner3eGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    return await scenes.write_next(
        state.payload.world,
        intent,
        answer,
        cast_type=LonerCharacter,
        role=WORLDSMITH,
        guidance=guidance(packs, state.packs),
    )


def install_scene(state: Loner3eGame, written: BaseModel) -> tuple[Fact, ...]:
    # The conflicts close before the crossing: close_conflicts reads the scene being left.
    closed = close_conflicts(state)
    return (*closed, *scenes.install_scene(state, written, finished_note=GROWTH_NOTE))


def render_opening(
    packs: Mapping[str, Pack], source: str, picks: Sequence[Slug], kind: ScenarioKind
) -> str:
    return scenes.render_opening(
        LonerCharacter, WORLDSMITH, source, guidance(packs, picks), kind, HUB_PHRASE
    )
