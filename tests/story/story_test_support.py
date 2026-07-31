from core_test_support import initialized as initial_story_game

from aidm.engines.story.direction import Risk, StoryConsequence, StoryDirection, TakeStress

__all__ = ["initial_story_game", "setback_direction"]


def setback_direction(*, take_stress: bool = False) -> StoryDirection:
    branch: list[StoryConsequence] = [TakeStress(amount=1)] if take_stress else []
    risk = Risk(
        approach="empathetic",
        difficulty=2,
        on_setback=branch,
    )
    mechanics: list[StoryConsequence] = [risk]
    return StoryDirection(
        intent="Kael attempts something dangerous.",
        tone="tense",
        mechanics=mechanics,
    )
