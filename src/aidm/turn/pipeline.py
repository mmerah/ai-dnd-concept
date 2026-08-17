from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel

from aidm.config import Settings
from aidm.engines.loader import Engine
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import transact
from aidm.state.base import Entity, EntityId, slug, text_slug
from aidm.state.facts import CORE, Fact, narrator_evidence
from aidm.state.plan import DirectorBeat, Resolution
from aidm.state.turn import Creation, MemoryProposal, StepTrace, Turn, WorldkeeperReport
from aidm.state.world import Exchange, GameState, Memory

from . import prompts
from .roles import PlanContext, Stages, exchanges_to_messages
from .scene import SceneSnapshot, VisibleScene


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: GameState
    turn: Turn


TURN_STEPS: tuple[str, ...] = ("director", "resolve", "beat", "hooks", "narrator", "worldkeeper")


def apply_report(
    draft: GameState, report: WorldkeeperReport, *, max_growth: int, max_memories: int
) -> list[Fact]:
    facts = [
        draft.add(_created_entity(creation, draft))
        for creation in admitted(report.creations, draft, max_growth)
    ]
    facts.extend(_remembered(report.memories, draft, max_memories))
    return facts


def _remembered(proposals: Sequence[MemoryProposal], draft: GameState, maximum: int) -> list[Fact]:
    seen = {memory.text.casefold() for memory in draft.world.memories.values()}
    kept: list[Fact] = []
    for proposal in proposals:
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
    stages: Stages,
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
    snapshot = SceneSnapshot.of(state)

    announce("director")
    plan_prompt = prompts.render_director(snapshot, engine.renderer(state), state.scenario, prompt)
    plan = await stages.director.run(plan_prompt, PlanContext(engine=engine, state=state), history)
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
        beat = await stages.director.run(
            beat_prompt, PlanContext(engine=engine, state=draft, settle=last), history
        )
        draft.world.pending_notes = ()
        steps.append(_traced(f"beat-{len(beats)}", beat_prompt, beat))
        announce("resolve")
        beats.append(transact(engine, draft, _resolver(engine, beat, rng), rng))
        draft = beats[-1].state.draft()
        if last:
            break

    facts = [fact for beat in beats for fact in beat.facts]
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
    narrator_prompt = prompts.render_narrator(
        VisibleScene.of(SceneSnapshot.of(draft)),
        engine.renderer(draft),
        draft.scenario,
        evidence=evidence,
        prompt=prompt,
    )
    narration = await stages.narrator.run(narrator_prompt, None, history)
    if not narration:
        raise ValueError("the narrator answered with nothing")
    steps.append(StepTrace(name="narrator", prompt=narrator_prompt, output=narration))

    announce("worldkeeper")
    keeper_prompt = prompts.render_worldkeeper(
        SceneSnapshot.of(draft),
        engine.renderer(draft),
        draft.scenario,
        prompt=prompt,
        evidence=evidence,
        narration=narration,
    )
    report = await stages.worldkeeper.run(keeper_prompt, draft, history)
    reported = transact(
        engine,
        draft,
        lambda d: Resolution(
            facts=tuple(
                apply_report(
                    d, report, max_growth=settings.max_growth, max_memories=settings.max_memories
                )
            )
        ),
        rng,
    )
    draft = reported.state.draft()
    facts.extend(reported.facts)
    steps.append(_traced("worldkeeper", keeper_prompt, report))

    draft.history = (*draft.history, Exchange(prompt=prompt, narration=narration))
    draft.turn += 1
    final = draft.committed()
    return TurnResult(
        state=final,
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration, steps=tuple(steps)),
    )


def _resolver(
    engine: Engine[SheetBase], beat: DirectorBeat, rng: Random
) -> Callable[[GameState], Resolution]:
    return lambda draft: engine.resolve_beat(draft, beat, rng)


def _traced(name: str, rendered: str, output: BaseModel) -> StepTrace:
    return StepTrace(name=name, prompt=rendered, output=output.model_dump(mode="json"))


def admitted(creations: Sequence[Creation], state: GameState, maximum: int) -> tuple[Creation, ...]:
    """Locations sort first so an entity placed at one created this same report resolves."""
    seen = {entity.name.casefold() for entity in state.world.entities.values()}
    kept: list[Creation] = []
    for creation in creations:
        normalized = creation.name.casefold()
        if normalized in seen or len(kept) >= maximum:
            continue
        kept.append(creation)
        seen.add(normalized)
    return tuple(sorted(kept, key=lambda creation: creation.kind != "location"))


def _created_entity(creation: Creation, state: GameState) -> Entity:
    return Entity(
        id=slug(creation.name, state.world.all_ids()),
        kind=creation.kind,
        name=creation.name,
        brief=creation.brief,
        detail=creation.detail,
        known=True,
        parent_id=None if creation.kind == "location" else _placed(creation, state),
    )


def _placed(creation: Creation, state: GameState) -> EntityId:
    if creation.location is not None:
        wanted = creation.location.casefold()
        for entity in state.world.of_kind("location"):
            if entity.name.casefold() == wanted:
                return entity.id
    return state.player_location
