# L3 — engine shape before Cairn and Fate

Behaviour-preserving: goldens, prompts, saves and both engines' output stay byte-identical.
Verify with `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`
(baseline 253 passing). Tests are not a focus: correct them minimally to stay green.

The line this plan draws: cross-cutting plumbing that many modules must agree on lands now;
a change with exactly one consumer lands in the phase that brings that consumer.

## Cross-cutting changes the arriving engines need

1. **Thread a seeded RNG through character creation.** In `src/aidm/engines/core.py`:
   `CharacterCreation.create(self, name: str, brief: str, picks: Picks, rng: Random)`, plus
   `rolls: ClassVar[bool] = False` on the same class. Both existing `create` bodies take `rng` and
   `del rng`; `Loner3eCreation` and `TwentyfourxxCreation` change by two lines each.
   `src/aidm/ui/create.py`: `character_page` holds a `seed = 0`; `preview()` and `create()` both
   pass `Random(seed)` (the two call sites are `ui/create.py:86,109`), so the preview is stable
   across keystrokes; a `Reroll` button that bumps `seed` and refreshes the preview renders only
   when `creation.rolls`.
   Why: Cairn rolls name, attributes, HP, traits, background and gear, and an unseeded creator
   would reshuffle the whole character on every keystroke in the name field.

2. **A post-command engine hook.** Add a base `def settle(self, draft: Game) -> tuple[Fact, ...]`
   to `Engine` returning `()`, and call it in `apply_to_draft` (`src/aidm/engines/core.py`) right
   after `play(draft, rng)`, merging what it returns: `landed = (*landed, *engine.settle(draft))` —
   then `_seed_created` and `engine.validate(draft)` run over the merged result, so what settle
   writes is both seeded and validated.
   **It must return facts, not `None`.** `apply_play` builds every trace line, card and ledger entry
   from the tuple `apply_to_draft` returns (`engines/core.py:409-416`); a hook typed `-> None` drops
   the player to 0 HP with no `Fact`, no `MechanicEvent`, and no line telling the Director it
   happened.
   **No `rng` parameter, and it must be idempotent.** `apply_play` first runs the whole command
   against a throwaway copy (`draft_refusal(..., Random(0))`, `core.py:403-406`), so settle executes
   twice per command. No planned settle rolls dice.
   Why: core `move`, `gain_improvised_item` and `kill` all change what an actor carries, and
   `Engine.validate` may only refuse, never write. Without this, Cairn's printed encumbrance rule
   — all ten slots filled reduces you to 0 HP (`CAIRN-BAREBONES.md:204`) — cannot be implemented,
   and the cap degrades into a refusal on the eleventh slot.

## Hand-maintained lists to replace

3. **Engine list, decision answers, win words and the pinned scenario in `evals/turn_eval.py`.**
   `ENGINES = engine_ids()` (from `aidm.app.launch`); delete `ANSWERS` and `Case.answers`, and
   answer with `played.pending.options[-1].id`, breaking out when there are no options. In the same
   edit, pass the winning outcomes through `cases_for` rather than the module-level `WON` (`:25`),
   and stop pinning `SCENARIO_ID = "whispering-vault"` / `CHARACTER_ID = "kael"` (`:20-23`) — pick
   the fixture per engine, since a new engine that `whispering-vault` does not declare would
   otherwise break the eval the moment `ENGINES` becomes reflective.
   Why: `ANSWERS` is identical behaviour today (`stake` → `proceed`, `defence` → `take-it`, Loner
   conflicts carry no options). `WON` is the sharper hazard: `unless_lost` (`:158`) passes whenever
   an outcome is **not** in `WON`, so Cairn's pass/fail and Fate's tie/fail vocabularies would make
   three of five shared cases vacuously pass for every new engine. The pinned scenario is the same
   hazard one level up.

## Copy-paste to expect — lift it on the third copy, not now

- **The staked action.** `resolve_stake` in `src/aidm/engines/twentyfourxx/rules.py:287` is ~8 lines:
  validate against `draft.draft()`, then `draft.pending = action.pending(f"{risk}\n\nProceed, or
  change your plan.", (DecisionOption(id="proceed", label="Proceed"),))`. Cairn stakes a save and
  Fate stakes an action the same way — and Fate's concede must be offered in exactly this shape,
  before the dice. When the third copy exists, lift `stake(draft, action, risk)` and a `PROCEED`
  slug into `engines/core.py`; one caller does not earn it.
- **Settling what a free-text answer consumed.** `_settle_defence` in
  `src/aidm/engines/twentyfourxx/engine.py:82` reads `deps.answered`, checks `kind`, revalidates the
  payload. Fate needs it three times (invoke after the dice, compel, taking harm). Copy it in L5,
  then lift `answered_as(deps, kind)`; the kind check is the trap worth centralising once.

## No refactor needed — the contract already carries it

- **Advancement stays mandatory.** This plan originally proposed `Engine.advancement:
  Advancement | None`, on the strength of `plans/L6-cairn-barebones.md` naming it a prerequisite.
  Cairn Barebones has Training (docs line 625), which is `SheetAdvancement` + `complete_chapter` in
  ~12 lines, and Fate has breakthroughs. No engine on the roadmap lacks advancement — dropped.
  (The doc was not wrong: it frames Training as a *downtime procedure* gated by Master, Costs and
  Milestones, which L6 cuts and records as a deviation.)
- **No `Decision` default option.** L5 first asked for one so a free-text answer could complete a
  decision. It is unnecessary and harmful: `turn/run.py:291-302` already hands the consumed decision
  back as `deps.answered` on free text, which is how 24XX turns "I raise my medkit" into the right
  item. A default option would override that with "take the hit" — a 24XX regression. Fate copies
  the settle shape instead.
- Per-item and per-aspect state: an engine's `Mechanics` may add fields beside `sheets` (`loner3e`
  already adds `twist`), so Cairn's item records and Fate's aspect ledger stay engine-owned.
- Seeding: `apply_to_draft` runs `Engine.seed` for every `entity_created` fact, covering improvised
  items and canon materialized by world growth (`_added_entity` goes through `Game.add`). `seed`
  already receives an `rng` it currently discards (`engines/core.py:328`), so an engine that wants
  rolled NPC sheets needs no signature change.
- Repeated pauses: `consume_answer` clears `pending` before the resolver runs, so a decision may
  legally open the next one — Fate's invoke loop needs nothing new.
- `SheetEngine` fits both arrivals: every actor carries one sheet in each.
- Chapters: `chapter_command` and `SheetMechanics.completed` are opt-in.
- Engine discovery, the launcher catalogue and the settings page are already reflective — a new
  engine adds no entry to any list outside its own package.
- `sheet_rows` and `describe` as flat `(label, value)` rows carry both new sheets.

## Surfaced here, deferred to the phase that consumes it

- **`DiceEvent` forbids a summed result.** `_rolled_matches_faces` in `src/aidm/state/facts.py`
  requires `kept in rolled`, so Fate's 4dF total has no honest representation. Cairn needs no summed
  pool (damage and hazards are single dice; creation rolls 3d6 through `rng` directly), so Fate is
  the only consumer — the relaxation, the summed combine on `roll_pool` and the die-face label land
  together in L5.

## Considered and cut — do not re-propose

- **Constants for the `entity_created` / `entity_discovered` fact kinds.** An earlier draft called
  this the one cross-module coupling worth naming. The real sites are five string literals
  (`state/model.py:235,243`, `engines/core.py:426,434`, `evals/turn_eval.py:207`); two module
  constants over five literals buy grep-ability, not type checking — nothing here is
  exhaustiveness-checked. Not worth a step.
- **`_STEP_COPY` in `ui/game.py` → an exhaustive `match`.** Out of scope by this plan's own rule.
  `TurnStep = Literal["director", "narrator", "scenario_creator"]` (`turn/run.py:178`) is a pipeline
  step, not engine vocabulary: no arriving engine adds one, and neither L5 nor L6 touches
  `ui/game.py`. Move it to a general cleanup pass if it is ever worth doing.

## Explicitly not doing

- No non-sheet `Engine` base, no zone or scene model, no core inventory or slot concept — Cairn
  owns its capacity rule, Fate owns its aspects. The `settle` hook is a callback, not a model.
- No advancement-less tab hiding in the UI, and no null-object `Advancement`.
- No rewrite of the per-engine cases in `evals/turn_eval.py`: engine vocabulary and content.
- No change to `Scenario.engines`, the `characters/<id>/<engine>.json` overlay layout, or
  `SavedGame`: two new engines add content, not format.
- No prompt or `director.md` restructuring — L4 rewrites those against the source rules anyway.
