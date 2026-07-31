# AI Dungeon Master

A role-separated narrative game platform with two first-party rules engines:

- **AIDM Story** — the default narrative-first, rules-light engine.
- **AIDM 5e** — the D&D 5e implementation, isolated in its own rules package.

```text
prompt → DIRECTOR → resolve → NARRATOR → MAINTAINER → CREATOR → commit
         Direction   Events    prose      Growth       Entity
```

The model proposes typed mechanics, the selected engine resolves them deterministically, and the
core reducer is the only state commit path. Core owns each role's visible entities, while the
selected engine annotates those entities with one shared state presentation. The Narrator receives
no unrevealed canon; for visible entities it receives the same state as the other roles, with
instructions to translate mechanics into fiction rather than recite stat blocks.

## Run

From the repository root:

```bash
uv sync
uv run aidm
```

The app opens at <http://localhost:8080>. Configure
`PROVIDERS__OPENROUTER__API_KEY` in `.env`. The home page lists saves and lets you choose a
scenario and any character compatible with its engine. Story and 5e are both included. The game
header always identifies the active engine and exact rules version.

Run repository checks with:

```bash
uv run ruff check
uv run basedpyright
uv run pytest
```

## Layout

```text
src/aidm/         engine-neutral state, reducer, pipeline, application, persistence
src/aidm_story/   Story definitions, rules, events, presentation, advancement
src/aidm_5e/      5e adapter, legacy mechanics, SRD data, advancement
src/aidm_ui/      NiceGUI composition root and engine-specific UI adapters
scripts/srd/      one-shot importer narrowing an upstream 5e-database checkout
characters/       explicit engine-selected character definitions
scenarios/        explicit engine-selected scenario definitions
tests/            per-package suites: core, story, dnd5e, ui
```

One distribution. The import direction is enforced by `tests/core/test_package_boundary.py`: the
core imports neither rules package nor NiceGUI. The shipped SRD pack is package data under
`src/aidm_5e/data/`.

The **Trace** tab shows private Director mechanics, resolved events, and the exact prompt received
by each role. The **State** tab shows the committed game state. **Advancement** delegates its
engine-specific decisions through a UI-owned adapter.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `docs/ROADMAP.md`: known weaknesses and possible next work.
