# AI Dungeon Master

A role-separated narrative game platform. One rules engine ships:

- **Loner 3e** — the tag-based engine: one closed question to the Oracle, Chance d6 against Risk
  d6, six outcomes, a Twist Counter, and Harm against a pool of Luck. Loner 3e rules CC BY-SA
  Roberto Bisceglie, Zotiquest Games — <https://lonersrd.zotiquestgames.com>. docs/LONER-3E.md is
  the SRD extraction, and names every deviation this implementation takes.

## The engine shelf

Candidate engines are docs, not code: an exact SRD extraction per system under `docs/`, each
ending with a sketch of what its engine package would look like here. The rule for the shelf —
official, freely licensed, low mechanical overhead: a system the Directors can drive without a
rules lawyer. On it now:

- `docs/24XX.md` — 24XX SRD v1.4 (CC BY 4.0, Jason Tocci). Skill-die pools, roll-highest,
  disaster/setback/success. The natural second engine.
- `docs/CAIRN-2E.md` — Cairn 2e (CC BY-SA 4.0, Yochai Gal). HP, three stats, armour, damage
  dice; ~2× the code of loner3e, implemented only if that texture is wanted.

`docs/LONER-3E.md` is the same extraction for the shipped engine. An engine package appears
only when it is next to be played; a skeleton package is dead code.

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
src/aidm/engines/loner3e/ Loner 3e engine: tag sheets, the closed question, the outcome ladder
src/aidm/ui/              NiceGUI shell: renders state, submits decisions
characters/               shared character canon plus one overlay per supported engine
scenarios/                shared world canon plus one overlay per supported engine
tests/                    per-package suites: core, loner3e, probe, ui
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
