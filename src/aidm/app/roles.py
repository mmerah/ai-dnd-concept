import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from aidm.app.builtin import run_builtin
from aidm.app.spawn import DRIVERS, RETRIES, RunResult, Spawner, Tools, ask, run_cli
from aidm.config import Role, Settings
from aidm.core.entities import Refusal
from aidm.core.facts import Fact, traced
from aidm.core.io import read_prompt
from aidm.core.model import AnyGame
from aidm.core.play import Chapter, Interjection, Narration, SpokenLine
from aidm.core.prompt import Sections, lines_of, section_if, sections, told_history
from aidm.core.tools import schema_text
from aidm.core.views import Companion, NarratorView, Subject
from aidm.engines.seam import AnyEngine
from aidm.turn.run import Turn

LOGGER = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
PAUSED = (
    'play pauses here on the player\'s decision: "{prompt}" End on the pause; settle nothing they '
    "have not yet answered."
)
REQUESTED = (
    "play stops here while the world is written on; end on this moment and settle nothing "
    "beyond what happened."
)


@dataclass(frozen=True, slots=True)
class RoleRunner:
    settings: Settings

    async def run(
        self, role: Role, prompt: str, session: str | None, tools: Tools | None = None
    ) -> RunResult:
        config = self.settings.roles.for_name(role)
        match config.provider:
            case "claude" | "codex":
                driver = DRIVERS[config.provider]
                return await run_cli(
                    role, config, driver, self.settings.server_port, prompt, session
                )
            case "openrouter" | "local":
                provider = self.settings.providers.for_name(config.provider)
                return await run_builtin(role, config, provider, prompt, tools)


@dataclass(frozen=True, slots=True)
class Roles:
    spawner: Spawner

    async def master(self, turn: Turn) -> None:
        """A crashed game master still played the turn, if it applied anything legal first."""
        prompt = turn.picture()
        for attempt in range(RETRIES + 1):
            try:
                await self.spawner.run("master", prompt, None, turn)
                return
            except Refusal as failed:
                if turn.landed():
                    LOGGER.warning(
                        "the game master failed after applying %d facts: %s",
                        len(turn.facts),
                        failed,
                    )
                    return
                if attempt == RETRIES:
                    raise
                LOGGER.warning("the game master landed nothing, spawning it again: %s", failed)

    async def narrate(
        self,
        engine: AnyEngine,
        draft: AnyGame,
        facts: tuple[Fact, ...],
        prompt: str,
    ) -> tuple[SpokenLine, ...]:
        view = engine.narrator_view(draft)
        evidence = traced(facts, told_only=True)
        if (pending := draft.pending) is not None:
            evidence += f"\n- {PAUSED.format(prompt=pending.prompt)}"
        if draft.generation is not None:
            evidence += f"\n- {REQUESTED}"
        narration = await ask(
            self.spawner,
            "narrator",
            render_narrator(
                view,
                evidence=evidence,
                prompt=prompt,
                scenes=draft.log,
            ),
            Narration,
            view.check_narration,
        )
        return view.spoken(narration.lines)

    async def interject(
        self, engine: AnyEngine, state: AnyGame, member: Companion
    ) -> tuple[tuple[SpokenLine, ...], str]:
        view = engine.narrator_view(state)
        history = state.exchanges()
        evidence = traced(history[-1].facts if history else (), told_only=True)
        answer = await ask(
            self.spawner,
            "narrator",
            render_interjection(view, member, state.log, evidence),
            Interjection,
            partial(view.check_interjection, member.id),
        )
        return view.spoken(answer.lines), answer.proposal


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[Chapter]
) -> str:
    return sections(
        (
            ("YOUR ROLE", read_prompt(PROMPTS_DIR / "narrator.md")),
            *_picture(view, scenes, evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


def render_interjection(
    view: NarratorView, member: Companion, scenes: Sequence[Chapter], evidence: str
) -> str:
    role = read_prompt(PROMPTS_DIR / "interjection.md").format(
        name=member.label, brief=member.detail, id=member.id
    )
    return sections(
        (
            ("YOUR ROLE", role),
            (
                "YOUR SHEET",
                "\n".join(f"- {label}: {value}" for label, value in member.sheet) or "(none)",
            ),
            *_picture(view, scenes, evidence, reader=member),
            ("ANSWER WITH", schema_text(Interjection)),
        )
    )


def _picture(
    view: NarratorView,
    scenes: Sequence[Chapter],
    evidence: str,
    *,
    reader: Subject | None = None,
) -> Sections:
    """`reader` is who reads it: nobody (the player themself) or a member reading about them."""
    lead, beside = ("you are", "with you") if reader is None else ("the player is", "with them")
    subjects = {subject.id: subject for subject in view.subjects}
    first, *rest = (subjects[member_id] for member_id in view.party)
    members = [f"{beside}: {member.headline}" for member in rest]
    party = "\n".join((f"{lead} {first.headline}", *(members or [f"nobody travels {beside}"])))
    others = view.others()
    who_is_here = (
        lines_of(f"- {subject.headline}" for subject in others) if others else "(nobody else)"
    )
    return (
        ("WHAT THE PLAYER HAS READ", told_history(scenes)),
        ("SCENE", f"{view.title}\n{view.situation}"),
        *section_if("WHAT THIS SCENE IS ABOUT", view.focus),
        ("WHO IS HERE", who_is_here),
        ("YOUR PARTY", party),
        ("THE PLAYER'S SHEET", lines_of(f"- {label}: {value}" for label, value in view.sheet)),
        ("WHAT HAPPENED", evidence),
    )
