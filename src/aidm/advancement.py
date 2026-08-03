from typing import Annotated, Literal

from pydantic import Field

from .base import AdvancementDecision, Frozen


class AdvancementStatus(Frozen):
    headline: str
    detail: tuple[str, ...] = ()
    progress: float = Field(default=0.0, ge=0.0, le=1.0)


class Block(Frozen):
    """Engine-authored prose for the renderer: a heading and the lines under it."""

    heading: str
    lines: tuple[str, ...] = ()


class SelectOption(Frozen):
    key: str
    label: str


class SelectField(Frozen):
    type: Literal["select"] = "select"
    id: str
    label: str
    note: str = ""
    options: tuple[SelectOption, ...] = Field(min_length=1)
    # More than one pick spends several allowances on one field, as a 5e ability increase does.
    choose: int = Field(default=1, ge=1)


class TextField(Frozen):
    type: Literal["text"] = "text"
    id: str
    label: str


type FormField = Annotated[SelectField | TextField, Field(discriminator="type")]


class AdvancementOption(Frozen):
    """One offered advancement: what to call it, what to fill in, and the button that reviews it."""

    id: str
    heading: str
    note: str = ""
    action: str = "Review"
    fields: tuple[FormField, ...] = ()


class AdvancementForm(Frozen):
    """Everything the renderer needs: a title, preview blocks, and exclusive options."""

    title: str
    blocks: tuple[Block, ...] = ()
    options: tuple[AdvancementOption, ...] = Field(min_length=1)


class AdvancementChoice(Frozen):
    """What the player filled in: one option, and the values that option's fields collected."""

    option_id: str
    values: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    def one(self, field_id: str) -> str:
        values = self.values.get(field_id, ())
        if len(values) != 1:
            raise ValueError(f"{field_id!r} needs exactly one value, got {len(values)}")
        return values[0]


class AdvancementReview(Frozen):
    """The confirm dialog's content beside the decision that commits it."""

    title: str
    confirm_label: str
    blocks: tuple[Block, ...] = ()
    decision: AdvancementDecision
