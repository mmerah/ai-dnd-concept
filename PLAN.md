# Plan

The phased plan for what is built next, in order. Rewritten 2026-08-12 after the reorientation
decision (see CONCEPT.md and DECISION.md): the D&D 5e engine is deleted, a small tag-based
Oracle engine replaces it as the mechanical engine, and the feature phases (scenario creator,
media) proceed against the settled engine boundary. Each phase carries enough detail to
implement without prior context; only the next unshipped phase needs full resolution.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 1 — Delete the D&D 5e engine (~½–1 day)

The engine boundary makes this cheap: `tests/core/test_package_boundary.py` proves nothing in
`state/`, `turn/`, `app/`, or `ui/` names dnd5e, and `loader.ENGINE_MODULES` is the only
registry. The dnd5e work is committed and tagged; git history is the archive.

1. Delete `src/aidm/engines/dnd5e/` (2,348 lines Python + 41.5k lines pack JSON), `scripts/srd/`
   (2,604-line importer), `tests/dnd5e/`, and the dnd5e line in `ENGINE_MODULES`
   (`src/aidm/engines/loader.py`).
2. Delete `state/packs.py` (298 lines) — its only consumer was dnd5e. `loader.py` imports
   `ContentRef` (for `AdvancementOffer.granted/options`) and `ENCODING` from it: replace
   `ContentRef` with a plain frozen `(collection, id, label)`-style ref or plain strings —
   whichever the story engine's advancement actually needs — and move `ENCODING` to
   `state/base.py`.
3. Delete dnd5e content: `characters/*/dnd5e.json`, `scenarios/*/dnd5e.json`, any dnd5e eval
   cases under `scripts/evals/`. Sweep docs for dnd5e references; CONCEPT.md and DECISION.md
   already record the reorientation.
4. Bump `SAVE_VERSION`, regenerate golden fixtures, and read the diff: only dnd5e-family
   fixtures should disappear and only `save_version` bytes should move elsewhere. The story
   engine and the probe engine (`tests/probe/`) still pass untouched — that is the proof the
   deletion stayed inside the boundary.

Done when: the suite is green with no dnd5e artifact in the tree, and `rg -i dnd5e src tests`
finds nothing outside git history.

## Phase 2 — Oracle engine (~3–5 days, 600–900 lines)

A first-party tag-based engine in the spirit of Loner 3e / 24XX (see ORIGINAL-GPT-RESEARCH.md
and CONCEPT.md §12) with original terminology — no SRD text is copied. It is an ordinary engine
package: `src/aidm/engines/oracle/` plus one `ENGINE_MODULES` line, structured like
`engines/story/` (554 lines) and sized like it. The story engine stays; Oracle is the engine
with mechanical teeth.

1. **Mechanics blob** (`mechanics.py`): `concept: str`, `edges: tuple[str, ...]` (2–3 capability
   tags), `burdens: tuple[str, ...]` (1+ weakness tags), `gear: tuple[str, ...]` (signature
   items), `fortune` as a `Counter` (`engines/counters.py`, max 6), `twist` counter, and
   `conditions: tuple[str, ...]` for temporary tags. NPCs and significant objects use the same
   shape — "everything is a character".
2. **Resolution** (`resolve.py`): one action type, a closed dramatic question with
   `advantage | neutral | disadvantage` position. The plan names which existing tags justify the
   position (`check_plan` refuses tags not on the sheet or in the scene — the model cannot
   invent a bonus); positive and negative cancel; never more than two dice a side. Chance d6 vs
   Risk d6 → six semantic outcomes (`strong-yes / yes / yes-but / no-but / no / no-and`), tie →
   `yes-but` + twist tick; every third twist tick emits a twist fact for the Director. Fortune
   spend = one reroll, resolver-side. All rolls in `resolve_action` against the draft, model
   never rolls.
3. **Creation** (`create.py`): via the existing `state/creation.py` steps — concept, 2 edges,
   1 burden, 2 gear, all free-text with AI-suggested options; no pack data needed.
4. **Advancement** (`advance.py`): milestone-driven, small — a new edge, a new gear tag, or
   clearing a burden; `offered`/`advance`/`violation` against explicit caps (max edges/gear).
5. **Prompts + fixtures**: `director.md`, `advancement.md`, `examples.json`; one live probe of
   the plan schema (working rule 2) before cutting golden fixtures; tests mirror
   `tests/story/` plus resolver-table tests (the 6-outcome mapping is pure and fully
   enumerable).

Done when: kael has an `oracle.json` binding, whispering-vault plays a full turn under Oracle
with a contested action resolving through the dice table, and the engine passes the same shape
of golden/fixture suite the story engine does.

## Phase 3 — Scenario creator (~3–4 days)

Premise → a complete scenario in the exact on-disk format, authored by a strong model at
authoring time. This is a script, not the app: agentic workflows are fine outside the turn
loop, where speed and small-model reliability do not constrain the design.

1. `scripts/create_scenario.py <slug> "<premise>"`. A pydantic-ai agent whose output type **is**
   `ScenarioWorld` (`NativeOutput`) — the strictest spec of the shared format already exists and
   is the validator. Role config key `creator` (set a strong model in `.env`:
   `ROLES__CREATOR__MODEL=...`). Give it one read-only tool returning whispering-vault's
   `world.json` as the worked example, and put the authoring bar in the instructions: 4+
   locations connected by relations with at least one hidden and one `locked` way, 2+ NPCs with
   at least one unrevealed, one secret item, at least one thread with hooks that advance it on
   `entity_discovered` facts, hook `note`s that steer the Director, and `detail.hook` on every
   entity worth one.
2. Validation loop, in the script: `ScenarioWorld` validates structurally on output (the agent
   retries on `ValidationError` for free). Then validate the world alone — a `Scenario` per
   engine with an empty/default overlay, `begin_game` with the shipped `kael`, and the engine's
   normal mechanics validation. Any `ValueError` goes back to the agent as a retry message, max
   3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per engine, output that engine's strict authored-overlay model,
   prompted with the generated world and engine-provided authoring guidance/defaults. Re-run
   step 2's loop with each generated overlay in place — the overlay is what `begin_game`
   exercises beyond shared structure.
4. Files land in `scenarios/<slug>/` only after every engine validates. The script prints a
   summary (entities, relations, threads, hooks per engine) and the author reviews the diff
   before committing — generated content merges by the same review as hand-written content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under both engines. Quality beyond
validity is judged by playing it, not asserted by the script. PDF/notes ingestion is a later
input mode for the same script, not a separate system.

## Phase 4 — Media: scene illustrations (~2–3 days)

Presentation only, outside mechanical truth: the game must be indistinguishable with media
disabled, and a failed generation must cost nothing but a log line.

1. `MediaConfig` on `Settings`: `enabled: bool = False`, `provider: ProviderName = "openrouter"`,
   `model: str` (an image-capable model id). `src/aidm/app/media.py`:
   `illustration_request(state: GameState, narration: str) -> str` builds the image prompt
   deterministically — location name and brief, the `here` entities' briefs, the narration — **no
   model call decides whether to illustrate**; a Producer role is not built until a deterministic
   builder proves insufficient. `async generate(prompt, config) -> bytes | None` calls the image
   API and returns None on any failure (logged, never notified).
2. Wiring, at the boundary: after the commit in `GameSession.submit`, when media is enabled,
   schedule generation as a background asyncio task writing
   `saves/<slug>.media/turn-<n>.png`. The turn returns without waiting. `restart()` discards the
   media directory alongside the save.
3. UI: the chat panel shows the image above its exchange when the file exists; refresh on next
   submit (simplest) picks up late arrivals, a `ui.timer` only if that feels bad in practice. No
   gallery, no regeneration button.
4. Tests: the request builder is pure — one test on its output for a known state; the generate
   path is not tested live (network rule). Voice, portraits, and ambient audio are later phases
   of the same shape, none specced until wanted.

Done when: with media enabled a turn grows an illustration within seconds after the narration,
and with it disabled (the default) nothing in state, saves, prompts, or tests differs.

# Considered and decided without a phase (updated 2026-08-12)

- **Rebuilding World Core per CONCEPT.md phases 0–1**: rejected. The boundary test proves engine
  concepts never leaked into core; `state/world.py` already is the neutral world layer. CONCEPT's
  ECS components, event-sourced projections, and `EngineAdapter` interface are not adopted — the
  existing `Engine` ABC is smaller and proven by three implementations.
- **Keeping dnd5e as a dormant engine**: rejected. 46k lines of artifact with a broken
  advancement backlog is not worth the tree weight; git history keeps it, and CONCEPT.md §27
  documents the containment strategy if it ever returns as a late-stage boundary stress test.
- **A content-pack system for Oracle**: rejected. Oracle's tags are free text; `state/packs.py`
  leaves with its only consumer. Reintroduce packs only when a second engine needs shared
  structured content.
- **Fact as the domain event stream**: already the architecture; memories and thread judgment
  build on it without an event bus.
- **FrozenMap removal**: rejected. Frozen Pydantic models do not deep-freeze contained dicts;
  the wrapper enforces the repository's frozen-value invariant.
- **Plain-text Director fallback removal**: rejected. It is a tested provider workaround, not an
  unused second design.
