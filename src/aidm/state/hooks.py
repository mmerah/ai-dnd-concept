from collections.abc import Sequence

from .apply_effects import apply_effect
from .facts import CORE, Fact
from .world import GameState, Hook

MAX_HOOK_ROUNDS = 3


def fire_hooks(draft: GameState, facts: Sequence[Fact]) -> list[Fact]:
    """Hooks fire in bounded rounds, so hooks feeding each other stop instead of looping."""
    fired: list[Fact] = []
    pending: Sequence[Fact] = facts
    for _ in range(MAX_HOOK_ROUNDS):
        produced = _hook_round(draft, pending)
        fired.extend(produced)
        if not produced:
            return fired
        pending = produced
    fired.append(
        Fact(
            source=CORE,
            kind="hooks_capped",
            trace=f"hook chain stopped after {MAX_HOOK_ROUNDS} rounds",
        )
    )
    return fired


def _hook_round(draft: GameState, facts: Sequence[Fact]) -> list[Fact]:
    fired: list[Fact] = []
    world = draft.world
    for hook in world.hooks.values():
        already = hook.id in world.fired_hooks
        if (hook.once and already) or not any(hook.match.matches(fact) for fact in facts):
            continue
        if not already:
            world.fired_hooks = (*world.fired_hooks, hook.id)
        fired.append(_hook_fact(hook, "hook_fired", f"hook {hook.id} fired"))
        for effect in hook.effects:
            try:
                fired.extend(apply_effect(draft, effect))
            except ValueError as refused:
                fired.append(_hook_fact(hook, "hook_failed", f"hook {hook.id} stopped: {refused}"))
                break
        if hook.note:
            world.pending_notes = (*world.pending_notes, hook.note)
    return fired


def _hook_fact(hook: Hook, kind: str, trace: str) -> Fact:
    return Fact(source=CORE, kind=kind, trace=trace, data={"hook_id": hook.id})
