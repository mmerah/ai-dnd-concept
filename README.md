# AI Dungeon Master

A role-separated narrative game platform. One rules engine ships:

- **AIDM Oracle** — the tag-based engine: one dramatic question, Chance d6 against Risk d6, six
  semantic outcomes. Its resolution is inspired by Loner 3e (Zotiquest Games, CC BY-SA 4.0);
  the terminology, the outcome ladder, and the code are original.

See PLAN.md for the phases.

```text
prompt → SCENE → RULES → resolve → hooks → NARRATOR → WORLDKEEPER → commit
      directive  one plan  engine code  facts fire   prose      new canon
```

The Scene Director decides what the turn is about; the Rules Director answers with one structured
turn plan — the single action resolved this turn, its fiction consequences keyed by outcome, and
unconditional effects. Engine code validates the plan against committed state, resolves it
deterministically on a draft (rolls, costs, intrinsic outcomes), committed Facts fire the
scenario's authored hooks, and core commits a fully revalidated state. An engine is ordinary typed
Python: its own strict mechanics model, and action models with their resolvers. Core owns the
fiction — entities, placement, relations, threads, traits — and persists the engine's mechanics as
one opaque payload it never reads. The Narrator receives no
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
scenario, rules engine, and compatible character. The game header always identifies the active
engine.

Run repository checks with:

```bash
uv run ruff check
uv run basedpyright
uv run pytest
```

## Layout

```text
src/aidm/state/           the deterministic machine: world, effects, plans, dice, trace
src/aidm/content/         authored scenarios and characters, saves and traces
src/aidm/engines/         the loader, plus one directory per engine
src/aidm/turn/            the turn loop, its agents, prompts, advancement
src/aidm/app/             composition root: launcher catalog, sessions, runtime
src/aidm/engines/oracle/  Oracle engine: tag sheets, the dramatic question, the outcome ladder
src/aidm/ui/              NiceGUI shell: renders state, submits decisions
characters/               shared character canon plus one overlay per supported engine
scenarios/                shared world canon plus one overlay per supported engine
tests/                    per-package suites: core, oracle, probe, ui
```

One distribution. The import direction — `state <- content <- engines <- turn <- app <- ui`, with
`aidm/config.py` a leaf every layer may read — is enforced by
`tests/core/test_package_boundary.py`: an engine does not import another or `aidm.ui`, and
nothing below `app` imports the UI or NiceGUI.

The **Trace** tab shows the Director's plan, resolved facts, and the exact prompt received
by each role. The **State** tab shows the committed game state. **Advancement** drafts a proposal
through an advisor role; the player reviews each change and its reason, then confirms.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `PLAN.md`: the phased plan for what is built next.
- `docs/ROADMAP.md`: known weaknesses and direction.
- `IDEAS.md`: loose ends and the idea backlog.
