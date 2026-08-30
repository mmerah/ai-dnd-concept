# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

Start: `src` 9,452 lines, `tests` 6,044 lines.

## Probes (done, before phase 1)

**The scene kit.** A throwaway kit driven by a real CLI: 5 turns and one scene write.
`change_world` came to 5,479 bytes across 11 arms, against the map version's 5,926 across 10.
Zero schema-invalid and zero rule-refused calls. The worldsmith wrote a strong scene — a
complication drawn straight from the source, two existing cast brought back, the secret kept —
in 335 seconds, with one id error. Two fixes came from it: the scene boundary is computed by
`scene_spent`, not judged by the game master, and the worldsmith never names the player.

**`SceneState[S]` round-trip.** A generic parameterised by a discriminated sheet union, inside a
payload discriminated on `engine`. Sixteen checks passed: byte-identical JSON round-trip, both
discriminators rejecting bad input, the kit's validator still firing through the generic,
`extra="forbid"` holding, two engines coexisting under one adapter, and schemas generating.
`basedpyright` keeps full type information throughout — nothing degrades to `Unknown`. The one
rule: sheet unions must be plain assignments, never `type X = ...`, or the discriminator breaks.

## Phase 0 — Keep the probe code — DONE

Counts unchanged: `src` 9,452, `tests` 6,044. Phase 0 adds no shipped code.

Both probe programs moved into `docs/probes/` (637 lines), excluded from ruff, and left out of
`basedpyright` by its existing `include` list. Each file gained a header saying what it proved
and what it lacks, and its `/tmp` imports were made relative.

- `scene_kit.py` — the eleven `change_world` arms, `apply_change`, `render_worldsmith`,
  `scene_unmet`. **No `apply_scene`, no `scene_spent`**; those are new work in phase 2.
- `scene_fixture.py` — the drowned-road fixture the probe played against.
- `state_spike.py` — the `SceneState[S]` round-trip, 16 checks.

Verification: 289 passed; ruff check, ruff format and basedpyright all clean.

## Phase 1 — Cut to one engine

Not started.
