from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel

from aidm.config import Settings
from aidm.engines.engine import Engine
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import transact
from aidm.state.base import Frozen, text_slug
from aidm.state.beat import Resolution
from aidm.state.facts import CORE, Fact, narrator_evidence
from aidm.state.trace import StepTrace, Turn
from aidm.state.world import Exchange, GameState, Memory

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
    steps: list[StepTrace] = []
    draft = state.draft()
    snapshot = SceneSnapshot.of(draft)
    expansions = Expansions()

    announce("director")
    plan_prompt = prompts.render_director(snapshot, engine.renderer(draft), draft.scenario, prompt)
    plan = (
        await stages.director.run(
            plan_prompt,
            deps=PlanContext(engine=engine, state=draft, rng=rng, expansions=expansions),
            message_history=history,
        )
    ).output
    # Each Director call consumes the notes its own prompt rendered, so a note a beat writes
    # steers the next beat of this turn — or the next turn, when no further call renders it.
    draft.world.pending_notes = ()
    steps.append(_traced("director", plan_prompt, plan))

    announce("resolve")
    beats = [transact(engine, draft, _resolver(engine, plan, rng), rng)]
    draft = beats[-1].state.draft()
    # A roll earns another beat; the cap and a roll that asks to settle both earn one last one.
    while beats[-1].followup != "none":
        last = beats[-1].followup == "settle" or len(beats) >= settings.max_beats
        announce("beat")
        beat_prompt = prompts.render_director(
            SceneSnapshot.of(draft),
            engine.renderer(draft),
            draft.scenario,
            prompt,
            happened=narrator_evidence(beats[-1].facts),
            preface=prompts.SETTLE if last else prompts.BEAT,
        )
        beat = (
            await stages.director.run(
                beat_prompt,
                deps=PlanContext(
                    engine=engine, state=draft, rng=rng, expansions=expansions, settle=last
                ),
                message_history=history,
            )
        ).output
        draft.world.pending_notes = ()
        steps.append(_traced(f"beat-{len(beats)}", beat_prompt, beat))
        announce("resolve")
        beats.append(transact(engine, draft, _resolver(engine, beat, rng), rng))
        draft = beats[-1].state.draft()
        if last:
            break

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
