# AI Dungeon Master

A role-separated narrative game platform with two first-party rules engines:

- **AIDM Story** — the default narrative-first, rules-light engine.
- **AIDM 5e** — the D&D 5e implementation, isolated in its own engine package.

```text
prompt → SCENE → RULES → resolve → hooks → NARRATOR → WORLDKEEPER → commit
      directive  one plan  engine code  facts fire   prose      new canon
```

The Scene Director decides what the turn is about; the Rules Director answers with one structured
turn plan — the single action resolved this turn, its fiction consequences keyed by outcome, and
unconditional effects. Engine code validates the plan against committed state, resolves it
deterministically on a draft (rolls, costs, intrinsic outcomes), committed Facts fire the
scenario's authored hooks, and core commits a fully revalidated state. An engine is ordinary typed
Python plus content: a sheet template, action models with their resolvers, and content records
whose `facts` map carries every mechanical value the resolver reads. The Narrator receives no
unrevealed canon; for visible entities it receives the same state as the other roles, with
instructions to translate mechanics into fiction rather than recite stat blocks.

## Run

From the repository root:

```bash
uv sync
uv run aidm
```

The app opens at <http://localhost:8080>. Configure
`PROVIDERS__OPENROUTER__API_KEY` in `.env`. The home page lists saves and lets you choose a
scenario, rules engine, and compatible character. Story and 5e are both included. The game header
always identifies the active engine.

Run repository checks with:

```bash
uv run ruff check
uv run basedpyright
uv run pytest
```

A live-model eval harness lives in `scripts/evals/` (`uv run python scripts/evals/run.py`,
`--only director|advisor|worldkeeper` to pick a suite). Each case replays an authored turn
against the real provider and probes the committed state, so what it measures is model
reliability on this codebase's actual schemas and prompts. It runs manually when a
model-facing surface changes — never from pytest, and it is not a merge gate. At 3 runs per
case, single-case movement is noise; re-run before attributing anything below n=9.

## Layout

```text
src/aidm/state/           the deterministic machine: world, sheet, effects, plans, dice, trace
src/aidm/content/         authored scenarios and characters, saves and traces
src/aidm/engines/         the loader, plus one directory per engine
src/aidm/turn/            the turn loop, its agents, prompts, advancement
src/aidm/app/             composition root: launcher catalog, sessions, runtime
src/aidm/engines/story/   Story engine: spec, director procedure, rules
src/aidm/engines/dnd5e/   5e engine: spec, director procedure, SRD pack, rules
src/aidm/ui/              NiceGUI shell: renders state, submits decisions
scripts/srd/      one-shot importer projecting an upstream 5e-database checkout into the pack
scripts/evals/    live-model eval harness, run manually and never from pytest
characters/       shared character canon plus one overlay per supported engine
scenarios/        shared world canon plus one overlay per supported engine
tests/            per-package suites: core, story, dnd5e, ui
```

One distribution. The import direction — `state <- content <- engines <- turn <- app <- ui`, with
`aidm/config.py` a leaf every layer may read — is enforced by
`tests/core/test_package_boundary.py`: the engines do not import each other or `aidm.ui`, and
nothing below `app` imports the UI or NiceGUI. The shipped SRD pack is package data under `src/aidm/engines/dnd5e/packs/`.

The **Trace** tab shows the Director's plan, resolved facts, and the exact prompt received
by each role. The **State** tab shows the committed game state. **Advancement** drafts a proposal
through an advisor role; the player reviews each change and its reason, then confirms.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `PLAN.md`: the phased plan for what is built next.
- `docs/ROADMAP.md`: known weaknesses and direction.
- `IDEAS.md`: loose ends and the idea backlog.
