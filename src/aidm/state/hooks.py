from collections.abc import Sequence

from .actions import advance_thread
from .facts import Fact
from .world import Game, Hook

MAX_HOOK_ROUNDS = 3


def fire_hooks(draft: Game, facts: Sequence[Fact]) -> list[Fact]:
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
            kind="hooks_capped",
            trace=f"hook chain stopped after {MAX_HOOK_ROUNDS} rounds",
        )
    )
    return fired


def _hook_round(draft: Game, facts: Sequence[Fact]) -> list[Fact]:
    discovered = {
        entity_id
        for fact in facts
        if fact.kind == "entity_discovered"
        and isinstance(entity_id := fact.data.get("entity_id"), str)
    }
    fired: list[Fact] = []
    world = draft.world
    for hook in world.hooks:
        if hook.id in world.fired_hooks or hook.on_discover not in discovered:
            continue
        world.fired_hooks = (*world.fired_hooks, hook.id)
        fired.append(_hook_fact(hook, "hook_fired", f"hook {hook.id} fired"))
        try:
            for entity_id in hook.reveals:
                fired.extend(draft.reveal(world.require(entity_id)))
            if hook.advance_thread is not None:
                fired.extend(advance_thread(draft, hook.advance_thread))
        except ValueError as refused:
            # The note claims the consequence landed, so a refused hook must not steer on it.
            fired.append(_hook_fact(hook, "hook_failed", f"hook {hook.id} stopped: {refused}"))
            continue
        if hook.note:
            world.pending_notes = (*world.pending_notes, hook.note)
    return fired


def _hook_fact(hook: Hook, kind: str, trace: str) -> Fact:
    return Fact(kind=kind, trace=trace, data={"hook_id": hook.id})
