from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.core.entities import Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import ScenarioKind, WorldsmithAnswer
from aidm.engines import scenes
from aidm.engines.breathless.creation import Pack, guidance
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.core import Person

# What `CAMPAIGN_OPENING` asks this engine's hub to be.
HUB_PHRASE = "a camp or a safe house, whoever holds it and the regulars"
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)


async def write_next(
    packs: Mapping[str, Pack], state: BreathlessGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    return await scenes.write_next(
        state.payload.world,
        intent,
        answer,
        cast_type=Person,
        role=WORLDSMITH,
        guidance=guidance(packs, state.packs),
    )


def install_scene(state: BreathlessGame, written: BaseModel) -> tuple[Fact, ...]:
    return scenes.install_scene(state, written, finished_note="")


def render_opening(
    packs: Mapping[str, Pack], source: str, picks: Sequence[Slug], kind: ScenarioKind
) -> str:
    return scenes.render_opening(
        Person, WORLDSMITH, source, guidance(packs, picks), kind, HUB_PHRASE
    )
