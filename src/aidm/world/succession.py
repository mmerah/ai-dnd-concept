from random import Random

from pydantic import Field

from aidm.state.entities import DEAD, CheckedEntityId, EntityId, Frozen
from aidm.state.facts import Fact, entity_fact
from aidm.state.model import Game, draft_refusal
from aidm.state.play import PendingDecision, PendingOption
from aidm.state.tools import DirectorTool, Validate, apply_to_draft, director_tool


def take_over(draft: Game, successor_id: EntityId) -> tuple[Fact, ...]:
    """Only the played id moves: sheets, items and history keep pointing where they point."""
    successor = draft.world.require_kind(successor_id, "actor")
    if successor_id not in draft.world.party:
        raise ValueError(f"{successor.name} does not travel with the player")
    if successor.trait(DEAD) is not None:
        raise ValueError(f"{successor.name} is dead and carries nothing on")
    draft.world.party.remove(successor_id)
    draft.player_id = successor_id
    return (
        entity_fact(
            successor,
            "player_succeeded",
            f"{draft.label(successor)} is the played character from here on",
            card=f"You play on as {successor.name}",
        ),
    )


class TakeOver(Frozen):
    successor_id: CheckedEntityId = Field(description="Exact id of the party member who plays on.")


TAKE_OVER: DirectorTool = director_tool(
    "take_over",
    "Hand the played character's story on to a companion who travels with them.",
    TakeOver,
    lambda draft, one, _rng: take_over(draft, one.successor_id),
)


def succession_decision(state: Game, validate: Validate) -> PendingDecision | None:
    """None where nobody can carry the story on: the game ends with the played character."""
    options: list[PendingOption] = []
    for member_id in state.world.party:
        # Eligible means the swap leaves a game this engine can play, so there is no second rule.
        refused = draft_refusal(
            state,
            lambda draft, one=member_id: apply_to_draft(
                validate, draft, lambda copy, _rng: take_over(copy, one), Random()
            ),
        )
        if refused is not None:
            continue
        member = state.world.require(member_id)
        options.append(
            PendingOption(
                id=member_id,
                label=f"Play on as {member.name}",
                detail=member.brief,
                name=TAKE_OVER.name,
                args={"successor_id": member_id},
            )
        )
    if not options:
        return None
    return PendingDecision(
        kind="succession",
        prompt=f"{state.player.name} is dead. Who carries the story on?",
        options=tuple(options),
        allows_text=False,
    )


def player_over(state: Game) -> str | None:
    """A death nobody was left to answer: the succession decision would still be open."""
    if state.pending is None and state.player.trait(DEAD) is not None:
        return "You died."
    return None
