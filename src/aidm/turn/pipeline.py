from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel

from aidm.config import Settings
from aidm.engines.loader import Engine
from aidm.state.apply import apply_effect, fire_hooks
from aidm.state.base import Entity, EntityId, slug, text_slug
from aidm.state.facts import CORE, Fact, narrator_evidence
from aidm.state.plan import TurnPlanBase
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


TURN_STEPS: tuple[str, ...] = ("director", "resolve", "hooks", "narrator", "worldkeeper")


def resolve_plan(
    engine: Engine, draft: GameState, plan: TurnPlanBase, rng: Random
) -> tuple[GameState, list[Fact]]:
    """Returns the revalidated draft the rest of the turn builds on."""
    facts = engine.resolve_action(draft, plan, rng)
    return draft.committed().draft(), facts


def apply_hooks(draft: GameState, facts: Sequence[Fact]) -> tuple[GameState, list[Fact]]:
    """Runs before the Narrator, so a hook's consequences are narrated the turn they happen."""
    fired = fire_hooks(draft, facts)
    return (draft.committed().draft() if fired else draft), fired


def apply_report(
    draft: GameState, report: WorldkeeperReport, *, max_growth: int, max_memories: int
) -> list[Fact]:
    facts = [
        draft.add(_created_entity(creation, draft))
        for creation in admitted(report.creations, draft, max_growth)
    ]
    facts.extend(_remembered(report.memories, draft, max_memories))
    for move in report.thread_moves:
        facts.extend(apply_effect(draft, move))
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
    engine: Engine,
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
    # Notes are read once: the draft carries none forward, so the next turn shows only new ones.
    draft.world.pending_notes = ()
    steps.append(_traced("director", plan_prompt, plan))

    announce("resolve")
    draft, facts = resolve_plan(engine, draft, plan, rng)
    evidence = narrator_evidence(facts)
    steps.append(StepTrace(name="resolve", output=evidence))

    announce("hooks")
    draft, fired = apply_hooks(draft, facts)
    if fired:
        facts.extend(fired)
        evidence = narrator_evidence(facts)
    fired_trace = "\n".join(fact.trace for fact in fired) or "- (no hooks fired)"
    steps.append(StepTrace(name="hooks", output=fired_trace))

    announce("narrator")
    narrator_prompt = prompts.render_narrator(
        VisibleScene.of(SceneSnapshot.of(draft)),
        engine.renderer(draft),
        draft.scenario,
        focus=plan.focus,
        speaker_id=plan.speaker_id,
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
    facts.extend(
        apply_report(
            draft, report, max_growth=settings.max_growth, max_memories=settings.max_memories
        )
    )
    steps.append(_traced("worldkeeper", keeper_prompt, report))

    draft.history = (*draft.history, Exchange(prompt=prompt, narration=narration))
    draft.turn += 1
    engine.commit(draft)
    final = draft.committed()
    return TurnResult(
        state=final,
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration, steps=tuple(steps)),
    )


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
