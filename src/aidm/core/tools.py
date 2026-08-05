from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import Annotated

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from .base import PLAYER_ID, Entity, EntityId, Frozen, Kind, slug
from .facts import CORE, Fact
from .world import EngineRules, GameState


class DirectorNotes(Frozen):
    """What the Director hands the Narrator once its tool calls have settled the turn."""

    intent: str
    tone: str
    speaker_id: EntityId | None = None


class RefereeVerdict(Frozen):
    """The Referee's ruling on the Director's settled turn."""

    objection: Annotated[str, Field(min_length=1)] | None = Field(
        default=None,
        description="Null when the turn stands; otherwise what the Director must correct now, "
        "in one or two sentences.",
    )


def objection_fact(objection: str) -> Fact:
    return Fact(source=CORE, kind="referee_objection", trace=objection)


@dataclass
class TurnContext[R: EngineRules]:
    """The deps every director tool receives; owns this turn's draft transaction."""

    draft: GameState[R]
    rng: Random
    facts: list[Fact]
    default_rules: Callable[[Entity], R]

    def record(self, facts: Sequence[Fact]) -> str:
        """A tool ends here: the facts it appended are also what the model reads back."""
        self.facts.extend(facts)
        return "; ".join(fact.trace for fact in facts) or "nothing changed"


def require[R: EngineRules](state: GameState[R], entity_id: EntityId) -> Entity:
    entity = state.world.find(entity_id)
    if entity is None:
        raise ModelRetry(f"unknown entity id {entity_id!r}. Use only ids you were shown.")
    return entity


def require_kind[R: EngineRules](state: GameState[R], entity_id: EntityId, kind: Kind) -> Entity:
    entity = require(state, entity_id)
    if entity.kind != kind:
        raise ModelRetry(
            f"{entity_id!r} is a {entity.kind}, not a {kind}. "
            "Use an id of the kind this argument asks for."
        )
    return entity


def require_actor_here[R: EngineRules](state: GameState[R], actor_id: EntityId | None) -> Entity:
    if actor_id is None or actor_id == PLAYER_ID:
        return state.player
    actor = require_kind(state, actor_id, "actor")
    if not state.is_here(actor):
        raise ModelRetry(
            f"{actor_id!r} is not here with the player. "
            "Move them here first, or act on who is here."
        )
    return actor


def require_carried[R: EngineRules](state: GameState[R], item_id: EntityId) -> Entity:
    item = require_kind(state, item_id, "item")
    if item.parent_id != PLAYER_ID:
        raise ModelRetry(f"the player does not carry item {item_id!r}")
    return item


def check_speaker[R: EngineRules](state: GameState[R], speaker_id: EntityId | None) -> str | None:
    """The player is addressed, never the speaker: losing this lets the Director voice them."""
    if speaker_id is None:
        return None
    if speaker_id == PLAYER_ID:
        return "speaker_id names another actor the player addresses, never the player."
    speaker = state.world.find(speaker_id)
    if speaker is None:
        return f"unknown speaker id {speaker_id!r}. Use only ids you were shown, or null."
    if speaker.kind != "actor" or not speaker.known or not state.is_here(speaker):
        return (
            f"speaker {speaker_id!r} must be an NPC the player has met and who is here with them. "
            "Use null if nobody is being addressed."
        )
    return None


def director_notes[R: EngineRules](
    ctx: RunContext[TurnContext[R]], notes: DirectorNotes
) -> DirectorNotes:
    if fault := check_speaker(ctx.deps.draft, notes.speaker_id):
        raise ModelRetry(fault)
    return notes


def discover[R: EngineRules](
    ctx: RunContext[TurnContext[R]],
    entity_id: Annotated[
        EntityId, Field(description="Exact id of the existing canon entity to reveal.")
    ],
) -> str:
    """Reveal an existing canon entity to the player.

    Use when the player's action reveals something from the unrevealed list: they notice it, are
    told of it, or reach it. Prefer this over inventing a replacement.
    """
    deps = ctx.deps
    return deps.record(deps.draft.reveal(require(deps.draft, entity_id)))


def move[R: EngineRules](
    ctx: RunContext[TurnContext[R]],
    location_id: Annotated[
        EntityId, Field(description="Exact id of the canon location the actor enters.")
    ],
    actor_id: Annotated[
        EntityId | None,
        Field(description="Exact id of the actor to move; omit to move the player."),
    ] = None,
) -> str:
    """Move the player or another actor to an existing location.

    Use when an actor actually changes location. Omit `actor_id` to move the player. Moving the
    player to an unrevealed location discovers it.
    """
    deps = ctx.deps
    draft = deps.draft
    destination = require_kind(deps.draft, location_id, "location")
    here = draft.player_location
    if actor_id is None or actor_id == PLAYER_ID:
        return deps.record([*draft.reveal(destination), draft.move(draft.player, destination)])
    actor = require_kind(deps.draft, actor_id, "actor")
    if actor.parent_id != here and destination.id != here:
        raise ModelRetry(f"movement of actor {actor_id!r} would not be witnessed")
    revealed = draft.reveal(actor) if destination.id == here else []
    return deps.record([*revealed, draft.move(actor, destination)])


def take_item[R: EngineRules](
    ctx: RunContext[TurnContext[R]],
    item_id: Annotated[
        EntityId, Field(description="Exact id of a loose canon item at the player's location.")
    ],
) -> str:
    """Move a loose canon item at the current location into the player's inventory.

    Use when the player takes an existing item shown at their current location. The item is
    discovered automatically if it was unrevealed.
    """
    deps = ctx.deps
    item = require_kind(deps.draft, item_id, "item")
    if item.parent_id != deps.draft.player_location:
        raise ModelRetry(f"item {item_id!r} is not loose at the player's location")
    return deps.record([*deps.draft.reveal(item), deps.draft.move(item, deps.draft.player)])


def drop_item[R: EngineRules](
    ctx: RunContext[TurnContext[R]],
    item_id: Annotated[
        EntityId, Field(description="Exact id of an item the player currently carries.")
    ],
) -> str:
    """Leave a carried item at the player's current location.

    Use when the player puts down, abandons, or otherwise stops carrying an item in their
    inventory.
    """
    deps = ctx.deps
    item = require_carried(deps.draft, item_id)
    here = deps.draft.world.require(deps.draft.player_location)
    return deps.record([*deps.draft.reveal(item), deps.draft.move(item, here)])


def give_item[R: EngineRules](
    ctx: RunContext[TurnContext[R]],
    item_id: Annotated[
        EntityId, Field(description="Exact id of an item the player currently carries.")
    ],
    actor_id: Annotated[
        EntityId, Field(description="Exact id of the receiving actor here with the player.")
    ],
) -> str:
    """Transfer a carried item to another actor who is here.

    Use when the player hands an inventory item to another actor at their location. The receiving
    actor then carries it.
    """
    deps = ctx.deps
    if actor_id == PLAYER_ID:
        raise ModelRetry("give_item must name another actor: the player already holds the item")
    actor = require_actor_here(deps.draft, actor_id)
    item = require_carried(deps.draft, item_id)
    return deps.record([*deps.draft.reveal(item), deps.draft.move(item, actor)])


def gain_improvised_item[R: EngineRules](
    ctx: RunContext[TurnContext[R]],
    item_name: Annotated[
        str,
        Field(
            min_length=1,
            description="The incidental item written out, such as 'a handful of gravel'.",
        ),
    ],
) -> str:
    """Give the player a minor incidental item that has no canon entry.

    Use only for an ordinary incidental object that is not already in canon and is not important
    enough for the Maintainer and Creator to develop. Never use it as a substitute for an existing
    item.
    """
    deps = ctx.deps
    item = Entity(
        id=slug(item_name, deps.draft.world.all_ids()),
        kind="item",
        name=item_name,
        brief=item_name,
        known=True,
        parent_id=deps.draft.player_location,
    )
    created = deps.draft.add(item, deps.default_rules(item))
    return deps.record([created, deps.draft.move(item, deps.draft.player)])


def world_toolset() -> FunctionToolset[TurnContext[EngineRules]]:
    return FunctionToolset[TurnContext[EngineRules]](
        [discover, move, take_item, drop_item, give_item, gain_improvised_item]
    )
