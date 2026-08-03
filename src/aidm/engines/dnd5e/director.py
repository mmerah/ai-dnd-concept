from collections.abc import Sequence
from random import Random

from pydantic import ValidationError
from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.directing import check_refs, check_speaker
from aidm.world import GameState

from .direction import CONSEQUENCE_TYPES, Consequence, Dnd5eDirection, flatten
from .rules import Dnd5eRules


def consequence_menu(types: Sequence[type[Consequence]]) -> str:
    """Each consequence's docstring, GUIDANCE and field descriptions are prompt text."""
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        if not isinstance(action, str):
            raise TypeError(f"{consequence.__name__} has no literal action default")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {consequence.__doc__}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


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

    @property
    def output(self) -> OutputSpec[Dnd5eDirection]:
        return NativeOutput(Dnd5eDirection)

    def instructions(self) -> str:
        return MECHANICS

    def validate(
        self,
        ctx: RunContext[GameState],
        direction: Dnd5eDirection,
    ) -> Dnd5eDirection:
        state = ctx.deps
        faults = [consequence.check() for consequence in flatten(direction.mechanics)]
        faults.append(check_speaker(state, direction.speaker_id))
        faults.append(check_refs(state, direction.canon_refs()))
        if fault := next((item for item in faults if item is not None), None):
            raise ModelRetry(fault)
        self._dry_run(direction, state)
        return direction

    def _dry_run(self, direction: Dnd5eDirection, state: GameState) -> None:
        for seed in _DRY_RUN_SEEDS:
            try:
                _ = self._rules.resolve(direction, state, Random(seed))
            except ValidationError:
                raise
            except ValueError as error:
                raise ModelRetry(f"{error}. Propose mechanics this state allows.") from error
