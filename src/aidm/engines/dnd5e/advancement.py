from dataclasses import dataclass
from random import Random

from aidm.base import AdvancementDecision, Frozen
from aidm.transition import Transition
from aidm.world import GameState

from . import features, progression
from .access import Dnd5eWorld, read_player
from .identity import ENGINE_ID
from .progression import AdvancementPlan, LevelBenefits, LevelUpPreview
from .ruleset import Ruleset
from .state import MAX_LEVEL, Decisions, Dnd5eActor


class Dnd5eAdvancementDecisions(Frozen):
    decisions: Decisions


def dump_decision(decisions: Dnd5eAdvancementDecisions) -> AdvancementDecision:
    return AdvancementDecision(engine=ENGINE_ID, choice=decisions.model_dump(mode="json"))


def load_decision(decision: AdvancementDecision) -> Dnd5eAdvancementDecisions:
    if decision.engine != ENGINE_ID:
        raise ValueError(f"5e received a {decision.engine!r} decision")
    return Dnd5eAdvancementDecisions.model_validate(decision.choice)


@dataclass(frozen=True, slots=True)
class Section:
    """A heading and the lines under it, for the engine's own panel."""

    heading: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LevelStatus:
    headline: str
    detail: tuple[str, ...]
    progress: float


def benefit_sections(benefits: LevelBenefits) -> tuple[Section, ...]:
    lines = [f"Hit die: d{benefits.hit_die} (rolled by the engine on confirm)"]
    if benefits.retroactive_hp_gain:
        lines.append(
            f"Retroactive hit points from a raised constitution: +{benefits.retroactive_hp_gain}"
        )
    if benefits.prof_bonus_after > benefits.prof_bonus_before:
        lines.append(f"Proficiency +{benefits.prof_bonus_before} → +{benefits.prof_bonus_after}")
    lines.extend(
        f"Level {change.slot_level} slots: {change.before} → {change.after}"
        for change in benefits.spell_slot_changes
    )
    return (
        Section(heading=f"Level {benefits.level}", lines=tuple(lines)),
        *(
            Section(
                heading=f"{feature.name} — {features.actionability(feature)}",
                lines=(feature.desc,),
            )
            for feature in benefits.features
        ),
    )


def plan_sections(plan: AdvancementPlan) -> tuple[Section, ...]:
    sections = benefit_sections(plan.benefits)
    if not plan.selections:
        return sections
    return (
        *sections,
        Section(
            heading="Your choices",
            lines=tuple(
                f"{selection.prompt.capitalize()}: {', '.join(selection.labels)}"
                for selection in plan.selections
            ),
        ),
    )


class Dnd5eAdvancement:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def available(self, state: GameState) -> bool:
        current = self._player(state).progression
        return current is not None and current.level_up_available

    def status(self, state: GameState) -> LevelStatus:
        actor = self._player(state)
        if actor.progression is None:
            return LevelStatus(
                headline="5e advancement unavailable",
                detail=("This character has no class, so there is nothing to advance.",),
                progress=0.0,
            )
        current = actor.progression
        features_detail = self._features(actor)
        if current.level >= MAX_LEVEL:
            detail = (f"Level {MAX_LEVEL} is the last.", *features_detail)
        elif current.level_up_available:
            detail = (f"Level {current.level + 1} is ready.", *features_detail)
        else:
            detail = ("No level-up has been awarded yet. Keep playing.", *features_detail)
        return LevelStatus(
            headline=f"level {current.level}",
            detail=detail,
            progress=current.level / MAX_LEVEL,
        )

    def preview(self, state: GameState) -> LevelUpPreview:
        player = self._checked(self._player(state))
        return progression.preview(player, self._ruleset)

    def plan(self, state: GameState, decisions: Decisions) -> AdvancementPlan:
        player = self._checked(self._player(state))
        return progression.plan(player, decisions, self._ruleset)

    def advance(self, decision: AdvancementDecision, state: GameState, rng: Random) -> Transition:
        decisions = load_decision(decision)
        world = Dnd5eWorld(state=state.draft(), rng=rng, ruleset=self._ruleset)
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
        return read_player(state)

    @staticmethod
    def _checked(player: Dnd5eActor) -> Dnd5eActor:
        if player.progression is None or not player.progression.level_up_available:
            raise ValueError("no 5e level-up has been awarded")
        return player
