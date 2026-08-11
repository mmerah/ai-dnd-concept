from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from random import Random

from aidm.content.authored import Rules
from aidm.engines.counters import CounterChange
from aidm.engines.loader import Engine, EntityRenderer
from aidm.state.base import EngineId, EntityId, Slug
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_all, apply_branch, check_action, check_effects
from aidm.state.world import GameState

from .actions import Action, Attack, CastSpell, Check, Improvise, Rest, TurnPlan, UseFeature
from .advance import Dnd5eAdvancement
from .content import ENGINE_DIR, PROJECTING
from .mechanics import apply, begin, commit, render
from .resolve import dispatch_action, spell_of

ENGINE_ID: EngineId = EngineId("dnd5e")
CONTESTED = frozenset[Slug]({"success", "failure"})
UNCONTESTED = frozenset[Slug]()
SLOT = "slot-"


class Dnd5eEngine(Engine):
    id = ENGINE_ID
    badge = ("D&D 5E", "red-9")
    plan_type = TurnPlan
    engine_dir = ENGINE_DIR

    def __init__(self, pack_paths: Sequence[Path] | None = None) -> None:
        super().__init__(pack_paths)
        if unknown := sorted(set(PROJECTING) - set(self.collections)):
            raise ValueError(f"projecting names no such collection: {unknown}")
        self.advancement = Dnd5eAdvancement(self)

    def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None:
        begin(self, state, rules)

    def commit(self, state: GameState) -> None:
        commit(self, state)

    def renderer(self, state: GameState) -> EntityRenderer:
        return render(self, state)

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        assert isinstance(plan, TurnPlan)
        action = plan.action
        if action is None:
            return check_effects(state, plan, UNCONTESTED, apply)
        if refusal := _double_spend(plan, action):
            return refusal
        return check_action(
            state,
            plan,
            _labels(self, action),
            apply,
            lambda draft, rng: dispatch_action(self, draft, action, rng),
        )

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        facts, outcome = dispatch_action(self, draft, plan.action, rng)
        if outcome is not None:
            facts.extend(apply_branch(draft, plan, outcome, apply))
        return facts + apply_all(draft, plan.effects, apply)


def _labels(engine: Engine, action: Action) -> frozenset[Slug]:
    """Contested only when the roll can fail: for a spell, when its facts carry an attack or a
    save. A bad ref falls back here; the trial resolve refuses it before the labels are read."""
    match action:
        case Attack() | Check():
            return CONTESTED
        case Improvise():
            return CONTESTED if action.vs is not None else UNCONTESTED
        case CastSpell():
            try:
                record = spell_of(engine, action.spell)
            except ValueError:
                return UNCONTESTED
            contested = "attack-type" in record.facts or "save-ability" in record.facts
            return CONTESTED if contested else UNCONTESTED
        case UseFeature() | Rest():
            return UNCONTESTED


def _double_spend(plan: TurnPlan, action: Action) -> str | None:
    """The engine pays the action's own cost; a plan that also writes it spends twice."""
    paid = _paid_by_engine(action)
    if paid is None:
        return None
    payer, engine_pays = paid
    written = (*plan.effects, *(effect for branch in plan.branches for effect in branch.effects))
    for effect in written:
        if (
            isinstance(effect, CounterChange)
            and effect.entity_id == payer
            and engine_pays(effect.counter)
        ):
            return (
                f"the engine already spends {effect.counter!r} for this action: "
                "drop that effect and let the engine pay the cost"
            )
    return None


def _paid_by_engine(action: Action) -> tuple[EntityId, Callable[[str], bool]] | None:
    match action:
        case CastSpell():
            return action.actor_id, lambda counter: counter.startswith(SLOT)
        case UseFeature():
            return action.actor_id, lambda counter: counter == action.counter
        case _:
            return None


ENGINE = Dnd5eEngine
