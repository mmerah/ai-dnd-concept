from collections.abc import Callable
from dataclasses import dataclass
from random import Random

from pydantic_ai.usage import UsageLimits

from aidm.config import Role, Settings
from aidm.engines.engine import Engine, PlanContext, TurnLog
from aidm.state.model import Exchange, Game, StepTrace, Turn, narrator_evidence, narrator_lines

from . import prompts
from .agents import TurnAgents, exchanges_to_messages
from .scene import SceneSnapshot, VisibleScene


@dataclass(frozen=True, slots=True)
class TurnResult:
    state: Game
    turn: Turn


TURN_STEPS: tuple[str, ...] = ("director", "narrator")
DIRECTOR_REQUEST_LIMIT = 16
# ponytail: 4 chars/token estimate, swap for the provider's tokenizer if it starts misfiring
CHARS_PER_TOKEN = 4


async def run_turn(
    state: Game,
    prompt: str,
    *,
    engine: Engine,
    stages: TurnAgents,
    settings: Settings,
    rng: Random,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
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

    announce("director")
    director_prompt = prompts.render_director(scene, describe, draft.scenario, prompt)
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
    steps: list[StepTrace] = [
        StepTrace(name="director", prompt=director_prompt, output=directed.output),
        *log.steps,
    ]

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
    steps.append(
        StepTrace(name="narrator", prompt=narrator_prompt, output=narration.model_dump(mode="json"))
    )

    draft.history = (
        *draft.history,
        Exchange(prompt=prompt, lines=narration.lines, outcomes=narrator_lines(facts)),
    )
    draft.turn += 1
    return TurnResult(
        state=draft.committed(),
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration.text, steps=tuple(steps)),
    )


def _ensure_input_budget(role: Role, settings: Settings, rendered: str, history_chars: int) -> None:
    ceiling = settings.role(role).max_input_tokens
    estimate = (len(rendered) + history_chars) // CHARS_PER_TOKEN
    if estimate > ceiling:
        raise ValueError(
            f"{role} input is about {estimate} tokens, over its {ceiling}-token ceiling; "
            "this game has too much history for a turn to fit"
        )
