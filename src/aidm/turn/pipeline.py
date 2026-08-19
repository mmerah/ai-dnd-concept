import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.usage import UsageLimits

from aidm.config import Settings
from aidm.engines.engine import Engine, PlanContext, TurnLog
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import apply_to_draft
from aidm.state.facts import Fact, narrator_evidence, narrator_lines
from aidm.state.history import Exchange
from aidm.state.resolution import Resolution
from aidm.state.trace import StepTrace, Turn
from aidm.state.world import Game, Memory

from . import prompts
from .agents import TurnAgents, exchanges_to_messages
from .reports import MemoryProposal, TurnInterpretation
from .scene import SceneSnapshot, VisibleScene

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: Game
    turn: Turn


TURN_STEPS: tuple[str, ...] = ("interpreter", "director", "hooks", "narrator", "worldkeeper")
DIRECTOR_REQUEST_LIMIT = 16


def remember(draft: Game, memories: Sequence[MemoryProposal], maximum: int) -> list[Fact]:
    seen = {memory.text.casefold() for memory in draft.world.memories}
    kept: list[Fact] = []
    for proposal in memories:
        normalized = proposal.text.casefold()
        if normalized in seen or len(kept) >= maximum:
            continue
        seen.add(normalized)
        memory = Memory(owner=proposal.owner_id, text=proposal.text)
        draft.world.memories.append(memory)
        kept.append(
            Fact(
                kind="memory_kept",
                trace=f"remembered: {memory.text}",
                data={"owner": memory.owner},
            )
        )
    return kept


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

    history = exchanges_to_messages(state.history[-settings.history_window :])
    log = TurnLog()
    draft = state.draft()

    scene, describe = SceneSnapshot.of(draft), engine.renderer(draft)

    announce("interpreter")
    interpreter_prompt = prompts.render_interpreter(scene, describe, draft.scenario, prompt)
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

    announce("hooks")
    steps.append(
        StepTrace(
            name="hooks", output="\n".join(fact.trace for fact in log.fired) or "- (no hooks fired)"
        )
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
    narration = (
        await stages.narrator.run(narrator_prompt, deps=visible, message_history=history)
    ).output
    if not narration.text:
        raise ValueError("the narrator answered with nothing")
    steps.append(_traced("narrator", narrator_prompt, narration))

    announce("worldkeeper")
    keeper_prompt = prompts.render_worldkeeper(
        SceneSnapshot.of(draft),
        engine.renderer(draft),
        draft.scenario,
        prompt=prompt,
        evidence=evidence,
        narration=narration.text,
    )
    report = (
        await stages.worldkeeper.run(keeper_prompt, deps=draft, message_history=history)
    ).output
    kept = apply_to_draft(
        engine,
        draft,
        lambda copy, _rng: Resolution(
            facts=tuple(remember(copy, report.memories, settings.max_memories))
        ),
        rng,
    )
    facts.extend(kept.facts)
    steps.append(_traced("worldkeeper", keeper_prompt, report))

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
