# Plan

The phased plan for what is built next, in order. Rewritten 2026-08-13 after the recentering
decision: the project ships official, freely licensed, LLM-as-GM-friendly tabletop engines
only. The first-party story engine is deleted; the oracle engine is renamed loner3e and made
compliant with the Loner 3e SRD (CC BY-SA 4.0), with every deviation named in
docs/LONER-3E.md; 24XX and Cairn 2e sit on a docs-only shelf until one is wanted. Each phase
carries enough detail to implement without prior context; only the next unshipped phase needs
full resolution. Shipped phases move to PROGRESS.md.

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

## Phase 1 — loner3e: rename and close the compliance gap (~1–2 days)

The oracle engine already matches the Loner 3e SRD's core loop: Chance d6 vs Risk d6, the six
outcomes with the both-low/both-high and/but rules, tie → twist tick with a twist due at 3,
harm 3/2/1 against a Luck pool of 6, advantage/disadvantage as one extra die on one side. What
remains is vocabulary, the random tables, and the edges of the rules. Final step resolution
waits on docs/LONER-3E.md (the exact SRD text, CC BY-SA 4.0, attributed); the shape is:

1. **Rename**: package `engines/oracle/` → `engines/loner3e/`, engine id `loner3e`, badge, and
   SRD vocabulary throughout sheet, prompts, and fixtures — `edges` → `skills`, `burdens` →
   `frailties`; `concept`, `gear`, `luck`, `twist` already match. Content follows:
   `characters/kael/oracle.json` → `loner3e.json`, same for the scenario overlay. Bump
   `SAVE_VERSION`, regenerate fixtures, read the diff. CC BY-SA 4.0 attribution to Roberto
   Bisceglie / Zotiquest Games in README.md and the engine's director.md.
2. **Roll the SRD's tables resolver-side, Director interprets**: when a twist comes due, roll
   the 2d6 twist table (subject × action) in `resolve.py` and put the rolled pairing in the
   note that `pending_notes` already carries to the next turn's directors — the LLM writes the
   fiction, never picks the row. Tables are frozen Python constants in the engine package, not
   content packs (see below).
3. **Close rule gaps against docs/LONER-3E.md**, each either implemented or added to that
   doc's Deviations section with a reason. Already SRD-exact, verified against the extraction:
   the outcome grid with both-≤3/both-≥4 modifiers, advantage as one extra die of that color
   keep-highest capped at two, net tag cancellation, harm 3/2/1, and conflict exchanges never
   ticking the Twist Counter ("The Twist Counter does NOT apply to Harm & Luck"). The real
   gaps: Luck "resets after conflicts" with no spend rule (the SRD has none — decide whether
   the reset is resolver-side at conflict end or stays a Director `counter-change`);
   advancement options (SRD growth also adds a frailty or modifies a trait; today's milestone
   buys only edge/gear/clear-burden); Goal/Motive/Nemesis (map to threads and entities rather
   than sheet fields); non-living characters (SRD gives objects concept/skills/frailties/Luck;
   sheets are actors-only today); the optional next-scene mood roll (Scene Director judgment
   replaces it). Twists landing one turn late — the note channel — is a standing deviation:
   the Narrator only writes from committed facts.
4. **Deviations doc**: docs/LONER-3E.md ends with the named list of every remaining
   divergence — the standing contract for what "compliant" means here.

Done when: kael plays a full turn under `loner3e`, the suite is green on regenerated
fixtures, and every divergence from the SRD is either closed or named in docs/LONER-3E.md.

## Phase 2 — The engine shelf: docs-only stubs (~½ day)

Candidate engines are docs, not code: an exact SRD extraction per engine under `docs/`, each
ending with a short "what its engine package would look like" note (~10 lines: sheet shape,
plan/action types, resolver, which of its tables the Directors replace or roll). No skeleton
packages — an engine package appears only when it is next to be played.

1. `docs/24XX.md` — 24XX SRD (CC BY 4.0, Jason Tocci). The natural second engine: skill-die
   pools, one roll-highest resolution, disaster/setback/success.
2. `docs/CAIRN-2E.md` — Cairn 2e SRD (Yochai Gal). More mechanical (HP, three stats, armour,
   damage dice); implement only if its shape is wanted.
3. README.md names the shelf and the rule: official, freely licensed, low mechanical
   overhead — an engine the Directors can drive without a rules lawyer.

Done when: both docs exist with license attribution and the README names the shelf.

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
   shipped engine with an empty/default overlay, `begin_game` with the shipped `kael`, and the
   engine's normal mechanics validation. Any `ValueError` goes back to the agent as a retry
   message, max 3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per shipped engine, output that engine's strict
   authored-overlay model, prompted with the generated world and engine-provided authoring
   guidance/defaults. Re-run step 2's loop with each generated overlay in place — the overlay
   is what `begin_game` exercises beyond shared structure.
4. Files land in `scenarios/<slug>/` only after every shipped engine validates. The script
   prints a summary (entities, relations, threads, hooks per engine) and the author reviews the
   diff before committing — generated content merges by the same review as hand-written
   content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under every shipped engine. Quality beyond
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

# Considered and decided without a phase (updated 2026-08-13)

- **Keeping the story engine**: rejected. The recentering rule is official, freely licensed
  systems only; a first-party ruleset competes with them for maintenance and eval attention
  while nobody would choose it. Its only structural value — proving the engine boundary with a
  second implementation — is already carried by the probe engine (`tests/probe/`).
- **Loner's tables as a content pack**: rejected. The twist table is a 6×6 of short strings;
  a frozen constant next to `resolve.py` is typed and needs no loader. Packs return only when
  a scenario needs to override an engine's tables, which nothing asks for.
- **Runnable stubs for 24XX / Cairn 2e**: rejected in favour of docs-only SRD extractions
  (Phase 3). A skeleton package is dead code with a maintenance cost; the `Engine` ABC stays
  honest through loner3e plus the probe engine.

- **Rebuilding World Core as its own ECS layer**: rejected. The boundary test proves engine
  concepts never leaked into core; `state/world.py` already is the neutral world layer. ECS
  components, event-sourced projections, and an `EngineAdapter` interface are not adopted — the
  existing `Engine` ABC is smaller and proven by three implementations.
- **Keeping dnd5e as a dormant engine**: rejected. 46k lines of artifact with a broken
  advancement backlog is not worth the tree weight; git history keeps it.
- **A content-pack system for Oracle**: rejected. Oracle's tags are free text; `state/packs.py`
  leaves with its only consumer. Reintroduce packs only when a second engine needs shared
  structured content.
- **Fact as the domain event stream**: already the architecture; memories and thread judgment
  build on it without an event bus.
- **FrozenMap removal**: rejected. Frozen Pydantic models do not deep-freeze contained dicts;
  the wrapper enforces the repository's frozen-value invariant.
- **Plain-text Director fallback removal**: rejected. It is a tested provider workaround, not an
  unused second design.
