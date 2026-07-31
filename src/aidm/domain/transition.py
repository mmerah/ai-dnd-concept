from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from aidm_5e.domain.models.direction import Dnd5eDirection
from aidm_5e.domain.models.facts import Dnd5eFact
from aidm_story.direction import StoryDirection
from aidm_story.facts import StoryFact

from .facts import CoreFact
from .state import GameState

type Fact = Annotated[CoreFact | StoryFact | Dnd5eFact, Field(discriminator="source")]
type Direction = Annotated[StoryDirection | Dnd5eDirection, Field(discriminator="engine")]


@dataclass(frozen=True, slots=True)
class Transition:
    """One engine transaction: a revalidated state and the facts that produced it."""

    state: GameState
    facts: tuple[Fact, ...]
