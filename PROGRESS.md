# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Shipped

- **2026-08-13 — Recentering, and the engine shelf.** The project ships official, freely licensed,
  LLM-friendly systems only. Exact SRD extractions written for the shipped engines
  (docs/LONER-3E.md, docs/24XX.md) and for the shelf (docs/CAIRN-2E.md — ~2× loner3e's code,
  implemented only if that texture is wanted). Each names every deviation its implementation takes.

- **2026-08-13 — Delete what the recentering stranded.** The eval harness (−1,199) and the story
  engine with its tests, fixtures and overlays (−3,177) are gone; live eval gates stay suspended,
  golden fixtures and offline parity tests are the safety net.

- **2026-08-13 — loner3e.** The tag-based engine: one closed question, Chance d6 against Risk d6,
  six outcomes, a game-wide Twist Counter, Harm against Luck. Twists narrate the turn they land and
  the note develops them the next turn.

- **2026-08-13 — Shrink and comply** (11 steps, SAVE_VERSION 57). Two full-tree audits' findings:
  dead dice generality and per-engine boilerplate deleted, ~250 lines of prompt prose moved from
  Python into `*.md`, content packs (SRD + AP01 fantasy) with table-set selection as creation
  step 0, SRD compliance prose landed, opponents' sheet tags reachable by the resolver, Luck reset
  when a conflict ends, and the vestigial save fields removed.

- **2026-08-14 — Redesign refactor** (9 steps, SAVE_VERSION 58→61). The engine contract, roster,
  capability shape, hooks/clocks, overlays and packs, ending in a second engine as the proof:
  - Roster is 3 in-turn roles: the two Directors merged into one that writes scene judgment
    (`focus`/`pressure`/`stakes`/`speaker_id`) before its action. Worldkeeper survives.
  - `Advancement` generalized to a subject-aware `Subsystem` with one generic `Applied` trace
    entry, so NPC advancement fell out and a new capability edits no core file.
  - `roll_pool(faces, reason, rng)` keeps the highest die and replaced expression parsing and
    `RollMode`; threads gained clocks; hooks gained `once`, engine effects, and a bounded
    `fire_hooks` drain (`MAX_HOOK_ROUNDS = 3`, `hooks_capped` fact) that closed a dead chain.
  - Engines declare `rules_type`, so authored overlays validate field-by-field at load; `commit`
    split into a pure `validate` (never repairs) and a `seed` the pipeline runs for every
    `entity_created` fact. Packs load from `Settings.packs_dir` and pack identity persists in saves.
  - **24XX** (`src/aidm/engines/twentyfourxx/`, 613 LOC): skill-die pools, one `attempt`, three
    outcomes, the bad-luck test, credits, advancement as a Subsystem, creation from its own pack.
    Registering it was one entry in `ENGINE_MODULES` and no edit in `state/`, `turn/`, `app/`,
    `ui/` — the acceptance bar the refactor was built to meet.
  - A fidelity pass then closed four deviations: the specialty kit and the comm land as traits at
    creation (so a created character can actually cite the gear the Director is taught to look
    for), Muscle's either/or and Psychic's d10 are a conditional creation step, and an Alien picks
    two traits from the SRD's own examples. What the two engines share moved to
    `engines/sheets.py`, `engines/tags.py` and `engines/packs.py`.

## Standing facts

- **Probe a reshaped role schema live before trusting it.** gpt-oss-120b wrote zero plan effects
  under `NativeOutput` on the old Director schema; the Director now runs on `ToolOutput`. The
  merged Director schema was probed live on 2026-08-14 and answered fine.
- **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` only in the same commit as
  the change that justifies it, and read the diff. A SAVE_VERSION bump moves the save, state and
  turn families together; the current version is 61.
- **`Providers` stays a model, not a dict.** pydantic-settings does not merge a partial env
  override into a dict field's default, so `providers: dict[str, ProviderConfig]` breaks a `.env`
  that sets only `PROVIDERS__OPENROUTER__API_KEY`.
- **Accepted gaps.** A resumed save's hooks are parsed at fire time only (the scenario they came
  from is checked at load). The `hooks` step trace records the first pass; the Worldkeeper-pass
  fires reach `turn.facts` but no step. A user pack repeating a skill inside one specialty fails
  at creation rather than at load.
- **Licensing.** loner3e's prose and packs are CC BY-SA (Roberto Bisceglie / Zotiquest Games);
  `packs/ap01-fantasy.json` derives from a page whose own footer states only a plain copyright
  while the site declares CC BY-SA — treated as covered, flagged in README. 24XX is CC BY
  (Jason Tocci) and its licence requires the credit line the engine's prose and pack carry.
- **LOC.** 5,561 production lines; 4,948 outside the 24XX package, against the refactor's
  ≤4,823 bar — ~105 of the excess is the shared engine layer (`sheets.py`, `tags.py`, the pack
  helpers) that exists only because there are two engines. Two trim audits found no further
  genuine waste, and the rule is not to force deletions to hit a number.

## Next

- PLAN.md Phase 1: the scenario creator script, which binds to `ScenarioWorld`,
  `Engine.rules_type`, `write_scenario` and `begin_game` — all landed.
