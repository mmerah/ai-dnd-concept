from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random

from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import UsageLimits

from aidm.config import Role, Settings
from aidm.engines.core import (
    Advancement,
    Engine,
    Offer,
    PlanContext,
    ProposalBase,
    TurnLog,
    act,
    sequential_toolset,
    with_enum,
)
from aidm.llm import build_agent
from aidm.state import actions
from aidm.state.model import (
    PLAYER_ID,
    AdvanceThread,
    EntityId,
    Exchange,
    Fact,
    Game,
    MechanicEvent,
    Narration,
    Slug,
    StepTrace,
    Turn,
    narrator_evidence,
)

from . import context
from .context import SceneSnapshot, VisibleScene


def core_toolset() -> AbstractToolset[PlanContext]:
    def reveal(ctx: RunContext[PlanContext], entity_id: EntityId) -> str:
        """Reveal an entity that exists but the player does not know yet: they notice it, are told
        of it, or reach it.

        Args:
            entity_id: Exact id of the unrevealed canon entity.
        """
        return _resolved(ctx, lambda draft: actions.reveal(draft, entity_id))

    def move(ctx: RunContext[PlanContext], entity_id: EntityId, to_id: EntityId) -> str:
        """Move an actor who actually changes location, or one item within the player's reach:
        picked up, set down here, or handed to an actor here.

        Args:
            entity_id: Exact id of the actor or item that moves; `player` is the played character.
                An item must be one the player carries, or one loose at their location.
            to_id: Exact id of where it goes: for an actor the location they enter; for an item,
                `player` to pick it up, an actor here with the player to hand it over, or the
                player's own location to set it down.
        """
        return _resolved(ctx, lambda draft: actions.move(draft, entity_id, to_id))

    def gain_improvised_item(ctx: RunContext[PlanContext], item_name: str) -> str:
        """Give the player an ordinary incidental object that is not in canon and is not worth a
        canon entry of its own.

        Args:
            item_name: The object written out, such as 'a handful of gravel'.
        """
        return _resolved(ctx, lambda draft: actions.improvise(draft, item_name))

    def add_trait(
        ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug, text: str
    ) -> str:
        """Put a lasting condition, skill, or frailty on an entity.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Stable slug for the trait, such as `poisoned`; it shows written out, so
                `battle-worn` appears as Battle Worn.
            text: The constraint or benefit it puts on the entity, in prose.
        """
        return _resolved(ctx, lambda draft: actions.add_trait(draft, entity_id, trait_id, text))

    def remove_trait(ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug) -> str:
        """Lift a lasting condition, skill, or frailty the fiction has ended.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Exact id of a trait the entity carries.
        """
        return _resolved(ctx, lambda draft: actions.remove_trait(draft, entity_id, trait_id))

    def advance_thread(ctx: RunContext[PlanContext], advance: AdvanceThread) -> str:
        """Move a storyline the scenario is tracking: where it stands now, or that it is over.

        Args:
            advance: The movement to apply.
        """
        return _resolved(ctx, lambda draft: actions.advance_thread(draft, advance))

    def unlock_exit(ctx: RunContext[PlanContext], to_id: EntityId) -> str:
        """Open a locked way out of the player's location.

        Args:
            to_id: Exact id of the location the way leads to.
        """
        return _resolved(ctx, lambda draft: actions.unlock_exit(draft, to_id))

    def join_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor into the player's party.

        Args:
            actor_id: Exact id of the actor joining, who must be here with the player.
        """
        return _resolved(ctx, lambda draft: actions.join_party(draft, actor_id))

    def leave_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Take an actor out of the player's party when the fiction parts them.

        Args:
            actor_id: Exact id of the actor leaving.
        """
        return _resolved(ctx, lambda draft: actions.leave_party(draft, actor_id))

    return sequential_toolset(
        [
            reveal,
            move,
            gain_improvised_item,
            add_trait,
            remove_trait,
            advance_thread,
            unlock_exit,
            join_party,
            leave_party,
        ]
    ).prepared(_narrow_unlock_targets)


def _resolved(ctx: RunContext[PlanContext], apply: Callable[[Game], list[Fact]]) -> str:
    return act(ctx, lambda draft, _rng: tuple(apply(draft)))


def _unlock_targets(state: Game) -> list[str]:
    here = state.world.require_kind(state.player_location, "location")
    return sorted(w.to for w in here.exits if w.locked)


def _narrow_unlock_targets(
    ctx: RunContext[PlanContext], tools: list[ToolDefinition]
) -> list[ToolDefinition]:
    # This runs before the `possible()` filter drops `unlock_exit`, so with nothing locked the tool
    # is still here and an enum would be empty: no legal value at all.
    targets = _unlock_targets(ctx.deps.state)
    return [
        with_enum(tool, ("to_id",), targets) if tool.name == "unlock_exit" and targets else tool
        for tool in tools
    ]


def _a_locked_way_out(state: Game) -> bool:
    return bool(_unlock_targets(state))


def _an_actor_to_recruit(state: Game) -> bool:
    return any(
        entity.kind == "actor" and entity.id != PLAYER_ID and entity.id not in state.world.party
        for entity in state.world.entities
        if state.is_here(entity)
    )


def _a_party_member(state: Game) -> bool:
    return bool(state.world.party)


def _an_unresolved_thread(state: Game) -> bool:
    # The set the scene renders under ACTIVE THREADS: a thread put dormant is still movable.
    return any(thread.status != "resolved" for thread in state.world.threads)


def _a_trait_in_reach(state: Game) -> bool:
    # `is_here` is false of a location, which carries tags of its own that `add_trait` may write.
    return any(
        entity.traits
        for entity in state.world.entities
        if state.is_here(entity) or entity.id == state.player_location
    )


_APPLIES: Mapping[str, Callable[[Game], bool]] = {
    "unlock_exit": _a_locked_way_out,
    "join_party": _an_actor_to_recruit,
    "leave_party": _a_party_member,
    "advance_thread": _an_unresolved_thread,
    "remove_trait": _a_trait_in_reach,
}


def possible(name: str, state: Game) -> bool:
    applies = _APPLIES.get(name)
    return applies is None or applies(state)


@dataclass(frozen=True, slots=True)
class AdvancementContext:
    advancement: Advancement
    state: Game
    offer: Offer


@dataclass(frozen=True, slots=True)
class TurnAgents:
    director: Agent[PlanContext, str]
    narrator: Agent[VisibleScene, Narration]


def director_agent(
    engine: Engine,
    settings: Settings,
) -> Agent[PlanContext, str]:
    """Everything that happens this turn happens through a tool; the closing text only traces."""
    toolsets: list[AbstractToolset[PlanContext]] = [
        core_toolset().filtered(lambda ctx, tool: possible(tool.name, ctx.deps.state)),
        *engine.director_toolsets,
    ]
    return build_agent(
        "director",
        settings,
        instructions=context.director_instructions(engine.director_instructions),
        output_type=str,
        deps_type=PlanContext,
        toolsets=toolsets,
    )


def narrator_agent(settings: Settings) -> Agent[VisibleScene, Narration]:
    def attributed(ctx: RunContext[VisibleScene], narration: Narration) -> Narration:
        """The leak rule holds through the validator, not through trust."""
        present = {ctx.deps.player.id, *(entity.id for entity in ctx.deps.here)}
        strangers = sorted(
            {
                line.speaker_id
                for line in narration.lines
                if line.speaker_id is not None and line.speaker_id not in present
            }
        )
        if strangers:
            raise ModelRetry(
                f"nobody here has id {', '.join(strangers)}. Only the player or someone here with "
                "them speaks; leave `speaker_id` null for narration."
            )
        return narration

    return build_agent(
        "narrator",
        settings,
        instructions=context.NARRATOR,
        output_type=NativeOutput(Narration),
        deps_type=VisibleScene,
        validator=attributed,
    )


def advisor_agent(
    advancement: Advancement, settings: Settings
) -> Agent[AdvancementContext, ProposalBase]:
    def legal(ctx: RunContext[AdvancementContext], proposal: ProposalBase) -> ProposalBase:
        deps = ctx.deps
        refused = deps.advancement.violation(deps.state, deps.offer, proposal)
        if refused is not None:
            raise ModelRetry(refused)
        return proposal

    return build_agent(
        "advisor",
        settings,
        instructions=context.advisor_instructions(advancement.instructions),
        output_type=NativeOutput(advancement.proposal_type),
        deps_type=AdvancementContext,
        validator=legal,
    )


def build_turn_agents(engine: Engine, settings: Settings) -> TurnAgents:
    return TurnAgents(director=director_agent(engine, settings), narrator=narrator_agent(settings))


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages


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
    on_event: Callable[[MechanicEvent], None] | None = None,
) -> TurnResult:
    def announce(step: str) -> None:
        if on_step is not None:
            on_step(step)

    history = exchanges_to_messages(state.history)
    history_chars = sum(
        len(exchange.prompt) + len(exchange.narration) for exchange in state.history
    )
    log = TurnLog(on_event=on_event)
    draft = state.draft()

    scene, describe = SceneSnapshot.of(draft), engine.renderer(draft)

    announce("director")
    director_prompt = context.render_director(scene, describe, draft.scenario, prompt)
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
    narrator_prompt = context.render_narrator(
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
        Exchange(prompt=prompt, lines=narration.lines, events=tuple(log.events)),
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
