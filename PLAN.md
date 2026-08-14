# Plan

The phased plan for what is built next, in order. The transaction kernel, Cairn 2e and the beat
loop all shipped 2026-08-14 and now live in PROGRESS.md. Phase 1 collapses the Director's wire
contract, Phase 2 is the scenario creator, Phase 3 media. Each phase carries enough detail to
implement without prior context; only the next unshipped phase needs full resolution. Shipped
phases move to PROGRESS.md.

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

## Phase 1 — One small Director contract (~3–4 days)

The Director's wire schema is ~15–17KB of JSON Schema per engine, ~80% of it the effect union's
prose descriptions — duplicated per engine, and duplicated again as the worked examples
`_effect_vocabulary()` already injects into the prompt. Working rule 2 exists because large
schemas degrade small models. This phase makes the wire contract four fields and one generic
call, keeps every typed union behind the retry boundary where it already does its real work,
and proves the point by closing the deviations that were caused by schema size.

Out of scope, deliberately: the worldkeeper/advisor/creation schemas (small, healthy natively),
the authored content format (hooks keep writing op-shaped effect JSON; `parse_effect` is
untouched), and every deviation that is state/content modelling rather than schema — Cairn
Bonds, calendar/deprivation ticks, worn-vs-carried armor, 24XX gear-as-traits, creation menus.

1. **The wire contract** (`state/plan.py`): `RuleCall(name: Slug, args: dict[str, JsonValue])`,
   `DirectorBeat(roll: RuleCall | None, effects: tuple[RuleCall, ...])`, and
   `DirectorPlan(DirectorBeat + focus, speaker_id)` — one shape shared by every engine, so
   `plan_type`/`beat_type` leave `Engine` and both stages type against `DirectorPlan`/
   `DirectorBeat`. `action` is renamed `roll` on the wire: the prompt already spends prose
   separating fictional action from the one thing the dice settle, and `mechanic` would sit one
   letter from `GameState.mechanics`, which is engine state; `effects` keeps its name — it is
   the same concept everywhere else. The stringified-payload decode now lives on `RuleCall` as
   well as the plan: under this shape `args` is where a backend's re-serialization lands. The
   engine translates a call through the discriminators it already declares —
   `actions.validate_python({**call.args, "act": call.name})` and
   `effects.validate_python({**call.args, "op": call.name})`, the discriminator spread last so
   an `act`/`op` key smuggled into `args` cannot rename the call. Translation happens inside
   `check_beat` with its own error rendering: `check_draft`'s first-`msg` shortcut drops the
   field name, so a translation failure must retry as `goal: Field required`, never a bare
   `Field required`. Resolution dispatch moves onto the engine (`resolve_roll(draft, typed,
   rng)`, a match over its own union), so delete: the `Action` ABC, `SheetEngine`'s `A`
   parameter, `_resolver`/`_typed`, every per-engine `TurnPlan`/`TurnBeat`, and the Loner
   `TwistTables` protocol — the question's resolver takes the twist table as an argument the
   engine supplies. The three byte-identical effect unions
   (`TwentyfourxxEffect`/`Cairn2eEffect`/`Loner3eEffect`) fold into the one `EngineEffect`
   adapter on `SheetEngine`; of the plan plumbing only Cairn's `apply` override survives — its
   `check_overlay`/`begin`/`check_mechanics` are sheet lifecycle, not plan plumbing, and stay.
2. **The prompt teaches what the schema no longer carries.** Render each engine's vocabulary
   card into `director_instructions` *from the typed models themselves*, four ingredients per
   call: the class docstring line, each arg's description, its Literal choices and list shape,
   and its default/required marking — so prose cannot drift from validation, and choices the
   schema used to enforce are not left to retry churn. The when-to-use-which guidance now on
   each engine's `action` field description moves into the card header. Example validation
   moves onto the engine and keeps today's strictness: each `examples.json` entry and the
   shared world examples, reshaped to call shape, are translated through the engine's adapters
   at load — a `DirectorPlan`-only check would accept any misspelled name over a free `args`
   dict. Fixture families that move: per-engine `instructions`, the `turn_plan`/`turn_beat`
   schemas — now engine-independent, so they collapse to one shared pair beside
   `worldkeeper_report.json` — and the turn family; `SAVE_VERSION` bump (`Turn.steps` persists
   plan dumps in the trace) per working rule 1. **Live probe before trusting fixtures**
   (working rule 2): one real turn per engine on the shrunk contract, and while probing, try
   `NativeOutput` once — `ToolOutput` guards against a large-schema failure this contract no
   longer has; keep `ToolOutput` unless the probe says otherwise.
3. **Settle the roll vs take another action** (`state/plan.py`, `turn/pipeline.py`):
   `Resolution.flow` becomes `followup: Literal["none", "settle", "continue"]`, default
   `"continue"` — the resolvers that rely on the default today must keep looping. The roll-less
   resolution (`resolve` is `None`) returns `"none"`, replacing the loop's `outcome is not
   None` check. The loop rule, exhaustively: another full Director beat runs while the last
   resolution said `"continue"` and resolved rolls < `max_beats`; one final settle beat runs
   when the last resolution said `"settle"`, or when the loop hit the cap still on `"continue"`
   — never after `"none"`. A settle beat may write effects but no roll; that refusal is a
   pipeline-side check in the settle stage's validator, not a new engine method. Migrations:
   24XX's player disaster and landed luck trouble, and Cairn's player-grave `_flow`, say
   `"settle"` where they said `yield-to-player`. This closes LONER-3E deviation 6 — a twist
   fired on the last beat reaches the Director the same turn because the cap exit gets the
   settle pass too; update that deviation and 24XX deviation 4's loop description.
4. **24XX ally help, the proof by enrichment** (docs/24XX.md deviation 1): `Attempt` grows
   `helper_id: EntityId | None` + `helper_skill: str`; the helper must be here with a sheet,
   must not be the actor, and the skill must be on *their* sheet (same refusal shape as
   `skill`). The help die stays at most one, as `pool_faces` already insists: the helper's
   skill die when `helper_id` is set, the flat d6 when only `helped` names a circumstance, and
   naming both refuses — the SRD leaves stacking to the table, and one die is this repo's call.
   Risk-sharing stays fiction, as the deviation already argues. The wire contract does not
   change by one byte — that is the point.
5. **Cairn's rolled tables, the proof by addition** (docs/CAIRN-2E.md deviation 2): two new
   mechanics, one commit each. `fate` — `question: str`, one d6, 4–6 favorable, rolled
   resolver-side into a fact and a pending note. `reaction` — `actor_id` for the NPC met, 2d6
   into the SRD's five-row hostile→helpful table, table resolver-side like the Scars table,
   outcome slug plus a pending note steering the Director. Each is one union branch and one
   vocabulary line, no wire change. Morale and panic stay willpower-save rulings (the engine
   counts no casualties and knows no group size); the deviation text narrows to exactly that.
6. **Cairn's attack, enriched** (docs/CAIRN-2E.md deviation 3): `weapon_id` widens to
   `weapon_ids: tuple[EntityId, ...]` — the SRD's dual wield puts every named weapon's die in
   the pool, keep highest; empty stays the unarmed d4, and the refusal strings that say "leave
   `weapon_id` null" move with it. `target_ids` widens the same way for blast: one pool roll
   per target, each through the existing `_damage` path; `Resolution.outcome` is the worst
   per-target outcome — the player's own when they are a target — and the grave-moment scan
   already reads the full fact list. The deviation rewrite owns one drift the widening
   inherits from `joined_by`: an impaired multi-die pool is several d4s keep-highest, slightly
   kinder than the SRD's flat d4. Detachments stay out: a large group as one actor is state
   modelling, not schema. The deviation shrinks to detachments alone.

Done when: all four suites green, fixtures regenerated in the same commits that move them, one
live-probed turn per engine on the new contract, and the four deviation entries (24XX 1,
CAIRN-2E 2 and 3, LONER-3E 6) rewritten to describe what now holds.

## Phase 2 — Scenario creator (~3–4 days)

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

## Phase 3 — Media: scene illustrations (~2–3 days)

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
