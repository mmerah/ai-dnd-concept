from collections.abc import Mapping, Sequence
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm.state.base import Frozen, Slug

# An option id is named by the engine and may run hyphens together ('red---fire'), so it is
# laxer than `Slug`.
ContentSlug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=64)]

type Picks = Mapping[Slug, tuple[ContentSlug, ...]]


class CreationOption(Frozen):
    id: ContentSlug
    label: str
    detail: str = ""


class CreationStep(Frozen):
    id: Slug
    prompt: str
    options: tuple[CreationOption, ...] = Field(min_length=1)
    choose: int = 1

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        if not 1 <= self.choose <= len(self.options):
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


def picked(picks: Picks, step_id: Slug) -> tuple[ContentSlug, ...]:
    return picks.get(step_id, ())


def check_picks(steps: Sequence[CreationStep], picks: Picks) -> None:
    """One legality rule for the page and for `create`, so neither can drift."""
    known = {step.id for step in steps}
    if unknown := sorted(set(picks) - known):
        raise ValueError(f"no creation step is called {unknown}")
    for step in steps:
        _check_chosen(step, picked(picks, step.id))


def _check_chosen(step: CreationStep, chosen: tuple[ContentSlug, ...]) -> None:
    if len(set(chosen)) != len(chosen):
        raise ValueError(f"{step.id!r} repeats a pick")
    if len(chosen) != step.choose:
        raise ValueError(f"{step.id!r} takes exactly {step.choose} picks, not {len(chosen)}")
    legal = {option.id for option in step.options}
    if outside := sorted(set(chosen) - legal):
        raise ValueError(f"{step.id!r} offers no {outside}")
