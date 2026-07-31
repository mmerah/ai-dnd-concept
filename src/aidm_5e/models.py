from aidm.utils.models import EMPTY_FROZEN_MAP

from .content.records.base import ContentRef
from .domain.models.progression import Decisions, Origin, Progression
from .domain.models.stats import StatBlock
from .utils.models import Attributes, Frozen

type Dnd5eContentRef = ContentRef


class Dnd5eActorState(Frozen):
    stats: StatBlock
    progression: Progression | None = None
    ref: Dnd5eContentRef | None = None


class Dnd5eItemState(Frozen):
    ref: Dnd5eContentRef | None = None


class Dnd5eGameState(Frozen):
    pass


class Dnd5eCharacterData(Frozen):
    origin: Origin
    starting_attributes: Attributes = Attributes()
    decisions: Decisions = EMPTY_FROZEN_MAP


class Dnd5eActorDefinition(Frozen):
    ref: Dnd5eContentRef | None = None
    stats: StatBlock | None = None


class Dnd5eItemDefinition(Frozen):
    ref: Dnd5eContentRef | None = None
