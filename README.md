# AI Dungeon Master

A role-separated narrative game platform with two first-party rules engines:

- **AIDM Story** — the default narrative-first, rules-light engine.
- **AIDM 5e** — the D&D 5e implementation, isolated in its own engine package.

```text
prompt → DIRECTOR → resolve + commit → NARRATOR → MAINTAINER → CREATOR → growth + commit
         Direction   typed facts          prose         Growth       Entity
```

The model proposes typed mechanics, the selected engine resolves them deterministically against a
draft, and core commits a fully revalidated state. Core owns each role's visible entities, while
the selected engine annotates those entities with one shared state presentation. The Narrator
receives no unrevealed canon; for visible entities it receives the same state as the other roles, with
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

## Layout

```text
src/aidm/kernel/          engine-neutral world, content, persistence, composition
src/aidm/workflow/        the turn loop, its agents, director tools, prompts
src/aidm/plugins/story/   Story state, rules, presentation, advancement
src/aidm/plugins/dnd5e/   5e mechanics, compiled profiles, SRD pack, advancement
src/aidm/ui/              NiceGUI composition root
scripts/srd/      one-shot importer narrowing an upstream 5e-database checkout
characters/       shared character canon plus one overlay per supported engine
scenarios/        shared world canon plus one overlay per supported engine
tests/            per-package suites: core, story, dnd5e, ui
```

One distribution. The import direction is enforced by `tests/core/test_package_boundary.py`: the
engines do not import each other or `aidm.ui`, and the kernel and workflow import neither the UI
nor NiceGUI. The shipped SRD pack is package data under `src/aidm/plugins/dnd5e/packs/`.

The **Trace** tab shows private Director mechanics, resolved facts, and the exact prompt received
by each role. The **State** tab shows the committed game state. **Advancement** delegates its
engine-specific decisions to a panel the engine ships.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `docs/ROADMAP.md`: known weaknesses and possible next work.
