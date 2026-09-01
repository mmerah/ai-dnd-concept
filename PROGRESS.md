# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

## Counts

| phase | `src` | `tests` |
|---|---|---|
| start (`2c3e8a5`, phase 8 committed) | 8,913 | 5,101 |

## Why the plan was rewritten (2026-09-01)

Phase 8 shipped the rooms kit and Maze Rats, green, and the result was read against the tree:

1. **Each kit had one consumer.** Scenes existed for Loner, rooms for Maze Rats. Engines imported
   concrete kit state, verbs, renderers and worldsmith functions, not an interchangeable
   abstraction. The platform never named a kit; the kit layer sat between two things that did not
   need it.
2. **The generic world made both engines lie.** `Entity[S]` with `sheet: S | None` let an item
   carry no sheet where Loner's SRD says everything is a character, and let an actor be held by an
   item where Maze Rats forbids it; both engines re-checked after the fact what their own models
   could have made impossible.
3. **The seam grew to 27 members and 100 adapter lines per engine** (`_record`, `_history`,
   `_world_of`, `cast(LonerScene, …)`) whose only job was to plug kit functions into an engine.
4. **Maze Rats is too large for MVP0.** 1,688 engine lines plus an 856-line kit, and `rules.py`
   alone at 905, for an engine meant to prove the platform runs two games. Its rules survived two
   SRD audits and stay in git at `2c3e8a5` for a self-contained return.
5. **Measured shares:** shared kit substrate 393, scenes 810, rooms 856, Loner 965, Maze Rats
   1,688. Folding a kit into its engine is expected to shrink the pair 10–20%, not half; the win is
   one owner per line and structural invariants, not the count.

The decision: no kits; each engine owns its world; the platform owns none; MVP0 is Loner 3e and
Tunnel Goons, the two engines that play least alike. A second opinion (Codex) reached the same
recommendation independently and is folded into `VISION.md`.

## Standing decisions — settled, do not re-propose

1. The thirteen items under "Settled" in `PLAN.md`.
2. **The union payload and sheet erasure are refuted.** `SceneState[S]` is invariant; erasing
   `[S]` renders the worldsmith a sheet schema of `{}`. Engine-owned, non-generic world models make
   both questions moot.
3. **Route 2 stands**: `Game[P]` with a `SerializeAsAny` payload and a per-engine `Game` subclass.
   Every save boundary loads through the engine's concrete `game`, `scenario` and `character` types.
4. **Speculative scene writing is deleted**, and `Scene.ways_out`, a travel tool and a menu of
   destinations are refused in Loner. The player's own sentence is the whole brief for the next
   scene. An authored map is a different engine's world, not a Loner feature.
5. **`packs` stays on the envelopes and on `Engine`.** Tunnel Goons has none and ships `()`; 24XX,
   Breathless and Maze Rats all have them.
6. **The `PlayerView` collapse is decided**: `sheet` plus titled `panels` whose rows may carry an
   icon id. The page draws what the engine hands it and knows no field called companion, thread,
   carrying, focus or trail.
7. **Decision options stay.** A review proposed deleting `PendingOption`, `Engine.answer` and
   `PendingDecision.options` because only Maze Rats built options. Refused: Tunnel Goons'
   `level_up` is an option pick (which ability; HP or Inventory), and the SRD gives the choice to
   the player, not to prose.
8. **`Engine.guidance`, `Authoring.refusal` and `Scenario.art_style` are deleted in phase 2.** The
   first was a round trip through the platform, the second duplicated `build` + `begin_game`, the
   third was never written by anything.

## Open — known and accepted

1. The local `saves/whispering-vault--kael.json` does not load and never did after the scene
   pivot. The home page logs it and skips it; `saves/` is untracked.
2. `tests/core/fixtures/source/drowned-road.{md,pdf}` are kept: `test_documents` reads them.
3. `docs/24XX.md`, `docs/BREATHLESS.md` and `docs/MAZE-RATS.md` cite deleted code paths. They are
   the notes for those engines' return and are rewritten then.

### The spawned CLIs — measured in phase 7B, still true

4. The codex master's cold start is `PLAN.md` settled item 13.
5. **Codex keeps a shell.** `--disable shell` and `--disable mcp` are rejected, so the acceptance
   is least privilege: read-only sandbox, empty working directory, `--ignore-user-config`,
   `--disable apps`, `web_search=disabled`, scrubbed environment. `--ignore-user-config` alone left
   the account's MCP servers standing; `--disable apps` removes them. Measured on codex-cli 0.151.0.
6. **Claude keeps `Read`.** Naming no built-in tool re-enables all of them. `--tools ""` disables
   nothing. `--restricted` drops the command-running tools and `WebFetch`. Measured on Claude Code
   2.1.251, where `--model` and `--effort` both exist.
7. **`HOME` is on the allowlist**, so a Claude role can still see `~/.claude`.
8. **The default models are Claude aliases.** Moving a role to codex means changing `model` in the
   same edit.
9. **A cold retry can open on a refusal.** `start_turn` sets `started` but lands no fact, so a
   master that dies straight after it is retried cold, and that retry's first call answers
   `ALREADY_OPEN`. It is an answer, not a crash.

## Adversarial review of the plan (2026-09-01)

A Fable subagent reviewed `VISION.md` and `PLAN.md` against the tree before any phase began. It
returned 26 findings; 25 were folded, one refused (standing decision 7). The two blockers: the
platform's `master.md` and `Turn.call` hard-coded Loner's `next_scene`, so "no `if engine` above
the seam" was false before Tunnel Goons existed (now phase 3 step 2); and "no `partial`" could not
hold while packs load at `build()` time (settled item 5 amended). Loner's landing was re-estimated
from 1,800 to about 1,950 on the reviewer's count (965 + 810 + 393 today, ~100 of it adapters).

## Phase entries

None yet. Each phase adds: counts before and after, the decisions made inside it, what the
adversarial review caught, and what was left known-and-accepted.
