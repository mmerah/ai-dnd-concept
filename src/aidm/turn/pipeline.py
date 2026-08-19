from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage

from aidm.config import Settings
from aidm.engines.engine import Engine
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import Transacted, transact
from aidm.state.base import Frozen, text_slug
from aidm.state.beat import Resolution
from aidm.state.facts import CORE, Fact, narrator_evidence
from aidm.state.history import Exchange
from aidm.state.trace import StepTrace, Turn
from aidm.state.world import GameState, Memory

from . import prompts
from .agents import PlanContext, TurnAgents, exchanges_to_messages
from .expansion import Expansions
from .reports import MemoryProposal
from .scene import SceneSnapshot, VisibleScene


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: GameState
    turn: Turn


TURN_STEPS: tuple[str, ...] = ("director", "resolve", "beat", "hooks", "narrator", "worldkeeper")


def remember(draft: GameState, memories: Sequence[MemoryProposal], maximum: int) -> list[Fact]:
    seen = {memory.text.casefold() for memory in draft.world.memories.values()}
    kept: list[Fact] = []
    for proposal in memories:
        normalized = proposal.text.casefold()
        if normalized in seen or len(kept) >= maximum:
            continue
        seen.add(normalized)
        memory = Memory(
            id=text_slug(proposal.text, draft.world.memories),
            owner=proposal.owner_id,
            text=proposal.text,
        )
        draft.world.memories[memory.id] = memory
        kept.append(
            Fact(
                source=CORE,
                kind="memory_kept",
                trace=f"remembered: {memory.text}",
                data={"memory_id": memory.id, "owner": memory.owner},
            )
        )
    return kept


@dataclass(frozen=True, slots=True)
class BeatRun:
    draft: GameState
    beats: tuple[Transacted, ...]
    steps: tuple[StepTrace, ...]


async def _ask_director(
    draft: GameState,
    prompt: str,
    step_name: str,
    *,
    engine: Engine[SheetBase],
    stages: TurnAgents,
    rng: Random,
    expansions: Expansions,
    history: Sequence[ModelMessage],
    happened: str = "",
    preface: str = "",
    settle: bool = False,
) -> tuple[Frozen, StepTrace]:
    """The first ask and every later beat render, call, and trace the Director the same way;
    only what they ask it to settle differs."""
    director_prompt = prompts.render_director(
        SceneSnapshot.of(draft),
        engine.renderer(draft),
        draft.scenario,
        prompt,
        happened=happened,
        preface=preface,
    )
    plan = (
        await stages.director.run(
            director_prompt,
            deps=PlanContext(
                engine=engine, state=draft, rng=rng, expansions=expansions, settle=settle
            ),
            message_history=history,
        )
    ).output
    # Each Director call consumes the notes its own prompt rendered, so a note a beat writes
    # steers the next beat of this turn — or the next turn, when no further call renders it.
    draft.world.pending_notes = ()
    return plan, _traced(step_name, director_prompt, plan)


async def _run_beats(
    draft: GameState,
    prompt: str,
    *,
    engine: Engine[SheetBase],
    stages: TurnAgents,
    settings: Settings,
    rng: Random,
    expansions: Expansions,
    history: Sequence[ModelMessage],
    announce: Callable[[str], None],
) -> BeatRun:
    """The first Director plan, then one more beat per roll — the cap and a roll that asks to
    settle both earn one last one."""
    steps: list[StepTrace] = []

    announce("director")
    plan, step = await _ask_director(
        draft,
        prompt,
        "director",
        engine=engine,
        stages=stages,
        rng=rng,
        expansions=expansions,
        history=history,
    )
    steps.append(step)

    announce("resolve")
    beats = [transact(engine, draft, _resolver(engine, plan, rng), rng)]
    draft = beats[-1].state.draft()
    while beats[-1].followup != "none":
        last = beats[-1].followup == "settle" or len(beats) >= settings.max_beats
        announce("beat")
        beat, step = await _ask_director(
            draft,
            prompt,
            f"beat-{len(beats)}",
            engine=engine,
            stages=stages,
            rng=rng,
            expansions=expansions,
            history=history,
            happened=narrator_evidence(beats[-1].facts),
            preface=prompts.SETTLE if last else prompts.BEAT,
            settle=last,
        )
        steps.append(step)
        announce("resolve")
        beats.append(transact(engine, draft, _resolver(engine, beat, rng), rng))
        draft = beats[-1].state.draft()
        if last:
            break

    return BeatRun(draft=draft, beats=tuple(beats), steps=tuple(steps))


async def run_turn(
    state: GameState,
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
    expansions = Expansions()
    run = await _run_beats(
        state.draft(),
        prompt,
        engine=engine,
        stages=stages,
        settings=settings,
        rng=rng,
        expansions=expansions,
        history=history,
        announce=announce,
    )
    draft, beats = run.draft, run.beats
    steps = list(run.steps)

    facts = [*expansions.facts, *(fact for beat in beats for fact in beat.facts)]
    steps.extend(expansions.steps)
    steps.append(
        StepTrace(
            name="resolve",
            output=narrator_evidence([fact for beat in beats for fact in beat.resolved]),
        )
    )

    announce("hooks")
    evidence = narrator_evidence(facts)
    fired = [fact.trace for beat in beats for fact in beat.fired]
    steps.append(StepTrace(name="hooks", output="\n".join(fired) or "- (no hooks fired)"))

    announce("narrator")
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
    reported = transact(
        engine,
        draft,
        lambda d: Resolution(facts=tuple(remember(d, report.memories, settings.max_memories))),
        rng,
    )
    draft = reported.state.draft()
    facts.extend(reported.facts)
    steps.append(_traced("worldkeeper", keeper_prompt, report))

    draft.history = (*draft.history, Exchange(prompt=prompt, lines=narration.lines))
    draft.turn += 1
    final = draft.committed()
    return TurnResult(
        state=final,
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration.text, steps=tuple(steps)),
    )


def _resolver(
    engine: Engine[SheetBase], beat: Frozen, rng: Random
) -> Callable[[GameState], Resolution]:
    return lambda draft: engine.resolve_beat(draft, beat, rng)


def _traced(name: str, rendered: str, output: BaseModel) -> StepTrace:
    return StepTrace(name=name, prompt=rendered, output=output.model_dump(mode="json"))
