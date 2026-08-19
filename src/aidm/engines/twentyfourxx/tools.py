import dataclasses

from pydantic_ai import RunContext
from pydantic_ai.tools import ObjectJsonSchema, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset

from aidm.engines.engine import PlanContext
from aidm.engines.sheets import require_sheet
from aidm.engines.transact import act, sequential_toolset
from aidm.state.base import EntityId
from aidm.state.resolution import Resolution
from aidm.state.world import GameState

from .actions import (
    Attempt,
    LuckTest,
    apply_change_credits,
    apply_complete_job,
    resolve_attempt,
    resolve_luck_test,
)
from .mechanics import Mechanics


def director_toolset() -> AbstractToolset[PlanContext]:
    def roll_attempt(ctx: RunContext[PlanContext], attempt: Attempt) -> str:
        """Put one risky attempt to the highest die of a pool.

        Args:
            attempt: The attempt to put to the dice.
        """
        return act(ctx, lambda draft, rng: resolve_attempt(draft, attempt, rng))

    def roll_luck_test(ctx: RunContext[PlanContext], test: LuckTest) -> str:
        """Put the SRD's standalone bad-luck test to the dice.

        Args:
            test: The luck test to put to the dice.
        """
        return act(ctx, lambda draft, rng: resolve_luck_test(draft, test, rng))

    def change_credits(ctx: RunContext[PlanContext], actor_id: EntityId, amount: int) -> str:
        """Move an actor's credits.

        Args:
            actor_id: Exact id of the actor: the player, or an actor here.
            amount: Positive to pay them, negative to charge them.
        """
        return act(
            ctx,
            lambda draft, _rng: Resolution(
                facts=tuple(apply_change_credits(draft, actor_id, amount))
            ),
        )

    def complete_job(ctx: RunContext[PlanContext]) -> str:
        """Record that the job is done."""
        return act(ctx, lambda draft, _rng: Resolution(facts=tuple(apply_complete_job(draft))))

    toolset = sequential_toolset([roll_attempt, roll_luck_test, change_credits, complete_job])
    return toolset.prepared(_narrow_to_skills_in_play)


def _skills_in_play(state: GameState) -> set[str]:
    """The skills a `roll_attempt` may name; `is_here` already covers the player, who stands at
    their own location."""
    sheets = state.mechanics_as(Mechanics).sheets
    return {
        skill
        for actor in state.world.of_kind("actor")
        if state.is_here(actor)
        for skill in require_sheet(sheets, actor).skills
    }


def _narrow_to_skills_in_play(
    ctx: RunContext[PlanContext], tools: list[ToolDefinition]
) -> list[ToolDefinition]:
    skills = _skills_in_play(ctx.deps.state)
    return [
        _with_skill_enum(tool, skills) if tool.name == "roll_attempt" else tool for tool in tools
    ]


def _with_skill_enum(tool: ToolDefinition, skills: set[str]) -> ToolDefinition:
    # Copied, never mutated: a prepare function is handed the same definition on every step.
    properties: dict[str, ObjectJsonSchema] = dict(tool.parameters_json_schema["properties"])
    for name in ("skill", "helper_skill"):
        properties[name] = {**properties[name], "enum": ["", *sorted(skills)]}
    schema = {**tool.parameters_json_schema, "properties": properties}
    return dataclasses.replace(tool, parameters_json_schema=schema)
