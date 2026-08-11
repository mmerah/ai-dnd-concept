from typing import Self

from pydantic import Field, model_validator

from .base import Frozen
from .packs import ContentRef


class AdvancementOffer(Frozen):
    """One pending advancement, already resolved out of content."""

    prompt: str
    text: str = ""
    options: tuple[ContentRef, ...] = ()
    choose: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        if self.choose > len(self.options):
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


class ProposalBase(Frozen):
    """What an advancement writes, in the engine's own vocabulary."""
