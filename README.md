# AI Dungeon Master

A role-separated narrative game platform with two first-party rules engines:

- **AIDM Story** — the default narrative-first, rules-light engine.
- **AIDM 5e** — the D&D 5e implementation, isolated in its own engine package.

```text
prompt → DIRECTOR → resolve → NARRATOR → MAINTAINER → CREATOR → growth + commit
          one plan   engine code  prose      Growth      Entity
```

The Director answers with one structured turn plan — the single action resolved this turn, its
fiction consequences keyed by outcome, and unconditional effects. Engine code validates the plan
against committed state, resolves it deterministically on a draft (rolls, costs, intrinsic
outcomes), and core commits a fully revalidated state. An engine is data plus typed actions and
their resolvers: a sheet template, lenient content records, and the rules procedure in code. The
Narrator receives no unrevealed canon; for visible entities it receives the same state as the
other roles, with instructions to translate mechanics into fiction rather than recite stat blocks.

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

## Layout

```text
src/aidm/core/            engine-neutral world, sheet, effects, plans, content, persistence
src/aidm/workflow/        the turn loop, its agents, prompts, session composition root
src/aidm/engines/story/   Story engine: spec, director procedure, shim
src/aidm/engines/dnd5e/   5e engine: spec, director procedure, SRD pack, shim
src/aidm/ui/              NiceGUI shell: renders state, submits decisions
scripts/srd/      one-shot importer projecting an upstream 5e-database checkout into the pack
scripts/evals/    live-model eval harness, run manually and never from pytest
characters/       shared character canon plus one overlay per supported engine
scenarios/        shared world canon plus one overlay per supported engine
tests/            per-package suites: core, story, dnd5e, ui
```

One distribution. The import direction is enforced by `tests/core/test_package_boundary.py`: the
engines do not import each other or `aidm.ui`, and core and workflow import neither the UI
nor NiceGUI. The shipped SRD pack is package data under `src/aidm/engines/dnd5e/packs/`.

The **Trace** tab shows the Director's plan, resolved facts, and the exact prompt received
by each role. The **State** tab shows the committed game state. **Advancement** drafts a proposal
through an advisor role; the player reviews each change and its reason, then confirms.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `docs/ROADMAP.md`: known weaknesses and possible next work.
- `IDEAS.md`: loose ends and the idea backlog.
