from random import Random

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.directing import check_proposal, consequence_menu
from aidm.transition import Direction
from aidm.world import GameState

from .direction import CONSEQUENCE_TYPES, Dnd5eDirection, branches, dump_direction
from .rules import Dnd5eProposalRejected, Dnd5eRules

_MECHANICS_TEMPLATE = """`mechanics` — a list of 5e consequences resolved in order, \
deterministically. All ids MUST be exact ids from the lists above. Most consequences apply \
unconditionally; `roll_check` and `roll_save` nest `on_success` / `on_failure` branches for an \
action that can fail, and you fill both because you do not know which way it will fall. Where an \
amount is uncertain, give the dice and let them fall rather than choosing the number \
yourself. The deterministic 5e engine rolls every die, spends every resource, and decides all \
outcomes. Leave the list empty if nothing mechanical is at stake.

The consequences you can place in the list:

{consequences}"""

MECHANICS = _MECHANICS_TEMPLATE.replace("{consequences}", consequence_menu(CONSEQUENCE_TYPES))

_DRY_RUN_SEEDS = (2, 5)


class Dnd5eDirector:
    def __init__(self, rules: Dnd5eRules) -> None:
        self._rules = rules

    def output(self) -> OutputSpec[Direction]:
        def direct(ctx: RunContext[GameState], proposal: Dnd5eDirection) -> Direction:
            return self.check(ctx.deps, proposal)

        return NativeOutput(direct, name="Dnd5eDirection")

    def instructions(self) -> str:
        return MECHANICS

    def check(self, state: GameState, proposal: Dnd5eDirection) -> Direction:
        flat = dump_direction(proposal)
        if fault := check_proposal(
            state,
            proposal.mechanics,
            proposal.speaker_id,
            lambda consequence: branches(consequence).values(),
        ):
            raise ModelRetry(fault)
        self._dry_run(flat, state)
        return flat

    def _dry_run(self, direction: Direction, state: GameState) -> None:
        for seed in _DRY_RUN_SEEDS:
            try:
                _ = self._rules.resolve(direction, state, Random(seed))
            except Dnd5eProposalRejected as error:
                raise ModelRetry(f"{error}. Propose mechanics this state allows.") from error
