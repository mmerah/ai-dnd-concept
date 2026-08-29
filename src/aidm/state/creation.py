from collections.abc import Mapping, Sequence

from aidm.state.entities import Frozen, Slug
from aidm.state.play import DecisionOption

type Picks = Mapping[Slug, str]
ANSWER_MAX = 100


class CreationStep(Frozen):
    """No options means the player writes the answer."""

    id: Slug
    prompt: str
    options: tuple[DecisionOption, ...] = ()
    hint: str = ""


def picked(picks: Picks, step_id: Slug) -> str:
    return picks.get(step_id, "")


def numbered_steps(
    base: Slug,
    prompt: str,
    count: int,
    options: Sequence[DecisionOption] = (),
    hint: str = "",
    distinct_from: Picks | None = None,
) -> tuple[CreationStep, ...]:
    steps: list[CreationStep] = []
    used: set[str] = set()
    for index in range(1, count + 1):
        step_id = f"{base}-{index}"
        left = tuple(option for option in options if option.id not in used)
        steps.append(CreationStep(id=step_id, prompt=f"{prompt} {index}", options=left, hint=hint))
        if distinct_from is not None:
            used.add(picked(distinct_from, step_id))
    return tuple(steps)


def check_picks(steps: Sequence[CreationStep], picks: Picks) -> None:
    """One legality rule for the page and for `create`, so neither can drift."""
    known = {step.id for step in steps}
    if unknown := sorted(set(picks) - known):
        raise ValueError(f"no creation step is called {unknown}")
    for step in steps:
        answer = picked(picks, step.id)
        if not answer.strip():
            raise ValueError(f"{step.id!r} is unanswered")
        if len(answer) > ANSWER_MAX:
            raise ValueError(f"{step.id!r} takes at most {ANSWER_MAX} characters")
        if step.options and answer not in {option.id for option in step.options}:
            raise ValueError(f"{step.id!r} offers no {answer!r}")
