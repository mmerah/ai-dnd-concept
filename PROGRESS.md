# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

## Counts

| phase | `src` | `tests` |
|---|---|---|
| start (`2c3e8a5`, phase 8 committed) | 8,913 | 5,101 |
| 1 — Maze Rats and the rooms kit deleted | 6,365 | 4,144 |
| 2 — the seam and the player view | 6,334 | 4,221 |
| 2b — mechanical cuts from the phase 2 review | 6,225 | 4,202 |

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
8. **`Engine.guidance` and `Authoring.refusal` are deleted in phase 2.** The first was a round
   trip through the platform, the second duplicated `build` + `begin_game`. `Scenario.art_style`
   was slated with them because nothing wrote it; the maintainer chose instead to finish the
   feature (phase 2 fold 1): the field stays and the `/scenario` page writes it.

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

Each phase adds: counts before and after, the decisions made inside it, what the adversarial
review caught, and what was left known-and-accepted.

### Phase 1 — Maze Rats and the rooms kit deleted (2026-09-01)

- **Counts:** `src` 8,913 -> 6,365 (target about 6,350); `tests` 5,101 -> 4,144. 37 files
  staged, +5 / −9,669. Loner goldens byte-identical; no regeneration.
- **Off-plan, decided inside the phase:** `tests/ui/test_launcher.py` listed `("kael",
  "mazerats")` in two assertions the plan did not name; trimmed to Loner. `CLAUDE.md` design
  rule 2 named `src/aidm/kits/rooms/`; the clause was dropped so the rule file stays true (phase 5
  still rewrites the rule). Untracked residue removed: the empty
  `tests/core/fixtures/schemas/mazerats/` and `tools/__pycache__`, so `tools/` is gone.
- **Review:** Fable found the three items above, all fixed; Codex Sol found nothing. No
  refutations.
- **Known and accepted:** `uv run aidm` serves the home page (HTTP 200); on SIGTERM it logs
  `RuntimeError: Attempted to exit cancel scope in a different task` from
  `src/aidm/app/mcp.py:34`, a shutdown-only fault in code this phase does not touch.

### Phase 2 — the seam and the player view (2026-09-01)

- **Counts:** `src` 6,365 -> 6,334 (target about 6,285; −31 against −80); `tests` 4,144 ->
  4,221. 24 files staged (the research doc is most of the deletion). Every golden byte-identical;
  no regeneration. The shortfall: the `PlayerView` collapse moved fields into `Panel` rows
  instead of deleting them, and the plan's −80 counted the fields alone; the `art_style` writer
  (below) added about 17. Nothing was invented to close the gap (`PLAN.md` rule 6).
- **Off-plan, decided inside the phase:** step 6 reversed by the maintainer — `Scenario.art_style`
  stays and gets its writer: an "Art style" input on the `/scenario` page, carried through
  `Runtime.new_scenario(..., *, art_style)` and `Authoring.build(title, premise, art_style, packs,
  written, source)`; the illustrator reads `scenario.art_style or settings.media.style` as before.
  The sidebar draws the `Sheet` card first, then the
  engine's panels in the order it lists them; the kit's panels are `This scene`, `Here`,
  `Traits`, `Carrying`, `Threads`, `Trail`, so the Trail moved from the journal into the sidebar
  and the scene header's breadcrumb is gone. `Transition.arrival_brief` carries no comment: its
  type says what `None` means. `GameService._write` lost its `noun` parameter (one log line). The "crossing" word
  left `app/runtime.py`'s comments and log lines because the done-when grep forbade it there;
  `worldsmith.CROSSING` and `arrival_brief` keep it in the kit.
- **Review:** Fable found three (the `Engine` member order against `VISION.md`, a double
  `ready` check on the extend path, a test named for the deleted `world_tools` tier) and three
  cuts (`tuple(packs)`, `transition` bound twice, the `noun` parameter); Codex Sol found the
  member order alone. All six fixed; no refutations. Fable's second pass listed about −90 lines
  of cuts outside the phase (spawn token accounting, `engine_text`, one-field config wrappers
  and more; its `AGENTS.md` item was wrong, that file is already a symlink). Not folded here;
  they became step 2b below.
- **Known and accepted:** the `ready` lambda in Loner's `Transition` and the `_entity_known`
  adapter survive until Phase 3 step 4. The extend path (`arrival_brief is None`) has no engine
  behind it until Tunnel Goons; one test drives it through a replaced `Transition`. Smoke:
  `uv run aidm` serves `/` and the game page (both HTTP 200, panels rendered); no turn was
  played (a turn spawns live CLIs); the Phase 1 shutdown fault at `app/mcp.py:34` is unchanged.

### Step 2b — mechanical cuts from the phase 2 review (2026-09-01)

Not a `PLAN.md` phase: the out-of-phase cuts Fable's phase 2 review listed, taken as one commit
between phases 2 and 3 so the phase 3 diff stays about `kits/`.

- **Counts:** `src` 6,334 -> 6,225 (−109; the review guessed about −90); `tests` 4,221 -> 4,202.
  Goldens byte-identical.
- **Cut:** spawn token accounting (`RunResult.input_tokens/cached_tokens`, `_ClaudeUsage`,
  `_count`); `_FILENAME_SAFE` re-checks in `media.py` (`Speaker.id` and `Subject.id` are now
  `CheckedEntityId`, so the type holds the invariant); `TurnConfig`/`SourceConfig` flattened to
  `Settings.recent_exchanges` and `Settings.source_max_chars` (env keys `RECENT_EXCHANGES`,
  `SOURCE_MAX_CHARS`; the local `.env` held neither old key); `engine_text`, `_copy`
  (`shutil.copyfile`), `_content_dirs`; `Turn.landed`, `Game.take_notes`, `Narration.text`,
  `told_traces`, `illustrate_scene` (now public `illustrate(narration="")`), `_premise`, the
  `render_sections` alias (`render_picture`'s parameter became `engine_sections` so the import
  is not shadowed), `Header` folded into `EngineHeader`.
- **Decided by the maintainer:** `RoleConfig.command` and the raw-command branch deleted; the
  page's dev tab and `master_log` deleted; `ClaudeDriver.parse` raises on non-JSON output
  instead of reading it as loose text.
- **Refuted from the review's list:** `picked()` (eleven identical `.get(id, "")` calls are what
  a helper is for); `_open_game` (two callers, not one); `AGENTS.md` (already a symlink to
  `CLAUDE.md`; the review's `diff -q` followed the link).
- **Tests:** the env-allowlist test started a real `sh`, which `CLAUDE.md` forbids; the env dict
  became `child_environment(secrets)` and the test checks it without a process. The raw-command
  timeout test lost `command=`; a test proves `parse` raises on prose.
- **Review:** Fable found five (a malformed `PROGRESS.md` line, a `_ = await` leftover, the
  cleared-box arm of `_changes` untested, the `.env` rename risk — checked, none present — and a
  stale key name in `IDEAS.md`); Codex Sol found the missing `parse` test. All fixed. Sol's cut
  "drop the `PROGRESS.md` edit" refuted: the brief's out-of-scope list bound the implementer.
