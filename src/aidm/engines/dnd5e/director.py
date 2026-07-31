from collections.abc import Sequence
from random import Random

from pydantic import ValidationError
from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.base import ActorEntity, EntityId
from aidm.world import GameState

from .direction import CONSEQUENCE_TYPES, Consequence, Dnd5eDirection, References, flatten
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
        refs = [
            (EntityId(str(entity_id)), reference) for entity_id, reference in direction.canon_refs()
        ]
        if direction.speaker_id is not None:
            refs.append(
                (
                    EntityId(str(direction.speaker_id)),
                    References("actor", present=True),
                )
            )
        faults = [direction.check()]
        faults.extend(consequence.check() for consequence in flatten(direction.mechanics))
        if fault := next((item for item in faults if item is not None), None):
            raise ModelRetry(fault)
        canon = state.world.entities
        missing = sorted({entity_id for entity_id, _ in refs if entity_id not in canon})
        if missing:
            raise ModelRetry(f"unknown entity id(s): {missing}. Use only ids you were shown.")
        mismatched = sorted(
            f"{entity_id} is a {canon[entity_id].kind}, not a {reference.kind}"
            for entity_id, reference in refs
            if reference.kind is not None and canon[entity_id].kind != reference.kind
        )
        if mismatched:
            raise ModelRetry(
                f"wrong kind of entity: {'; '.join(mismatched)}. "
                "Use an id of the kind each field asks for."
            )
        absent = sorted(
            {
                entity_id
                for entity_id, reference in refs
                if reference.present and not state.is_here(canon[entity_id])
            }
        )
        if absent:
            raise ModelRetry(
                f"not here with the player: {absent}. Move them here first, or act on who is here."
            )
        if direction.speaker_id is not None:
            speaker = canon[EntityId(str(direction.speaker_id))]
            if (
                not isinstance(speaker, ActorEntity)
                or not speaker.known
                or not state.is_here(speaker)
            ):
                raise ModelRetry(
                    f"speaker {str(direction.speaker_id)!r} must be an NPC the player has met "
                    "and who is here with them. Use null if nobody is being addressed."
                )
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
