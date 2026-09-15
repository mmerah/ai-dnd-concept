"""The three roles answering from `script.py`, so a recording carries authored prose."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import JsonValue

sys.path.insert(0, str(Path(__file__).parents[1] / "qa"))
from agents import ScriptedAgents, Spoken

sys.path.insert(0, str(Path(__file__).parent))
from script import BEATS, OPENING, Beat

SCENE = {
    "place": "undercroft-stair",
    "title": "The Undercroft Stair",
    "focus": "How far down does the stair go before the map stops matching it?",
    "situation": (
        "The flagstone lifts onto a stair the abbey's own plans deny: dressed stone for eight "
        "steps, then something older, cut rather than laid. The lantern reaches four steps down "
        "and stops. Somewhere below, water moves."
    ),
    "present": ["tomas"],
    "hidden": [],
    "cast": {
        "tomas": {
            "id": "tomas",
            "name": "Brother Tomas",
            "brief": "A deaf old porter who sweeps the cloister and knows every door in it.",
        }
    },
    "arc": "",
    "recap": "Kael took the vault map from Mara and put his weight on the flagstone.",
}


@dataclass(slots=True)
class DemoAgents(ScriptedAgents):
    """Plays the beats in order: the master's calls, then the narrator's authored lines."""

    calls: list[tuple[tuple[str, dict[str, JsonValue]], ...]] = field(default_factory=list)
    narrations: list[tuple[tuple[str | None, str], ...]] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, beats: tuple[Beat, ...] = BEATS, delay: float = 0.9) -> "DemoAgents":
        return cls(
            delay=delay,
            calls=[beat.calls for beat in beats],
            narrations=[OPENING, *_narrations(beats)],
        )

    async def _master(self, prompt: str, spoken: Spoken) -> None:
        del prompt
        played = self.calls.pop(0) if self.calls else ()
        for name, args in played:
            await self._call(name, args, spoken)
        self.answers.extend(answer for _, _, answer in spoken.calls)

    def _narrator(self, prompt: str) -> str:
        if "NARRATOR" not in prompt:
            return super()._narrator(prompt)
        lines = self.narrations.pop(0) if self.narrations else ()
        if not lines:
            lines = ((None, "(the demo script has no line for this turn)"),)
        return json.dumps(
            {"lines": [{"speaker_id": speaker, "text": text} for speaker, text in lines]}
        )

    def _worldsmith(self, prompt: str) -> str:
        schema = prompt[prompt.find("ANSWER WITH") :]
        if '"situation"' in schema:
            return json.dumps(SCENE)
        return super()._worldsmith(prompt)


def _narrations(beats: tuple[Beat, ...]) -> list[tuple[tuple[str | None, str], ...]]:
    """A turn that grows the world is narrated twice: what happened, then where the player is."""
    written: list[tuple[tuple[str | None, str], ...]] = []
    for beat in beats:
        written.append(beat.lines)
        if beat.after:
            written.append(beat.after)
    return written
