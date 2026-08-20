import logging
from collections.abc import Callable
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.usage import UsageLimits

from aidm.config import Role, Settings
from aidm.engines.engine import Engine, PlanContext, TurnLog
from aidm.engines.sheets import SheetBase
from aidm.state.facts import narrator_evidence, narrator_lines
from aidm.state.history import Exchange
from aidm.state.trace import StepTrace, Turn
from aidm.state.world import Game

from . import prompts
from .agents import TurnAgents, exchanges_to_messages
from .reports import TurnInterpretation
from .scene import SceneSnapshot, VisibleScene

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: Game
    turn: Turn


TURN_STEPS: tuple[str, ...] = ("interpreter", "director", "narrator")
DIRECTOR_REQUEST_LIMIT = 16
# ponytail: 4 chars/token estimate, swap for the provider's tokenizer if it starts misfiring
CHARS_PER_TOKEN = 4


async def run_turn(
    state: Game,
    prompt: str,
    *,
    engine: Engine[SheetBase],
    stages: TurnAgents,
    settings: Settings,
    rng: Random,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    """A new role is one more explicit call in this sequence."""

    def announce(step: str) -> None:
        if on_step is not None:
            on_step(step)

    history = exchanges_to_messages(state.history)
    history_chars = sum(
        len(exchange.prompt) + len(exchange.narration) for exchange in state.history
    )
    log = TurnLog()
    draft = state.draft()

    scene, describe = SceneSnapshot.of(draft), engine.renderer(draft)

    announce("interpreter")
    interpreter_prompt = prompts.render_interpreter(scene, describe, draft.scenario, prompt)
    _ensure_input_budget("interpreter", settings, interpreter_prompt, history_chars)
    plan: TurnInterpretation | None = None
    try:
        plan = (await stages.interpreter.run(interpreter_prompt, message_history=history)).output
    except UnexpectedModelBehavior as unread:
        # Advisory, like the Expander: a plan nobody could read costs the turn its plan, not the
        # turn — the Director judged the mechanics alone before this role existed.
        LOGGER.warning("no plan was read: %s", unread)
    steps: list[StepTrace] = [
        StepTrace(
            name="interpreter",
            prompt=interpreter_prompt,
            output=None if plan is None else plan.model_dump(mode="json"),
        )
    ]

    announce("director")
    director_prompt = prompts.render_director(scene, describe, draft.scenario, prompt, plan)
    _ensure_input_budget("director", settings, director_prompt, history_chars)
    shown = len(draft.world.pending_notes)
    directed = await stages.director.run(
        director_prompt,
        deps=PlanContext(engine=engine, state=draft, rng=rng, log=log),
        message_history=history,
        usage_limits=UsageLimits(request_limit=DIRECTOR_REQUEST_LIMIT),
    )
    # Only what the prompt rendered is spent; a note its own tools wrote steers the next turn too.
    draft.world.pending_notes = draft.world.pending_notes[shown:]
    facts = list(log.facts)
    steps.extend(
        (StepTrace(name="director", prompt=director_prompt, output=directed.output), *log.steps)
    )

    announce("narrator")
    evidence = narrator_evidence(facts)
    visible = VisibleScene.of(SceneSnapshot.of(draft))
    narrator_prompt = prompts.render_narrator(
        visible,
        engine.renderer(draft),
        draft.scenario,
        evidence=evidence,
        prompt=prompt,
    )
    _ensure_input_budget("narrator", settings, narrator_prompt, history_chars)
    narration = (
        await stages.narrator.run(narrator_prompt, deps=visible, message_history=history)
    ).output
    if not narration.text:
        raise ValueError("the narrator answered with nothing")
    steps.append(_traced("narrator", narrator_prompt, narration))

    draft.history = (
        *draft.history,
        Exchange(prompt=prompt, lines=narration.lines, outcomes=narrator_lines(facts)),
    )
    draft.turn += 1
    return TurnResult(
        state=draft.committed(),
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration.text, steps=tuple(steps)),
    )


def _traced(name: str, rendered: str, output: BaseModel) -> StepTrace:
    return StepTrace(name=name, prompt=rendered, output=output.model_dump(mode="json"))


def _ensure_input_budget(role: Role, settings: Settings, rendered: str, history_chars: int) -> None:
    ceiling = settings.role(role).max_input_tokens
    estimate = (len(rendered) + history_chars) // CHARS_PER_TOKEN
    if estimate > ceiling:
        raise ValueError(
            f"{role} input is about {estimate} tokens, over its {ceiling}-token ceiling; "
            "this game has too much history for a turn to fit"
        )
