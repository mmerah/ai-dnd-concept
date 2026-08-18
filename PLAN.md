# Plan

The phased plan for what is built next, in order. The Director-contract work, the 2026-08-17
drastic simplification (Cairn 2e deleted, the wire contract cut to `roll` + `effects`), and the
engine-true mechanics and the scenario creator all shipped (git history has the detail). The
2026-08-17 research pass (`docs/ADVENTURE-SOURCES-RESEARCH.md`, `docs/SYBYL-LEARNINGS.md`) was
adopted: Phase 2 (progressive world expansion), Phase 3 (the source system: PDF ingestion,
grounded expansion, fused authoring) and Phase 4 (scene illustrations) shipped; Phase 5 is the
player-facing UI (`docs/ui-mock/index.html` is its visual reference) and Phase 6 the two authoring
knobs the creator still lacks. Each phase carries enough detail to
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

## Phase 5 — Player-facing UI (~2–3 days)

Re-skin the game page from a debug surface into a play surface, per `docs/ui-mock/index.html`
(open it in a browser first; its README explains each view). No new dependencies, and domain logic
stays out of `src/aidm/ui/` — the UI renders view models built at the app boundary. Steps 1–4 add
no state field and move no persisted byte; step 5 does both, deliberately, and is the only reason
this phase bumps `SAVE_VERSION`.

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
   - Left: scene header (location name, brief, the Phase 4 image or its in-flight placeholder),
     then the chat, then the input row. Show the entities-here and known-exits from `PlayerScene`
     as compact rows under the header (`docs/ui-mock` "Here now" / "Exits" cards are the look to
     approximate, not pixel-match).
   - Right tabs become: `scene` (character mini + `sheet_view` pairs + threads), `journal`
     (`JournalView`), the advancement tab as today, and `dev` (the current trace + state panels,
     unchanged). Default tab: `scene`.
   - Role badges stay in the header; they double as the turn progress indicator.
4. Markdown journal export (`docs/SYBYL-LEARNINGS.md` item 1): a pure
   `journal_markdown(state) -> str` projection of the chronicle — prompts, narration, thread
   states — plus an export button on the journal tab writing `saves/<slug>.journal.md`. A
   projection only: nothing is ever read back from it.
5. **Speaker attribution, and the icons that pay for it.** `speaker_id` was deleted in the
   2026-08-17 simplification for want of a reader; the chat is that reader, so it comes back in
   its real form. This is a schema change on the one role that still answers in plain text, and it
   is the step to sequence first if the phase runs short.
   - Narrator output becomes `NativeOutput(Narration)` — `lines: tuple[Line, ...]`, each `Line` a
     `speaker_id: EntityId | None` (null is narration, not speech) and its `text`. An output
     validator refuses a `speaker_id` that is not a revealed entity of the `VisibleScene` the
     Narrator was given, with `ModelRetry`: the leak rule holds through the validator, not through
     trust. Live probe first (working rule 2) — small schema, the shape the worldkeeper already
     proves works.
   - `Exchange` stores `lines`; `narration` becomes a property joining their text, so prompts and
     the journal export read exactly what they read today. Persisted bytes move: bump
     `SAVE_VERSION` and regenerate the `save`/`state`/`turn` fixture families in the same commit.
   - Icons gain a third origin, `characters/<slug>/icons/<entity_id>.<ext>`, for the player and
     anything the character brought — the split rule of Phase 4 with the character dir added, so
     `authored_ids` becomes an origin lookup rather than one frozenset. The player's icon is
     generated on the same background task as the first illustration; the player stays out of the
     scene image itself (the picture is the room as it is looked at).
   - Chat rendering: an NPC line gets that entity's icon as its avatar, their name, and a bubble
     distinct from the player's; the player's line gets the character's own icon; a null-speaker
     line is the DM's, with one shipped placeholder avatar used by every game — a material icon,
     not a generated file. A speaker whose icon is missing falls back to a letter avatar, never to
     a blank.
6. Out of scope, deliberately: suggestion chips (nothing authors them), mid-game engine switching
   (mock-only presentation), the map view (the catalogue list is the same data), and the home page
   re-skin.

Done when: `uv run aidm` plays a turn narration-first with the rails populated from view models,
NPC dialogue arrives attributed and iconed, the leak test pins that no unrevealed name reaches a
player panel or a `speaker_id`, trace/state still work under dev, and the suite is green with only
the `SAVE_VERSION` fixtures moved.

## Phase 6 — Authoring controls: expansion policy and art style (~half a day)

Two knobs the creator cannot set today, both one field wide. Neither touches `GameState`, so no
`SAVE_VERSION` bump.

Both are arguments of the authoring call, never flags parsed in `create_scenario.py`: the CLI and
the scenario-creator page (deferred below) must offer the same two fields, and a knob that lives in
argument parsing has to be built twice.

1. `--expansion {closed,generative,grounded,extended}` writes `ScenarioWorld.expansion` instead of
   the hardcoded `grounded`, defaulting to `grounded` when a source document is given and
   `generative` when only a premise is. This retires PROGRESS's "`extended` is reached by editing
   one field in `world.json`".
2. `ScenarioWorld.art_style: str = ""` overrides `media.STYLE` when set — authored content, not
   state, which is why it lives on `ScenarioWorld` and not on `ScenarioMeta` (that one is copied
   into every save). `open_media` reads it; the creator's authoring schema carries it so a source
   document's own tone can pick the palette, and `--style` overrides what the model wrote.
3. Icons still generate on first play, on demand, into the scenario dir — the creator authors no
   art. A `scripts/bake_icons.py <slug>` that walks a scenario's non-location entities is the
   whole of "pre-bake", and is worth writing only when authoring a scenario for someone else.

## Deferred, with their trigger

- Scenario-creator page: after Phase 6, so the page has both knobs to offer on its first
  version. `src/aidm/ui/create.py` is character creation only today; the scenario creator has run
  from `scripts/create_scenario.py` since Phase 1. The page is that agent driven from a form —
  premise or uploaded document, expansion policy, art style — and its hard part is a long
  agentic run behind a busy surface, not the form.
- Sybyl player assistance ("What can I do?", "Ask the rules"): after Phase 5, because it wants
  `PlayerScene` and the engine vocabulary as its only inputs.
- Player-agency eval: when live eval gates come back (working rule 3).
- Provider/cost UX (connection checks, per-turn latency, token counts): shell polish after the
  play surface exists.
