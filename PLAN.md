# PLAN: the ownership inversion

Derived from VISION.md, which is the authority on the target and the reasoning; this file is
the order of work. Read VISION.md first. Reviewed by Codex (gpt-5.6-sol) against the code;
its corrections are folded in: the kit move rides the atomic port (no dual path), the
`connections` fold and `AuthoringTool` deletion share one phase, and every estimate below is
the audited number, not the first draft's.

## Ground rules

- Verification, from the repo root with `UV_CACHE_DIR` unset: `uv run pytest`,
  `uv run ruff check`, `uv run ruff format --check`, `uv run basedpyright`. "Full check"
  means all four.
- **Every phase records three counts before and after** (`.py` files only):
  `find <dir> -name '*.py' | xargs cat | wc -l` for `src`, `tests`, `evals`.
  Base: src 9076, tests 5691, evals 1783.
- **`src` must end at or below 9076.** A phase tracking above its own estimate stops and
  re-scopes; no invented cuts; the refused deletions (Codex driver, builtin authoring page,
  agent log) stay refused.
- Goldens regenerate only inside the phase that changes them, once, and every diff is read
  (`git diff tests/core/fixtures`) before the next plain run.
- Evals: targeted named cases only (`evals/turn_eval.py run --label <phase> --case <name>`),
  never a full run.
- Each phase ends with the game playable (`uv run aidm`, open a save, play a turn), and no
  phase leaves two live implementations of one concept.

## Phase 0: probe `change_world` against today's code

Bigger than a tuple swap; budget all of it:

1. **Before the swap**, run the multi-verb baseline on the old surface:
   `--label pre-union --case loner3e/three-things` (the shared multi-verb case) plus the
   three standing cases. `phase3-5` holds only the three named cases; there is no
   retroactive multi-verb comparison.
2. Add **arm telemetry** to the eval record (`Played` keeps successful tool names/arms;
   today they are discarded, so wrong-arm rate is unmeasurable).
3. Build the union in `world/tools.py`: per-engine union models (Breathless has no
   improvised-item arm), a described wrapper field (the `director_tool` schema guard
   requires descriptions), dispatch to the existing action functions. Update
   `world/prompts/director_world.md`.
4. Rewrite the ~22 test references to old tool names (`golden_turn_support.py`,
   `test_pipeline.py`, `test_code_mode.py`, …) to call `change_world` arms. Regenerate
   goldens once: schema fixtures **and** director-prompt fixtures move.
5. Record the union arm's schema size (complete per-engine tool lists run 10.9–15.9 KB
   today; the arm is the new number to watch).
6. Re-run the four cases against `pre-union`.

**Gate:** union at prior scores → ships, the kit inherits it. Union loses → revert, record
the numbers in VISION's future-work section, kit keeps separate verbs.

Estimate: −10 to −40 src (0 if reverted).

## Phase 1: kernel types, envelopes, protocol, service

New `aidm/kernel/` (or reshaped `state/`; pick once, at the start):

1. **Envelopes** for save, scenario, character: kernel metadata (ids, engine, packs, turn,
   history, prompt, notes) + one engine payload. **Two-stage parse at every disk boundary**:
   `content/io.py` catalog reads, save restore and `reload()`, authoring writes, launcher —
   envelope first, then the named engine's payload model. Launcher keeps skip-unreadable.
2. **The engine protocol** per VISION: `Engine[S]` with `state`/`scenario`/`character`
   payload types, static `tools`, `answer -> Resolution` (facts + notes),
   `views`, `new_game`/`validate` taking the envelope's pack ids — plus the erased base the
   composition root holds engines by.
3. Kernel-owned **view types** (Director/Narrator/Player, `PlayerPrompt`) and
   **`CreationPreview`**, produced by `creation.create()` alongside the payload — defined
   now, or the create page breaks before Phase 4.
4. **Denormalized speech**: the Narrator's output stays minimal (`speaker_id`, `text`); the
   resolver records persisted lines with speaker name + icon key; `Exchange` records the
   prompt's speaker the same way (succession attribution). Views carry `(id, name, brief)`
   art subjects including the player.
5. `GameSession` → `GameService`: rename, `view` accessor, explicit begin/call/end turn
   methods carrying both commit modes (builtin per segment; code mode per accepted call plus
   the closing narration).
6. Rewrite `tests/core/test_package_boundary.py` for the new package names now.

Temporary shim, counted, dies in Phase 3: the old `Engine` dataclass adapted behind the new
protocol — covering `begin_game`, creation, authoring entry, content I/O, restore, and the
catalog, not just the turn loop. All shipped scenario/character JSON and the state/save/turn
goldens are rewritten once, here.

Estimate: +180 to +300 src. Full check; goldens regenerated once and read.

## Phase 2: the hostile engine

In `tests/`: one resource, two procedures, no rooms concepts, built on the new protocol and
driven end to end through `GameService` (begin, turn with a `FunctionModel`, save, restore,
view render, a `PlayerPrompt` round-trip). If it needs a stub for any kernel concept, fix
the kernel now — Phase 3 may not require production changes to keep it green.

Estimate: ≈ 0 src, ~+150 tests. Full check.

## Phase 3: the atomic port — kit + three engines + authoring

The switchover cannot be split without dual paths (1024 lines of `world/` would need
re-exports; authoring writes the scenario format). One phase, sequenced inside, committed
as one:

1. **The kit**: `world/` becomes `aidm/kits/rooms/` as `RoomsState[S]` — `S` is the
   engine's discriminated sheet union, `Entity[S].sheet: S | None`, `player_id` in kit
   state — with `change_world` (Phase 0's winner; `during_suspension` semantics kept as the
   kernel tool flag), the view builder, mandatory leak checks, and the authoring module:
   draft model whose patch carries `connections` (authored entity shape exposes no writable
   `exits`; every connection preflighted before the patch's first mutation — `Draft.apply`
   atomicity must not regress), bars, growth. Delete `AuthoringTool`, `blank_authoring`,
   and the MCP publication branches in this same phase.
2. **Port 24XX first**: `TwentyfourxxState` on `RoomsState[SheetUnion]`, the ship as its
   own model (`buy_gear` installs into it), continuations via the kit's shared frozen call.
   Convert `evals/cases/twentyfourxx.py:fit-the-skiff` and the ship-upgrade test to the
   typed ship — the fixture exists; do not author a new one; the 55 case ids stay 55.
3. Port loner3e and breathless. Port-time micro-cuts ride along: `ItemSheet.broken`
   (derive from `breaks.current == 0`), the one-line `all_ids`/`find`/`thread` wrappers
   (keep `require`/`require_kind`), `offered`/`play_action` folded into the service.
4. Move the turn loop and service onto the protocol; delete the Phase-1 shim, the old
   `Engine` catalogue and helpers, the mechanics seam (`rules`, `mechanics_of`,
   `mechanics_patched`, `mechanics_delta`, `entity_maps`, `sheet_of`, stray-id validators),
   `resolvers`/`PendingOption.name/args`/`restored`'s option revalidation, and the kernel's
   `entity_discovered` branch (into `change_world`). Notes flow through `Resolution` onto
   the envelope.
5. Regenerate all goldens once; read every diff. Rewrite eval `setup`/`choose` against
   payloads; case ids and expectation names unchanged.

Estimate: −110 to −250 src; tests/evals move a lot — priced, recorded.
Eval: the three standing cases + `twentyfourxx/fit-the-skiff` at prior scores.

## Phase 4: code mode and UI onto the service and views

1. Code mode onto `GameService.begin/call/end` (commit semantics live in the service since
   Phase 1); absorb only real duplication — its LLM-facing prose (preamble, scene text,
   listings) stays.
2. UI and media onto views: chat/journal read persisted denormalized lines; `media.py`
   reads `(id, name, brief)` subjects (player included); create page reads
   `CreationPreview`; sheet/journal panels read the player view. Package-boundary test
   green throughout.

Estimate: 0 to −40 src. Full check; `uv run aidm` renders a game page, both authoring pages
work, the external viewer still renders from saves alone.

## Phase 5: scheduled deletions and the sweep

1. Collapse the trial-apply wrappers to one survivor (−20; they are 49 physical lines).
2. Delete the raw-state panel; keep the dev tab's agent log (−5; decided scope).
3. Old-plan carryovers: `page_header` merge + delete `show_engine_badge`; delete
   `GameSession._resumable`'s second validate; one line atop
   `docs/NEXT-ENGINE-RESEARCH.md` (≈ −10). (`_mechanic_event` does not exist; nothing to
   rename.)
4. Eval-gated: inline pack meanings at authoring time, deleting `describe_rows` and Loner's
   `meanings`/`pack_meanings` (−10 to −20) — one targeted case before keeping.
5. Codex extra cuts not already taken in Phase 3: media response models → one `AliasPath`
   boundary model (−20, cover empty/malformed/success); `ScenarioRun.write()` reuses the
   finish gate's validated `Scenario` instead of re-constructing (−12, keep the final
   validation at the disk write); inline `take_notes`/`close_segment` (−9, preserve
   code-mode commit timing and notes-read-once); merge `ui/panels.py` into `ui/game.py`
   once both are pure view renderers (−6).
6. Add the standing **identifier-level kernel-vocabulary test** (scope and allowlist per
   VISION) and the secrecy golden rebuilt on views.
7. Deletion sweep: grep every name Phase 3 deleted across `src`, `tests`, `evals`.

Estimate: −80 to −120 src. Full check after each numbered item.

## Done when

- [ ] Three counts recorded per phase; **`src` ≤ 9076**, or the overrun is reported with
      the phase that was stopped and re-scoped.
- [ ] Full check green; `uv run aidm` plays a turn on each of the three engines.
- [ ] Hostile engine green with no production-code special case; the `fit-the-skiff`
      upgrade installs into a ship model; vocabulary test and secrecy golden standing.
- [ ] Phase 0 gate outcome recorded (union kept or reverted, with the numbers).
- [ ] Named eval cases at prior scores (`loner3e/walk-and-look`, `loner3e/fight-the-rat`,
      `twentyfourxx/fight-the-wrecker`, `twentyfourxx/fit-the-skiff`,
      `loner3e/three-things` vs `pre-union`).
- [ ] Goldens regenerated only inside Phases 0/1/3, each read.
- [ ] This file deleted in the final commit; VISION.md stays; git log is the record.
