import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from aidm.app.builtin import BuiltinSpawner
from aidm.app.spawn import CliSpawner, RunResult, Spawner, ask
from aidm.config import Role, Settings
from aidm.core.entities import Refusal
from aidm.core.facts import Fact, traced
from aidm.core.io import read_prompt
from aidm.core.model import AnyGame, WorldsmithAnswer
from aidm.core.play import Interjection, Narration, SceneRecord, SpokenLine
from aidm.core.prompt import lines_of, sections, told_history
from aidm.core.tools import schema_text
from aidm.core.views import NarratorView, Pairs, Subject
from aidm.engines.base import Person
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
class RoleSpawner:
    settings: Settings
    cli: CliSpawner
    builtin: BuiltinSpawner

    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult:
        config = self.settings.roles.for_name(role)
        played_by = self.cli if config.api is None else self.builtin
        return await played_by.run(role, prompt, session)


@dataclass(frozen=True, slots=True)
class Roles:
    """The three AI roles and how each is asked; committing what they answer is the caller's."""

    spawner: Spawner
    engine: AnyEngine

    async def master(self, turn: Turn) -> None:
        """A crashed game master still played the turn, if it applied anything legal first."""

        def nothing_landed() -> bool:
            return not turn.facts and turn.draft.pending is None

        prompt = turn.picture()
        for last in (False, True):
            try:
                await self.spawner.run("master", prompt, None)
                return
            except (OSError, Refusal) as failed:
                if not nothing_landed():
                    LOGGER.warning(
                        "the game master failed after applying %d facts: %s",
                        len(turn.facts),
                        failed,
                    )
                    return
                if last:
                    raise
                LOGGER.warning("the game master landed nothing, spawning it again: %s", failed)

    async def narrate(
        self, draft: AnyGame, facts: tuple[Fact, ...], prompt: str, *, fatal: bool
    ) -> tuple[SpokenLine, ...]:
        view = self.engine.narrator_view(draft)
        evidence = traced(facts, told_only=True)
        if (pending := draft.pending) is not None:
            evidence += f"\n- {PAUSED.format(prompt=pending.prompt)}"
        if draft.generation is not None:
            evidence += f"\n- {REQUESTED}"
        try:
            narration = await ask(
                self.spawner,
                "narrator",
                render_narrator(
                    view, evidence=evidence, prompt=prompt, scenes=self.engine.scenes(draft)
                ),
                Narration,
                view.narration_refusal,
            )
        except (OSError, Refusal) as failed:
            if fatal:
                raise
            # The scene cost minutes to write; an unwritable arrival must not throw it away.
            LOGGER.warning("the arrival went unnarrated: %s", failed)
            return ()
        return view.spoken(narration.lines)

    async def interject(self, state: AnyGame, member: Person) -> tuple[tuple[SpokenLine, ...], str]:
        view = self.engine.narrator_view(state)
        history = self.engine.history(state)
        evidence = traced(history[-1].facts if history else (), told_only=True)
        answer = await ask(
            self.spawner,
            "narrator",
            render_interjection(
                view, member.subject(), member.rows(), self.engine.scenes(state), evidence
            ),
            Interjection,
            partial(view.interjection_refusal, member.id),
        )
        return view.spoken(answer.lines), answer.proposal

    def worldsmith(self) -> WorldsmithAnswer:
        return partial(ask, self.spawner, "worldsmith")


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[SceneRecord]
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
    view: NarratorView,
    member: Subject,
    sheet: Pairs,
    scenes: Sequence[SceneRecord],
    evidence: str,
) -> str:
    role = read_prompt(PROMPTS_DIR / "interjection.md").format(
        name=member.label, brief=member.detail, id=member.id
    )
    return sections(
        (
            ("YOUR ROLE", role),
            (
                "YOUR SHEET",
                "\n".join(f"- {label}: {value}" for label, value in sheet) or "(none)",
            ),
            *_picture(view, scenes, evidence, reader=member),
            ("ANSWER WITH", schema_text(Interjection)),
        )
    )


def _picture(
    view: NarratorView,
    scenes: Sequence[SceneRecord],
    evidence: str,
    *,
    reader: Subject | None = None,
) -> Pairs:
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
        *((("WHAT THIS SCENE IS ABOUT", view.focus),) if view.focus else ()),
        ("WHO IS HERE", who_is_here),
        ("YOUR PARTY", party),
        ("THE PLAYER'S SHEET", lines_of(f"- {label}: {value}" for label, value in view.sheet)),
        ("WHAT HAPPENED", evidence),
    )
