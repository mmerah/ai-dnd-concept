from random import Random

from aidm.advancement import AdvancementStatus
from aidm.base import PLAYER_ID, Frozen
from aidm.transition import Transition
from aidm.world import GameState

from . import features, progression
from .access import actor_of
from .progression import AdvancementPlan, LevelUpPreview
from .ruleset import Ruleset
from .state import MAX_LEVEL, Decisions, Dnd5eActor


class Dnd5eAdvancementDecisions(Frozen):
    decisions: Decisions


class Dnd5eAdvancement:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def available(self, state: GameState) -> bool:
        current = self._player(state).progression
        return current is not None and current.level_up_available

    def status(self, state: GameState) -> AdvancementStatus:
        actor = self._player(state)
        if actor.progression is None:
            return AdvancementStatus(
                headline="5e advancement unavailable",
                detail=("This character has no class, so there is nothing to advance.",),
            )
        current = actor.progression
        features_detail = self._features(actor)
        if current.level >= MAX_LEVEL:
            detail = (f"Level {MAX_LEVEL} is the last.", *features_detail)
        elif current.level_up_available:
            detail = (f"Level {current.level + 1} is ready.", *features_detail)
        else:
            detail = ("No level-up has been awarded yet. Keep playing.", *features_detail)
        return AdvancementStatus(
            headline=f"level {current.level}",
            detail=detail,
            progress=current.level / MAX_LEVEL,
        )

    def preview(self, state: GameState) -> LevelUpPreview:
        return progression.preview(self._ready(state), self._ruleset)

    def plan(
        self,
        state: GameState,
        decisions: Dnd5eAdvancementDecisions,
    ) -> AdvancementPlan:
        return progression.plan(self._ready(state), decisions.decisions, self._ruleset)

    def advance(
        self,
        state: GameState,
        decisions: Dnd5eAdvancementDecisions,
        rng: Random,
    ) -> Transition:
        draft = state.draft()
        facts = progression.advance(
            self._ready(draft),
            decisions.decisions,
            self._ruleset,
            rng,
        )
        return Transition(state=draft.committed(), facts=tuple(facts))

    def _features(self, actor: Dnd5eActor) -> tuple[str, ...]:
        current = actor.progression
        if current is None:
            return ()
        owned = features.owned(current, actor.stats.attributes, self._ruleset)
        if not owned:
            return ("Current class features: none.",)
        return (
            "Current class features:",
            *(self._feature_line(feature) for feature in owned),
        )

    @staticmethod
    def _feature_line(feature: features.OwnedFeature) -> str:
        use_status = ""
        if feature.pool is not None:
            state = feature.pool.state
            use_status = (
                f" — {state.remaining}/{state.maximum} uses — recharges on a {state.recharge} rest"
            )
        return (
            f"{feature.profile.name} — {features.actionability(feature.profile)}"
            f"{use_status} — {feature.profile.desc}"
        )

    @staticmethod
    def _player(state: GameState) -> Dnd5eActor:
        return actor_of(state, PLAYER_ID)

    def _ready(self, state: GameState) -> Dnd5eActor:
        player = self._player(state)
        if player.progression is None or not player.progression.level_up_available:
            raise ValueError("no 5e level-up has been awarded")
        return player
