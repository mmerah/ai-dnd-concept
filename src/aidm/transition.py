from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from aidm.engines.dnd5e.direction import Dnd5eDirection
from aidm.engines.dnd5e.facts import Dnd5eFact
from aidm.engines.story.direction import StoryDirection
from aidm.engines.story.facts import StoryFact

from .facts import CoreFact
from .world import GameState

type Fact = Annotated[CoreFact | StoryFact | Dnd5eFact, Field(discriminator="source")]
type Direction = Annotated[StoryDirection | Dnd5eDirection, Field(discriminator="engine")]


@dataclass(frozen=True, slots=True)
class Transition:
    """One engine transaction: a revalidated state and the facts that produced it."""

    state: GameState
    facts: tuple[Fact, ...]
