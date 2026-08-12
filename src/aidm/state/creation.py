from collections.abc import Mapping, Sequence
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm.state.base import Frozen, Slug

# An option id is named by the engine and may run hyphens together ('red---fire'), so it is
# laxer than `Slug`.
ContentSlug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=64)]

type Amounts = Mapping[Slug, int]
type Picks = Mapping[Slug, tuple[ContentSlug, ...] | Amounts]


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


class AllocationStep(Frozen):
    """Numbers, not picks: the player puts a value on each entry, within bounds the step names.
    What the values must add up to is the engine's own rule — a 27-point budget, the standard
    array, one seed's roll — and `create` refuses a set that breaks it with the reason."""

    id: Slug
    prompt: str
    entries: tuple[CreationOption, ...] = Field(min_length=1)
    minimum: int
    maximum: int

    @model_validator(mode="after")
    def _bounds_hold(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError(f"no value lies between {self.minimum} and {self.maximum}")
        return self


type Step = CreationStep | AllocationStep


def picked(picks: Picks, step_id: Slug) -> tuple[ContentSlug, ...]:
    held = picks.get(step_id, ())
    return held if isinstance(held, tuple) else ()


def allocated(picks: Picks, step_id: Slug) -> Amounts:
    held = picks.get(step_id, {})
    return {} if isinstance(held, tuple) else held


def check_picks(steps: Sequence[Step], picks: Picks) -> None:
    """One legality rule for the page and for `create`, so neither can drift."""
    known = {step.id for step in steps}
    if unknown := sorted(set(picks) - known):
        raise ValueError(f"no creation step is called {unknown}")
    for step in steps:
        # An answer of the wrong shape reads as no answer, and meets the step's own refusal.
        if isinstance(step, CreationStep):
            _check_chosen(step, picked(picks, step.id))
        else:
            _check_allocated(step, allocated(picks, step.id))


def _check_chosen(step: CreationStep, chosen: tuple[ContentSlug, ...]) -> None:
    if len(set(chosen)) != len(chosen):
        raise ValueError(f"{step.id!r} repeats a pick")
    if len(chosen) != step.choose:
        raise ValueError(f"{step.id!r} takes exactly {step.choose} picks, not {len(chosen)}")
    legal = {option.id for option in step.options}
    if outside := sorted(set(chosen) - legal):
        raise ValueError(f"{step.id!r} offers no {outside}")


def _check_allocated(step: AllocationStep, amounts: Amounts) -> None:
    wanted = {entry.id for entry in step.entries}
    # The page writes what a browser number input gives it, and `Amounts` is a bare alias no
    # validator stands behind: a float or a string would reach the engine as a crash, not a refusal.
    if wrong := sorted(key for key, value in amounts.items() if type(value) is not int):
        raise ValueError(f"{step.id!r} takes whole numbers, and {wrong} holds something else")
    if missing := sorted(wanted - set(amounts)):
        raise ValueError(f"{step.id!r} has no value for {missing}")
    if unknown := sorted(set(amounts) - wanted):
        raise ValueError(f"{step.id!r} has no entry called {unknown}")
    outside = sorted(
        key for key, value in amounts.items() if not step.minimum <= value <= step.maximum
    )
    if outside:
        raise ValueError(
            f"{step.id!r} takes {step.minimum} to {step.maximum} for each entry: {outside} "
            "lies outside"
        )
