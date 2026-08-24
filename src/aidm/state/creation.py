from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.state.entities import ContentSlug, Frozen, Slug

type Picks = Mapping[Slug, tuple[str, ...]]


class CreationOption(Frozen):
    id: ContentSlug
    label: str
    detail: str = ""


class CreationStep(Frozen):
    id: Slug
    prompt: str
    options: tuple[CreationOption, ...] = Field(min_length=1)
    choose: int = 1
    repeats: bool = False

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        # A repeatable step may ask for more picks than it offers options: they stack.
        distinct = self.choose <= len(self.options) or self.repeats
        if self.choose < 1 or not distinct:
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


class TextStep(Frozen):
    """A creation question the player answers in their own words."""

    id: Slug
    prompt: str
    hint: str = ""
    count: int = 1
    max_length: int = 100


type AnyStep = CreationStep | TextStep


def picked(picks: Picks, step_id: Slug) -> tuple[str, ...]:
    return picks.get(step_id, ())


def check_picks(steps: Sequence[AnyStep], picks: Picks) -> None:
    """One legality rule for the page and for `create`, so neither can drift."""
    known = {step.id for step in steps}
    if unknown := sorted(set(picks) - known):
        raise ValueError(f"no creation step is called {unknown}")
    for step in steps:
        answers = picked(picks, step.id)
        if isinstance(step, TextStep):
            _check_written(step, answers)
        else:
            _check_chosen(step, answers)


def _check_chosen(step: CreationStep, chosen: tuple[str, ...]) -> None:
    # Blank repeat slots are missing picks, not invalid offered options.
    named = tuple(pick for pick in chosen if pick)
    if not step.repeats and len(set(named)) != len(named):
        raise ValueError(f"{step.id!r} repeats a pick")
    if len(named) != step.choose:
        raise ValueError(f"{step.id!r} takes exactly {step.choose} picks, not {len(named)}")
    legal = {option.id for option in step.options}
    if outside := sorted(set(named) - legal):
        raise ValueError(f"{step.id!r} offers no {outside}")


def _check_written(step: TextStep, answers: tuple[str, ...]) -> None:
    if len(answers) != step.count:
        raise ValueError(f"{step.id!r} takes exactly {step.count} answers, not {len(answers)}")
    for answer in answers:
        if not answer.strip():
            raise ValueError(f"{step.id!r} takes an answer in words")
        if len(answer) > step.max_length:
            raise ValueError(f"{step.id!r} takes at most {step.max_length} characters")
