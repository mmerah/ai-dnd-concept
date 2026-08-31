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
