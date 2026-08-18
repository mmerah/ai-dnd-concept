# Plan

The phased plan for what is built next, in order. The Director-contract work, the 2026-08-17
drastic simplification (Cairn 2e deleted, the wire contract cut to `roll` + `effects`), and the
engine-true mechanics and the scenario creator all shipped (git history has the detail). Phase 2
(progressive world expansion), Phase 3 (the source system: PDF ingestion, grounded expansion,
fused authoring), Phase 4 (scene illustrations) and Phase 5 (the player-facing UI) shipped; Phase 6
turns the scenario creator into a page. Each phase carries enough detail to implement without prior
context; only the next unshipped phase needs full resolution. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted. `tests/core/test_golden_state.py` pins `FIXTURE_SAVE_VERSION` —
   bump both or the suite catches you.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 6 — The scenario creator becomes a page (~2-3 days)

Authoring stops being a script. Today `scripts/create_scenario.py <slug> "<premise>"|<file>` runs
`app.scenario_creator` end to end and writes the scenario the moment the agent's `finish` tool
validates. The page replaces both halves: the run is driven from a form, and **the agent's `finish`
no longer ends the authoring — the user's does.** `docs/ui-mock/index.html`'s Create view
(Source -> World draft -> Engines -> Review) is the visual reference; approximate it, do not
pixel-match.

The hard part is not the form. It is that a draft must outlive one agent run, so the user can read
the whole scenario back and then ask for changes in words.

1. `src/aidm/ui/create.py` -> `character_create.py`, `creation_page` -> `character_page`. It has
   only ever been character creation, and a file named `create.py` beside a scenario creator is a
   trap. Pure rename, no behaviour change, one commit of its own.
2. **The two knobs, as arguments of the authoring call and never as flags a surface parses.** A
   knob that lives in argument parsing has to be built twice.
   - `ScenarioWorld.expansion` is written from the form instead of the hardcoded `grounded`,
     defaulting to `grounded` when a document is given and `generative` when only a premise is.
     This retires PROGRESS's "`extended` is reached by editing one field in `world.json`".
   - `ScenarioWorld.art_style: str = ""` overrides `media.STYLE` when set — authored content, not
     state, which is why it lives on `ScenarioWorld` and not on `ScenarioMeta` (that one is copied
     into every save). `open_media` reads it; the authoring schema carries it so a document's own
     tone can pick the palette, and the form's value overrides what the model wrote.
   - **A policy that needs a document says so in the form.** `grounded` and `extended` are refused
     without one, and the page asks for the file rather than failing after a long run — the same
     refusal `open_source` already makes at play time, moved to where the choice is made.
3. **An authoring session, not a run.** The `WorldDraft` and the agent's message history live in
   one object the page holds, exactly as `GameSession` holds a game. `finish` ends the *model's*
   turn and hands back a validated draft; the session stays open. The user then sends another
   instruction — "give the smith a reason to lie", "the vault needs a second way in" — and the same
   agent continues against the same draft, with `write(ScenarioPatch)` upserting by id as it
   already does. This is the capability the existing agent was built for and nothing has used:
   PROGRESS's Phase 1 entry already notes that editing a scenario conversationally is the same
   agent with a draft loaded from disk.
4. **The page.** A form (slug, premise or uploaded document, expansion policy, art style), the
   busy surface for a long agentic run, and a complete read-back of the draft — every location,
   actor, item, relation, thread and hook, not a summary — beside the chat box that revises it.
   `WorldDraft.pretty` is the read-back's starting point. Nothing is written to disk while the
   session is open.
5. **Only the user's finish writes.** It authors the overlay for every shipped engine, then
   `write_scenario` — which already refuses to land anything unless every engine validates. A
   scenario the user never finishes leaves no directory behind.
6. `scripts/create_scenario.py` and `scenario_creator.main()` are deleted with the page, and so is
   `OPENING_FLAG`. Whatever the CLI offered that the page does not — the `--opening` brief — is
   either a control on the form or deleted with the flag; a capability with no surface is not
   kept.
7. Icons still generate on first play, on demand, into the scenario dir: the creator authors no
   art. A `scripts/bake_icons.py <slug>` walking a scenario's non-location entities is the whole of
   "pre-bake", and is worth writing only when authoring a scenario for someone else.

Done when: a scenario is authored, read back in full, revised by conversation and written to
`scenarios/<slug>/` without leaving the browser, under a policy and an art style the form chose;
and no scenario-authoring entry point exists outside the app.

## Deferred, with their trigger

- Player-agency eval: when live eval gates come back (working rule 3).
- Provider/cost UX (connection checks, per-turn latency, token counts): shell polish after the
  play surface exists.
