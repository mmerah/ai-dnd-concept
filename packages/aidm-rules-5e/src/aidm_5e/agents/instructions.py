from collections.abc import Sequence

from ..domain.models.consequences import CONSEQUENCE_TYPES, Consequence


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
