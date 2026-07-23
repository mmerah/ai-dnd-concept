"""ACTOR — turns the Director's guidance into mechanics. Tools resolve in Python; the model only
chooses which to call."""

from dataclasses import dataclass, field
from functools import cache
from random import Random
from typing import Literal

from pydantic_ai import Agent, ModelRetry, RunContext

from ..domain.events import (
    EntityDiscovered,
    Event,
    HpChanged,
    InventoryChanged,
    Moved,
    apply,
)
from ..domain.models import Ability, GameState, find, find_by_name
from ..engine import rules
from .llm import RETRIES, model

INSTRUCTIONS = """You are the ACTOR of a tabletop RPG engine. You never write prose and you never \
decide outcomes. You call the tools that carry out the Director's guidance, and nothing else.

HOW TO READ THE GUIDANCE
The guidance is the plan for this turn. Work through it in order.
1. If it names a check, call `ability_check` first, with the ability and DC it gives you. The \
tool tells you whether the roll succeeded.
2. Now re-read the guidance's sentence for the branch that actually happened — the success \
sentence if the roll succeeded, the failure sentence if it failed — and call one tool for every \
concrete thing that sentence names. Stopping after `ability_check` is the most common mistake: \
the roll alone changes nothing, and a consequence you do not call did not happen.
3. If the guidance names no check, apply what it describes directly.

The tools are the only record of this turn. Whoever writes the story afterwards sees nothing but \
the events you produce, so anything you leave uncalled will be missing from the world even if it \
was obviously meant to happen.

WHICH TOOL TO USE
- the character gains or loses an object: `modify_inventory`
- the player learns of, is told about, is pointed to, or finds a person, place or item that \
already exists but was unknown to them: `discover_entity`
- the character goes somewhere: `move_to`
- the character is hurt or healed: `modify_hp`

NAMES
`discover_entity` accepts only something listed above under what the player knows or does not \
know yet, written exactly as it appears there. Scenery, furniture, dust, doors, ledgers and \
anything else absent from those lists is not an entity: it needs no tool at all, and trying to \
reveal it is an error. Never invent a name the guidance did not give you.

When the guidance genuinely describes nothing that changes — small talk, a look around, a refusal \
— calling no tool at all is correct.

When you are finished, reply with one short factual sentence naming the tools you called. Never \
write prose, dialogue or description."""


@dataclass
class ActorDeps:
    state: GameState
    rng: Random
    events: list[Event] = field(default_factory=list)

    @property
    def draft(self) -> GameState:
        """Tools validate against the turn so far, not against the turn's starting state."""
        return apply(self.state, self.events)


def _emit(ctx: RunContext[ActorDeps], *events: Event) -> str:
    ctx.deps.events.extend(events)
    return "\n".join(e.summary for e in events)


async def ability_check(ctx: RunContext[ActorDeps], ability: Ability, dc: int) -> str:
    """Roll a d20 + ability modifier against a difficulty class."""
    return _emit(ctx, rules.roll_check(ctx.deps.draft.character, ability, dc, ctx.deps.rng))


async def modify_inventory(
    ctx: RunContext[ActorDeps], item: str, delta: Literal[1, -1]
) -> str:
    """Give the character an item (delta 1) or take one away (delta -1)."""
    draft = ctx.deps.draft
    # canonical name, so canon and inventory agree; the model passes an id about as often as a name
    entity = find_by_name(draft.scenario, item) or find(draft.scenario, item)
    name = entity.name if entity else item
    if delta < 0 and name not in draft.character.inventory:
        raise ModelRetry(f"{name!r} is not in the inventory.")
    events: list[Event] = [InventoryChanged(item=name, delta=delta)]
    if entity is not None and not entity.known and delta > 0:
        # taking a thing is learning of it; leaving that to the model desynced canon in practice
        events.insert(0, EntityDiscovered(entity_id=entity.id, name=entity.name))
    return _emit(ctx, *events)


async def modify_hp(ctx: RunContext[ActorDeps], delta: int) -> str:
    """Damage (negative) or heal (positive) the character."""
    return _emit(ctx, HpChanged(delta=delta))


async def move_to(ctx: RunContext[ActorDeps], location: str) -> str:
    """Move the character to a new location."""
    return _emit(ctx, Moved(location=location))


async def discover_entity(ctx: RunContext[ActorDeps], name: str) -> str:
    """Reveal an existing person, place or item to the player by its exact name."""
    scenario = ctx.deps.draft.scenario
    entity = find_by_name(scenario, name) or find(scenario, name)
    if entity is None:
        raise ModelRetry(f"No scenario entity is named {name!r}. Do not invent one.")
    if entity.known:
        return f"{entity.name} was already known"
    return _emit(ctx, EntityDiscovered(entity_id=entity.id, name=entity.name))


@cache
def agent() -> Agent[ActorDeps, str]:
    return Agent(
        model(),
        name="actor",
        output_type=str,
        deps_type=ActorDeps,
        instructions=INSTRUCTIONS,
        # a refused tool call is normal here — the model must get several chances to correct itself
        retries=RETRIES,
        tools=[ability_check, modify_inventory, modify_hp, move_to, discover_entity],
    )


async def act(prompt: str, deps: ActorDeps) -> tuple[list[Event], str]:
    report = (await agent().run(prompt, deps=deps)).output
    return deps.events, report
