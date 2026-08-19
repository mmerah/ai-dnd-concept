# Opinion 3 — drastic simplification, same vibe

Mechanically, both engines need only actors with sheets; everything else exists for the app's own
guarantees (leak-proof Narrator, gated movement, discoverable secrets). So cut by guarantee, not
by entity kind — and collapse the plan lifecycle, where the real weight is.

## 1. Tool-calling Director replaces the beat loop

The Director runs once per turn with tools instead of one structured beat per call: roll tools
(`roll_question`, `roll_attempt`) return the dice outcome inside the same agent run, so it reacts
without being re-prompted. Effects become tool functions — the typed signature is the schema, the
resolver body the implementation. Tools mutate only the turn's draft through resolver code
(trial-copy validation first, as `expand_world` does); the turn still commits whole or not at all.

Deleted: `_run_beats`, `Followup`/settle, `beat.md`/`settle.md`, ASKED-AGAIN plumbing,
`Engine.beat_type`/`unpack_beat`/`check_beat`/`resolve_beat`/`_play`, the per-engine `*Beat`
models and `examples.json`, the `effects.py` op classes with their unions and dispatch.
`Engine` shrinks to sheet type, `describe`, and its extra tools.

## 2. Delete `Relation`

Core only ever interprets `connected` and `party-member`; any other kind is inert. Replace with
`exits: list[Exit(to, known, locked)]` on locations and `party: list[EntityId]` on the world.
Gone: undirected-id sorting, `joins`/`touches`/`far_end`, the reachability walkers (rewritten
against exits), the 4-mode `RelationChange` op. Moving through an unknown-but-existing exit
auto-reveals it — the Director moving the player IS the fiction revealing the way; locked refuses.

## 3. Shrink `Hook` to one concrete shape

`Hook(on_discover: EntityId, note, reveals, advance_thread)` — what nearly every authored hook
already is. The `FactMatch`/`DiscoveryMatch`/`ThreadMatch` hierarchy, dump-based matching, the
domino validator, and `WorldEffect`-as-persisted-data all die with it.

## 4. Shrink `Memory`

The Worldkeeper stays — a dedicated role is what keeps memories high-quality — but the model
loses its ceremony: `(owner, text)` pairs, no slug ids.

## Keep untouched

Entity's three kinds, `Trait`, `Counter`, `Thread`+clock; the `VisibleScene` leak boundary (the
Narrator's input type has no field a leak can travel through); transaction/commit discipline;
overlay validation; save versioning; packs; advancement; both engine rule implementations.

## Accepted consequences

Raise the Director's token budget and reasoning effort (a tool loop needs both); one live probe
before fixture work, per PLAN rule 2. All golden fixtures and much of `tests/core` get rewritten.
CLAUDE.md/AGENTS.md: "turn-loop tools are read-only" becomes "tools mutate only the turn's draft
through resolver code".
