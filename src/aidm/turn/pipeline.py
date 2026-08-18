from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import BaseModel

from aidm.config import Settings
from aidm.engines.loader import Engine
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import transact
from aidm.state.base import Entity, EntityId, slug, text_slug
from aidm.state.facts import CORE, Fact, explained_fact, narrator_evidence
from aidm.state.plan import DirectorBeat, Resolution
from aidm.state.turn import Creation, MemoryProposal, StepTrace, Turn, WorldkeeperReport
from aidm.state.world import CONNECTED, Exchange, GameState, Memory, Relation

from . import prompts
from .expansion import Expansions
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
    facts: list[Fact] = []
    for creation in admitted(report.creations, draft, max_growth):
        # Resolved before the entity exists, so a location cannot name itself as its own anchor.
        anchor = _placed(creation, draft)
        entity = _created_entity(creation, draft, anchor)
        facts.append(draft.add(entity))
        if entity.kind == "location":
            facts.append(_connect(draft, entity, anchor))
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
    snapshot = SceneSnapshot.of(draft)
    expansions = Expansions()

    announce("director")
    plan_prompt = prompts.render_director(snapshot, engine.renderer(draft), draft.scenario, prompt)
    plan = await stages.director.run(
        plan_prompt,
        PlanContext(engine=engine, state=draft, rng=rng, expansions=expansions),
        history,
    )
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
            beat_prompt,
            PlanContext(engine=engine, state=draft, rng=rng, expansions=expansions, settle=last),
            history,
        )
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
    narration = await stages.narrator.run(narrator_prompt, visible, history)
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

    draft.history = (*draft.history, Exchange(prompt=prompt, lines=narration.lines))
    draft.turn += 1
    final = draft.committed()
    return TurnResult(
        state=final,
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration.text, steps=tuple(steps)),
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


def _created_entity(creation: Creation, state: GameState, anchor_id: EntityId) -> Entity:
    return Entity(
        id=slug(creation.name, state.world.all_ids()),
        kind=creation.kind,
        name=creation.name,
        brief=creation.brief,
        detail=creation.detail,
        known=True,
        parent_id=None if creation.kind == "location" else anchor_id,
    )


def _placed(creation: Creation, state: GameState) -> EntityId:
    """The location the `location` field names: where a person or thing stands, and the place a new
    location is joined to. Nothing named puts it where the player is."""
    if creation.location is not None:
        wanted = creation.location.casefold()
        for entity in state.world.of_kind("location"):
            if entity.name.casefold() == wanted:
                return entity.id
    return state.player_location


def _connect(draft: GameState, location: Entity, anchor_id: EntityId) -> Fact:
    """Movement follows `connected` relations alone, so a created location arrives joined to one
    the player can already reach."""
    anchor = draft.world.require(anchor_id)
    # A known way may not name an entity the player has not met.
    relation = Relation(
        kind=CONNECTED, source=location.id, target=anchor.id, directed=False, known=anchor.known
    )
    draft.world.relations[relation.id] = relation
    joined = f"{location.name} — {CONNECTED} — {anchor.name}"
    # The trace names the anchor, so an unmet one keeps the whole line out of player-facing prose.
    return explained_fact(
        location,
        "relation_added",
        joined,
        {"kind": CONNECTED, "target": anchor.id},
        "",
        narrate=anchor.known,
    )
