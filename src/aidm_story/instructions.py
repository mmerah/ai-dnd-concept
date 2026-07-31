from collections.abc import Sequence

from .actions import CoreAction
from .direction import STORY_CONSEQUENCE_TYPES, StoryAction


def consequence_menu(
    types: Sequence[type[CoreAction] | type[StoryAction]],
) -> str:
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        summary = consequence.__doc__
        if not isinstance(action, str) or summary is None:
            raise TypeError(f"{consequence.__name__} has incomplete prompt documentation")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {summary}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


_MECHANICS_TEMPLATE = """`mechanics` — an ordered list of Story consequences. The deterministic \
engine applies them in order and decides every `risk` outcome. Use exact ids from the consolidated \
scene above. Leave the list empty only when the turn changes no location, ownership, discovery, \
injury, condition, pressure, or other Story state.

Story uses stress and conditions instead of hit points. Stress tracks mounting harm and pressure; \
maximum stress means taken out. Conditions hold persistent injuries and statuses with concrete \
fictional effects. Core consequences handle discovery, movement, and inventory.

The consequences you can place in the list:

{consequences}"""

MECHANICS = _MECHANICS_TEMPLATE.replace(
    "{consequences}",
    consequence_menu(STORY_CONSEQUENCE_TYPES),
)
