from random import Random

from aidm.advancement import AdvancementStatus
from aidm.base import AdvancementDecision, Frozen
from aidm.transition import Transition
from aidm.world import GameState

from . import features, progression
from .access import Dnd5eWorld
from .identity import ENGINE_ID
from .progression import AdvancementPlan, LevelUpPreview
from .ruleset import Ruleset
from .state import MAX_LEVEL, Decisions, Dnd5eActor


class Dnd5eAdvancementDecisions(Frozen):
    decisions: Decisions


def dump_decision(decisions: Dnd5eAdvancementDecisions) -> AdvancementDecision:
    """The UI mints the typed choice; core carries only the blob."""
    return AdvancementDecision(engine=ENGINE_ID, choice=decisions.model_dump(mode="json"))


def load_decision(decision: AdvancementDecision) -> Dnd5eAdvancementDecisions:
    """Validate the blob back; a decision from another engine cannot survive this."""
    if decision.engine != ENGINE_ID:
        raise ValueError(f"5e received a {decision.engine!r} decision")
    return Dnd5eAdvancementDecisions.model_validate(decision.choice)


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
        return progression.preview(self._checked(self._player(state)), self._ruleset)

    def plan(
        self,
        state: GameState,
        decisions: Dnd5eAdvancementDecisions,
    ) -> AdvancementPlan:
        player = self._checked(self._player(state))
        return progression.plan(player, decisions.decisions, self._ruleset)

    def advance(self, decision: AdvancementDecision, state: GameState, rng: Random) -> Transition:
        decisions = load_decision(decision)
        world = Dnd5eWorld(state=state.draft())
        player = self._checked(world.player())
        facts = progression.advance(player, decisions.decisions, self._ruleset, rng)
        return Transition(state=world.commit(), facts=tuple(facts))

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
        return Dnd5eWorld(state=state).player()

    @staticmethod
    def _checked(player: Dnd5eActor) -> Dnd5eActor:
        if player.progression is None or not player.progression.level_up_available:
            raise ValueError("no 5e level-up has been awarded")
        return player
