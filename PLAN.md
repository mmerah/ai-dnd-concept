# Plan

The phased plan for what is built next, in order. The Director-contract work, the 2026-08-17
drastic simplification (Cairn 2e deleted, the wire contract cut to `roll` + `effects`), and the
engine-true mechanics and the scenario creator all shipped (git history has the detail). The
2026-08-17 research pass (`docs/ADVENTURE-SOURCES-RESEARCH.md`, `docs/SYBYL-LEARNINGS.md`) was
adopted: Phase 2 is progressive world expansion, Phase 3 the source system (PDF ingestion, grounded
expansion, fused authoring), Phase 4 media, Phase 5 the player-facing UI;
`docs/ui-mock/index.html` is the visual reference for 4 and 5. Each phase carries enough detail to
implement without prior context; only the next unshipped phase needs full resolution. Shipped
phases move to PROGRESS.md.

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

## Phase 2 — Progressive world expansion (~5–7 days)

From `docs/ADVENTURE-SOURCES-RESEARCH.md`: a fully authored scenario stops being the unit required
to start a game. The runtime plays any valid adventure state —
`Adventure = GameState + CanonSource + ExpansionPolicy` — and canon can materialize mid-turn,
before the Director finishes its plan, through an Expander behind a Director tool. The Worldkeeper
keeps only post-narration maintenance. A curated scenario with `closed` policy must play exactly
as today.

1. **Strict topology.** In `_require_open_way` (`src/aidm/state/apply.py:56`), delete the
   `if not exits: return` wildcard: movement always follows explicit `connected` relations. In
   `WorldState._check_relation` (`src/aidm/state/world.py`), refuse a directed `connected`
   relation (shipped scenarios already write `directed: false`; play-created ones are already
   undirected). Worldkeeper locations stop stranding: in `apply_report`
   (`src/aidm/turn/pipeline.py`), a location `Creation` also writes an undirected, known
   `connected` relation to the location its `location` field names, else to the player's
   location — and that field's description (`src/aidm/state/turn.py`, prompt text) is updated to
   say so. Tests: a move with no matching relation is refused even from an exit-less location; a
   Worldkeeper-created location arrives connected.
2. **The Adventure triple.** New `src/aidm/content/sources.py`:
   `ExpansionPolicy = Literal["closed", "grounded", "generative"]` and a `CanonSource` protocol —
   `context() -> str`, what may exist beyond the materialized state. `ScenarioWorld` gains
   `expansion: ExpansionPolicy = "closed"`, so `world.json` carries the policy and a curated
   world is not diluted unless its author says so. `PremiseSource` is the first implementation:
   the scenario dir's `source.md` when present, else `meta.premise` (Phase 3 adds the
   record-backed source; `closed` needs none). The policy loads with `world.json`; the source is
   built beside the scenario in `Runtime._open` (`src/aidm/app/session.py`, the composition
   root), not stored on a pydantic model. `GameState` is untouched: a save resumes under its
   scenario's policy and source, and a restart replays the same opening, never regenerating it.
3. **Expander stage behind `expand_world`.** Add `"expander"` to the `Role` Literal and
   `ROLE_DEFAULTS` (`src/aidm/config.py`). New `src/aidm/turn/expansion.py`: `ExpansionPatch`
   (`Frozen`: entities, relations, threads, hooks — add-only, and a small schema) and an Expander
   `Stage` prompted with the turn draft's catalogue (it may see unrevealed canon; it never
   narrates), the `CanonSource` context, and the Director's request; output `NativeOutput`,
   live-probed before fixture work (working rule 2). `build_stages` grows a `Scenario` argument;
   when the policy is not `closed`, `director_stage` appends a `FunctionToolset` with
   `expand_world(kind, anchor_id, need)` — a closed game's Director agent stays byte-identical to
   today. The tool runs the Expander, then applies the patch via `transact`
   (`src/aidm/engines/transact.py` — the one mutation sequence: hooks fire, created actors are
   seeded) with a resolver that refuses any id the draft already holds and emits only
   `narrator=None` facts; everything materializes `known=False`, so nothing reaches the Narrator
   until the Director's own `reveal`/`move` effects establish it. The tool returns the created
   ids. Plumbing this needs two `run_turn` changes: the first Director call receives the turn
   draft (byte-identical to the committed state at that point), and `PlanContext` grows the
   turn's `rng` plus a mutable list the tool appends its facts and `StepTrace` to, which
   `run_turn` folds into the turn. At most 2 expansions per turn; past the cap, or on an Expander
   failure, the tool raises `ModelRetry` telling the Director to plan with what exists. A later
   turn failure still discards the whole draft.
4. **Premise-start.** Starting a game requires a premise, not a finished world:
   `create_scenario.py <slug> "<premise>" --opening` authors only an opening slice — the starting
   location, the two or three entities the first scene needs, one thread — by passing an opening
   bar into `playability` where `_bar_unmet` is today, then writes a real scenario dir with
   `"expansion": "generative"` in `world.json` and the verbatim premise as `source.md`
   (`write_scenario` grows an optional source argument). Play, saves, and restart treat it like
   any scenario. The full bar stays for dense `closed` scenarios.
5. **Vertical slice test and goldens.** With `FunctionModel` stubs for Director and Expander: the
   player travels to an unmaterialized frontier; `expand_world` adds one location and its
   connection; the Director reveals the route and moves the player; narrator evidence names no
   materialized-but-unrevealed canon; the commit is atomic and a failing Expander discards
   nothing but the tool call. No persisted save byte should move — policy and source are
   content-side with defaults — but working rule 1 applies in full if one does.

Done when: a game started from a bare premise plays turns in which travel beyond the frontier
expands the world through the tool; a curated `closed` scenario plays exactly as today with an
unchanged Director surface; the suite is green.

## Phase 3 — Sources: PDF ingestion, grounded expansion, fused authoring (~3–5 days)

The second `CanonSource`: a real document. One ingestion system feeds both scenario creation and
runtime expansion — no separate "PDF scenario creator".

1. **Ingestor.** PDF, Markdown, or plain text → immutable normalized `SourceRecord`s (id, text,
   page provenance, `visibility: player | private`) in `src/aidm/content/sources.py`, written as
   `sources.json` in the scenario dir; `RecordSource` joins `PremiseSource` as the second
   `CanonSource`, growing the protocol with `search(query) -> tuple[SourceRecord, ...]` — plain
   text search, a real choice, not a stub; a vector index is a separate decision if search proves
   insufficient. Extraction is deterministic; tests run on a small fixture document, no network.
   The PDF text dependency is chosen here (a pypdf-class library, nothing heavier).
2. **Fused authoring.** `create_scenario` accepts a source file path in place of a premise: it is
   ingested first, and `authoring_toolset` (`src/aidm/app/scenario_creator.py`) grows a read-only
   `search_source` tool over the records. Everything still passes the strict authored-content
   models and engine validation before any file is written (absorbs `docs/SYBYL-LEARNINGS.md`
   item 3).
3. **Grounded expansion.** Policy `grounded`: the Expander gains the same `search_source` tool
   and its patch names the record ids it drew from, refused when they do not exist.
4. **The leak rule extends to sources.** Raw source text reaches only the authoring agent and the
   Expander; the Narrator's input type still has no field it could travel through.

Done when: a shipped fixture document ingests to records, a scenario is created from a PDF alone,
and a `grounded` game expands only with canon that cites its records.

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
3. UI: the play page shows the newest existing `turn-<n>.png` as scene-header art above the
   narration (the placement the ui-mock settled on), not inline per exchange; refresh on next
   submit (simplest) picks up late arrivals, a `ui.timer` only if that feels bad in practice. No
   gallery, no regeneration button.
4. Tests: the request builder is pure — one test on its output for a known state; the generate
   path is not tested live (network rule). Voice, portraits, and ambient audio are later phases
   of the same shape, none specced until wanted.

Done when: with media enabled a turn grows an illustration within seconds after the narration,
and with it disabled (the default) nothing in state, saves, prompts, or tests differs.

## Phase 5 — Player-facing UI (~2–3 days)

Re-skin the game page from a debug surface into a play surface, per `docs/ui-mock/index.html`
(open it in a browser first; its README explains each view). This phase renders existing state
only: no new state fields, no persisted-byte change (no `SAVE_VERSION` bump), no model calls, no
new dependencies. Domain logic stays out of `src/aidm/ui/` — the UI renders view models built at
the app boundary.

**The leak rule, the one hard constraint:** a player-facing surface may only receive data through
a type that has no field a leak could travel through — the same rule the Narrator already obeys.
`VisibleScene` (`src/aidm/turn/scene.py`) is that type for the scene: it strips unrevealed
entities, unknown exits, and `detail.hook` by construction. Reuse it; never hand raw `GameState`,
`Hook`s, `pending_notes`, or thread `note`s (Director steering text) to a player panel. Trace and
raw state stay available, but only inside the explicitly-labelled dev tab.

1. Player view models in a new `src/aidm/app/views.py`, all frozen (`Frozen` from
   `aidm.state.base`) with pure builders taking `GameState`:
   - `PlayerScene`: wraps `VisibleScene.of(SceneSnapshot.of(state))` plus the location's `brief`
     and exit lock markers (`Exit.locked` is already on the scene's exits).
   - `JournalView`: chronicle from `state.history` (each `Exchange` is already player-safe),
     thread cards from `state.world.threads` showing `title`, `status`, `stage`, and the clock as
     "n / max" — not `note` — and memories from `state.world.memories` whose `owner` is `None` or
     names an entity with `known=True` (an authored memory can belong to someone the player has
     not met).
   Tests (`tests/` mirrors the package layout): build a small `WorldState` with one unrevealed
   entity, one unknown exit, and one hidden-owner memory; assert none of them appear in either
   view. This test is the leak rule's regression net — keep it strict.
2. Engine-owned sheet summary: add an abstract `sheet_view(self, state: GameState) ->
   tuple[tuple[str, str], ...]` to `Engine` (`src/aidm/engines/loader.py`) returning ordered
   (label, value) pairs for the player's sheet — e.g. loner3e: Concept / Skills / Frailty / Luck
   "4 / 6"; twentyfourxx: Specialty / Origin / Skills "Stealth d10" / Credits. Each engine reads
   its own mechanics via `state.mechanics_as(...)` exactly as its rules code does. Engines return
   data; NiceGUI stays out of `src/aidm/engines/`. One test per engine on a begun game's state.
3. Game page restructure (`src/aidm/ui/app.py` + `panels.py`), keeping the existing splitter,
   `GameView` refresh pattern, and busy handling:
   - Left: scene header (location name, brief, the Phase 4 image when present), then the chat,
     then the input row. Show the entities-here and known-exits from `PlayerScene` as compact
     rows under the header (`docs/ui-mock` "Here now" / "Exits" cards are the look to approximate,
     not pixel-match).
   - Right tabs become: `scene` (character mini + `sheet_view` pairs + threads), `journal`
     (`JournalView`), the advancement tab as today, and `dev` (the current trace + state panels,
     unchanged). Default tab: `scene`.
   - Role badges stay in the header; they double as the turn progress indicator.
4. Markdown journal export (`docs/SYBYL-LEARNINGS.md` item 1): a pure
   `journal_markdown(state) -> str` projection of the chronicle — prompts, narration, thread
   states — plus an export button on the journal tab writing `saves/<slug>.journal.md`. A
   projection only: nothing is ever read back from it.
5. Out of scope, deliberately: dialogue speaker attribution (needs structured Narrator output —
   `speaker_id` was deleted in the 2026-08-17 simplification; reintroducing it is a schema change
   with a live-probe cost, not polish), suggestion chips (nothing authors them), mid-game engine
   switching (mock-only presentation), the map view (the catalogue list is the same data), home
   page re-skin, and portraits/entity icons (later media phases).

Done when: `uv run aidm` plays a turn narration-first with the rails populated from view models,
the leak test pins that no unrevealed name can reach a player panel, trace/state still work under
dev, and the suite is green with no fixture movement.

## Deferred, with their trigger

- Sybyl player assistance ("What can I do?", "Ask the rules"): after Phase 5, because it wants
  `PlayerScene` and the engine vocabulary as its only inputs.
- Player-agency eval: when live eval gates come back (working rule 3).
- Provider/cost UX (connection checks, per-turn latency, token counts): shell polish after the
  play surface exists.
