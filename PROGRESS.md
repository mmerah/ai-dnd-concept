# Refactor progress

Plan: `REFACTOR-LENIENT.md`. One commit per phase; gates green before each commit.

## Phase 0 — eval harness — done, staged, not committed

- [x] `scripts/evals/probes.py` — era adapter: 12 probe models, resolved against today's typed state
- [x] `scripts/evals/run.py` — case model, runner, three-way scoring, results writer, CLI
- [x] `scripts/evals/characters/{bram,elowen}/` — eval-only fighter and wizard fixtures
- [x] `scripts/evals/scenarios/*.json` — 21 cases, 15 tagged `combat`
- [x] Every setup verified offline; every numeric bound verified by Monte Carlo against the real
      resolution code (`procedures.swing`, `spells.cast`, `features.use`)
- [x] Baseline measured twice against identical code, both records committed to `results/`
- [x] `scripts/evals/BASELINE.md` — rates, measured drift, pre-registered phase-3 thresholds
- [x] Gates green: 182 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean

Baseline at `e174637`, `openai/gpt-oss-120b`, `retries=3`, 63 turns per suite, mean of two runs:
**interpretation 74.2%, completion 95.2%, combat 67.8%, overall 70.6%.**

### Decisions taken

- **Three numbers, not one.** The first runs showed most failures were
  `UnexpectedModelBehavior: Tool 'X' exceeded max retries`, not bad arithmetic. A single blended rate
  would gate the refactor on this model's function-calling reliability, so every run is now recorded as
  completed / passed / failed and the suite reports **completion**, **interpretation** (pass rate among
  completed turns — the rules-reading signal) and **overall**.
- **Bands sized from measured drift, not guessed.** Two runs of identical code drifted 1.6–6.3 points on
  the three gate metrics, and up to 33 points on tags with ≤6 runs. Hence 12/10/12-point bands, and a
  tag-level rather than scenario-level collapse condition — at 3 runs a scenario swings 100%→33% on one
  turn, so a per-scenario floor would fire on noise.
- **Reuse `director_step`/`TurnWorkspace` from `aidm.workflow.pipeline`** instead of re-rendering the
  director prompt in the runner, so the eval exercises the code path the app uses.
- **Eval-only characters under `scripts/evals/characters/`.** Shipped `kael` carries only a lantern, so
  `procedures._held_weapon` refuses him every swing, and he casts nothing — no shipped character can
  exercise the arithmetic chains the eval exists to measure. `bram` (fighter, longsword + shortbow) and
  `elowen` (wizard) fill that gap; `kael` still covers the three non-mechanical cases, keeping shipped
  content in the suite. The scenario is always the shipped `whispering-vault`.
- **Probe vocabulary is written in post-refactor terms** (`pool` = `hp` / `slot-N` / feature index,
  `tag` = a condition name or `advancement-ready`, `set_number` keys like `armor-class`). Today those
  resolve into `StatBlock`/`Progression`; after phase 3 they are literally `Sheet` keys, so phase 3
  edits probe internals and touches no scenario file.
- **Typed 5e cannot express a starting level above 1** (`Dnd5eCharacterData` has no level field), so the
  `set_level` probe plays the level-ups out through `engine.advance`, answering each pending choice with
  its first legal option.
- **`pyproject.toml` gained `scripts/evals` in basedpyright's `extraPaths`**, matching how `scripts` and
  each `tests/` directory are already listed.

### Findings to carry into phase 1

1. **Multi-action turns are the largest single source of failures** — the director casts twice, swings
   twice, or adds a `damage` call after an `attack`, even when the prompt says "and do nothing else this
   turn". `single-action-discipline` scores 100%, so it *can* hold to one action. An explicit
   one-action-per-turn line in the phase-1 director procedure is the cheapest available win, and this
   suite will show whether it landed.
2. **Tool-argument compliance costs ~5% of turns** at `retries=3`. The lenient toolset in
   `core/mechanics.py` should prefer flat, obvious argument shapes over the fussier ones that fail today
   (`damage`'s `Magnitude`, `rest`'s enum). Watch `completion`, not just `overall`.
3. **The player's `armor-class` is hard-coded to 10** in `engines/dnd5e/engine.py`'s `initial_world` —
   never derived from dexterity or worn armour. When 5e moves onto the Sheet, `armor-class` has to be a
   number the content and the level rows actually set, or every player character stays at AC 10.
4. **Two required coverage items are unmeasurable today** and must gain scenarios in the phase that
   creates them: advantage via keep-highest (phase 1's `roll(mode=...)`) and concentration replacing a
   previous spell (a phase-3 `Sheet` note).

## Phase 1–3

Not started. Phase 1 begins with `core/sheet.py`, `core/mechanics.py`, `core/enginepack.py` and the
`git mv` of `dice.py` into core; it also amends CLAUDE.md's first Design rule as the plan quotes.
