# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

## Done

- 2026-08-13: recentering decided and PLAN.md rewritten — phases: 1 delete story, 2 oracle→loner3e
  (SRD-compliant, tables resolver-side), 3 docs-only engine shelf, then scenario creator, media.
- 2026-08-13: docs/24XX.md — exact SRD v1.4 (CC BY), engine package sketch filled.
- 2026-08-13: docs/LONER-3E.md — full 3e SRD from the lonersrd GitHub source (CC BY-SA); sketch
  filled; PLAN phase 2 gap list corrected against the exact text (conflict-no-tick is already
  SRD-exact; no Luck-spend rule exists).
- 2026-08-13: docs/CAIRN-2E.md — 2e Player's Guide mechanics extraction (CC BY-SA); sketch
  filled; verdict ~2× loner3e code, stays on the shelf.

- 2026-08-13: Phase 1 done — `cce1701` eval harness deleted (−1,199), `d20da72` story engine +
  tests + fixtures + overlays deleted, core tests repointed to oracle (−3,177/+123), `459a8d7`
  stranded trims: offer choice fields, `AllocationStep`, dice `vs=` (−183/+31). Suite 99 green,
  no SAVE_VERSION bump; only fixture movement is the always-null `vs`/`success` keys leaving
  the turn trace. Reviewed: sweeps clean, probe/oracle engines untouched.

- 2026-08-13: loner3e phase shipped (`dbec49c`) — full rename with SAVE_VERSION 56, twist
  table resolver-side, SRD growth verbs, deviations cut to 10: twists now narrate the turn they
  land (twist fact narratable, note develops it next turn) and the max-4 caps are gone.

- 2026-08-13: two full-tree audits (refactor + loner3e compliance) accepted and sequenced as
  PLAN.md Phase 3 (shrink and comply, 11 steps, one SAVE_VERSION bump in step 8); scenario
  creator and media renumbered to phases 4 and 5; content-pack rejection reversed (Loner
  adventure packs are real upcoming content).

- 2026-08-13: Phase 2 done — README names the engine shelf (24XX, Cairn 2e) and the rule;
  shelf docs were already in. Phase 3 step 6 upgraded to two selectable packs (SRD + AP01
  fantasy, selection as creation step 0; AP01 license ambiguity flagged in step 10).

- Phase 3 in flight (2026-08-13), suite green after each step:
  - step 1: dice.py trimmed to single-term `NdM` — `DiceExpr`/`ConstantTerm`/multi-term/`bonus=`/
    `"disadvantage"` gone; probe engine adds its stat in code.

  - step 2: `entity_fact`/`explained_fact`/`explained` live in `state/facts.py`; world.py
    add/reveal/move and both engines use them; four relation functions → one `_relation_change`,
    traces byte-exact.

  - step 3: launcher `_one` helper + `ContentOption.subtitle` (Scenario/CharacterOption gone),
    `LauncherModel`→`Frozen`; `FileStore` merges FileSaves/FileTraces, `_StoredVersion` gone;
    `GameSession`/`run_turn` take `Settings`+`FileStore`; `page_header` ctx manager,
    `functools.partial` handlers, `stage()`→`Stage.of`.

  - step 4: scene shapes (`Exit`…`_undetailed`) moved verbatim to `turn/scene.py`; prompts.py,
    pipeline, roles, `test_context_boundary` repointed.

  - step 5: five core prompt constants script-generated into `turn/prompts/*.md` (byte-exact,
    no trailing newline), loaded via `engine_text`; instruction fixtures unmoved.

  - step 6: `engines/loner3e/pack.py` (`Pack`/`PackEntry`, `load_packs`, `twist_table`) +
    `packs/srd.json` (curated tables verbatim + SRD twist columns, name "Core tables") and
    `packs/ap01-fantasy.json` (four d66 tables transcribed from the AP01 page, slugified ids,
    empty details, no twist table); creation step 0 "Choose a table set"; twists flow
    engine→`resolve_question(…, twists)`; delegation shim gone (begin/commit/renderer bodies
    live in rules.py), `read`/`write` wrappers → `read_mechanics(state, Model)` in counters.py.
  - step 7: compliance prose — Sibylline Responses section in director.md, three scene moods in
    scene_director.md, lingering-enemy-is-a-thread sentence in advancement.md, narrator recite
    list system-neutral; instruction fixtures regenerated, diff is exactly those four texts.

  - step 8: save-shape commit, SAVE_VERSION 56→57 — `available_tags` takes `Mechanics` and merges
    every carrier's sheet tags (rat's duplicated world trait deleted); edge/burden → skill/frailty
    in TraitChange/Trait docstrings, kael and world content; `Thread.kind`, `Memory.tags`,
    `Memory.turn`, `Counter.minimum`, `Counter.recharge` deleted. Golden regen read: removed keys,
    vocabulary swap, rat trait gone; turn fixture moved only on `save_version`.

  - step 9: `_strike` resets both participants' luck to LUCK_MAX when a side hits 0 (SRD "resets
    after conflicts"), defeat_note kept; tests: reset both pools, zero-luck refusal, opponent
    sheet tags visible to the resolver. No golden movement.

  - step 10: deviations list rewritten (12 entries — luck-reset deviation dropped; hidden twist
    counter, one-change milestones, closed concept menu, unrolled 5W+H added), sketch bullet now
    points at the landed prose; README gains Licensing (CC BY-SA attribution, AP01 ambiguity,
    code license open).

  - step 11: comment trim sweep over every production and test file (all `#` comments, all
    docstrings via AST dump, suppression directives) — nothing to delete; the flagged noise
    left with the files steps 1–6 rewrote. Zero-diff step.

  - adversarial review (fable subagent, full staged diff): no comment/docstring/test violations;
    fixed F1 (luck reset now refills to the sheet's own maximum, not a +LUCK_MAX delta; 10-max
    test) and F3 (creation picks pruned by surviving option on a pack switch, form refreshes
    before preview). F2 (history_window=0 shows all) accepted as intended; F4 (add/move on
    entity_fact silently fixed an unrevealed-mover narrator leak) accepted.

  - Phase 3 done (2026-08-13). Steps 1–11 are uncommitted, staged as one tree; every
    verification (pytest ×102, ruff check, format, basedpyright) green. Production LOC 4,814
    against the plan's ≈4,550 estimate — the remaining gap is the audits' pre-rewrite guess,
    not un-taken findings.

- Phase 4 (redesign refactor, REFACTOR.md) in flight (2026-08-13), suite green after each step:
  - step 1 core folds + config: `check_draft(state, act, what)` in `state/plan.py` folds `_trial`,
    `check_action`'s try, and loner3e `violation` (it commits the draft, as the real resolve
    path does, so nothing the model is told is legal fails later); `duplicates`/`require_unique`
    in `state/base.py` replace five dup-detection loops; `_unused` folds `slug`/`text_slug`
    numbering; `apply.py` `_require`/`_require_kind` deleted, their model-facing messages now on
    `WorldState.require`/`require_kind`; `config.Role` is a `Literal` and `roles` is keyed by it,
    so a role no stage is built for cannot be configured — pydantic refuses the key and pyright
    refuses the `Stage.of` name, with no second list to drift.
    Net +4 LOC, no fixture moved, SAVE_VERSION unchanged.
    Deviation: `Providers` stays a model — pydantic-settings does not merge a partial env
    override into a dict field's default, so `providers: dict[str, ProviderConfig]` would break
    the repo's own `.env` (which sets only `PROVIDERS__OPENROUTER__API_KEY`).

  - step 2 roster merge (SAVE_VERSION 57→58): Scene Director gone — `SceneDirective`,
    `scene_stage`, `Stages.scene` and the scene step deleted; `TurnPlanBase` carries
    `focus`/`pressure`/`stakes`/`speaker_id` before the engine's action; `check_speaker` is a
    Director output validator; `scene_director.md` merged into `director.md` (renamed from
    `rules_director.md`) and its Dramatic/Quiet/Meanwhile taxonomy moved to
    `engines/loner3e/director.md` as MOODS — the provenance leak; `render_director` has one
    signature and always shows MEMORIES; TURN_STEPS is 5. Fixture diff: version lines, the
    turn_plan schema's four new fields, the merged instructions, MEMORIES in the director
    prompt, the scene step gone — dice traces and facts unmoved.
    **Not done: the live probe gate.** REFACTOR.md wants one gpt-oss-120b run against the
    merged Director schema before trusting it; that needs network, so it is still owed. The
    documented fallback (two director calls sharing one render) is unaffected by anything
    landed here.
  - step 3 Subsystem unification (SAVE_VERSION 58→59): `Advancement`/`AdvancementOffer` →
    `Subsystem`/`Offer` with `subject_id`, `resolve(draft, offer, proposal, rng)` and a
    `ClassVar` id naming its own instructions file; `Engine.subsystems` is a tuple; trace
    entry `Advance` → `Applied(entry="subsystem", capability, subject_id)`; session keys
    advisors and drafts by capability slug (`Drafted` pairs offer + proposal, preview trials
    with `Random(0)` and confirm rolls the session rng); `subsystem_panel` renders one tab per
    subsystem. loner3e offers one milestone per subject in `{player} ∪ party()`, so NPC
    advancement fell out — new test grows a party member's own sheet. Only fixture movement:
    the advisor prompt's ON OFFER line, now subject-named.
    An NPC who joins after N resolved threads is offered those N milestones: accepted as
    loner3e behaviour (they earned them off-screen), not a bug for step 6's `seed` to fix.

  - adversarial review (fable subagent, staged diff): no state-corrupting defect. Fixed —
    `drafted.pop(capability, None)` in the panel (a queued second click could `KeyError`),
    `GameSession.subsystem_advisors` no longer collides with `Engine.subsystems`, the
    stale-offer gate is now covered in `test_proposals.py`. Verified clean: the merged
    Director's validator order, `check_draft`'s added commit (can only over-refuse),
    `Offer` equality as the still-on-offer gate, per-tab NiceGUI refresh, `_unused` at the
    64-char boundary. Standing hazard for step 6: `offers()` indexes `sheets[subject_id]`,
    which only `Loner3eEngine.commit`'s backfill keeps total — the split into pure `validate`
    must keep a path that gives every actor a sheet.

  - step 4 dice pools (SAVE_VERSION 59→60): `roll_pool(faces, reason, rng)` keeps the highest die
    and replaces `roll`/`RollMode` — expression parsing gone, `Rolled.total`→`kept`, fact data
    `dice`/`mode`/`total` → `faces`/`kept`; loner3e advantage is a `(6, 6)` pool, disadvantage the
    same pool on the risk side; probe engine ported. Fixture diff: the one advantage roll's trace
    (`2d6 [4, 5] -> 5`) and the data keys — dice values themselves unmoved.

  - step 5 threads/clocks/hooks (shares step 4's bump and regen, as REFACTOR allows): `Counter` to
    `state/base.py` (`collections.Counter` imported as `Tally` there); `Thread.clock: Counter | None`
    (a clock must name its maximum) rendered in the Director's thread lines; `AdvanceThread.tick`
    refuses a clockless thread; `Hook.once` and `Hook.effects: tuple[JsonValue, ...]` parsed by the
    engine — two new abstract methods, `Engine.parse_effect` (load) and `Engine.apply_effect`
    (fire), with `Binding` (engine id + parse_effect) replacing the `EngineId` argument of
    `load_scenario`/`load_character` so the "hooks advance only authored threads" check runs
    engine-bound in `content.check_hooks`; `fire_hooks` takes the engine's apply and runs a second
    pass over the Worldkeeper report's facts. `_effect_vocabulary`'s completeness raise is now a
    test — which exposed and fixed a latent bug: `effect_keys` never unwrapped the PEP-695 alias, so
    the old startup check was vacuous. Fixtures: `tick` in two schemas, `clock`/`once` in saves, and
    hook effects now stored as authored (no default-filled `status: null`).

  - step 6 typed overlays + validate/seed + write_scenario (no persisted bytes): `Engine.rules_type`
    (loner3e: `Sheet`) joins `Binding`, so `load_scenario`/`load_character` validate every authored
    overlay payload field-by-field at load (`content.check_overlay`); `commit` splits into pure
    `validate` (refuses a missing player, an actor with no sheet, a sheet with no actor — never
    repairs) and `seed(draft, entity, rng)`, driven by `pipeline.seed_created` over every
    `entity_created` fact of the turn, whoever wrote it. A seeded NPC starts at the resolved-thread
    count, so joining late owes them no milestone back-pay (new test). `write_scenario` beside
    `write_character` with a round-trip test; the `Rules` alias is gone (it read as a sibling of
    `rules_type` while being the untyped half). `test_engine_contract` inverted: a created actor is
    refused until seeded.

  - step 7 packs (SAVE_VERSION 60→61): `Settings.packs_dir`, `engines/packs.py:pack_paths` merging
    user files over shipped by stem, `Engine.__init__(extra_packs)` fed by `Runtime.engine` from
    `packs_dir / engine_id`; a broken pack is a logged skip, not a launcher crash. `Sheet.pack`
    records the table set at creation, `twist_table(packs, chosen)` reads the *player's* set and
    falls back to the SRD's for sets that publish none (AP01, most user packs) — the singleton
    raise is gone — and `validate` refuses a save whose set is not installed. Fixtures: version
    line plus `"pack": "srd"` on every sheet.

  - PLAN.md phase 5 (proposal study) landed inside step 5, as that section directs: `fire_hooks` is
    a bounded drain — rounds of the same one-pass body, each round matching the facts the previous
    round produced, stopping at `MAX_HOOK_ROUNDS = 3` with a `hooks_capped` fact, never silently;
    `thread_advanced` data carries `clock_filled` so a filled-clock hook matches one boolean.
    This closed a dead chain, not a late one: the shipped scenario's `vault-charted` reveals the
    vault, and `vault-sighted` now fires on that reveal in the same turn (it could never fire
    before). Fixture movement is exactly that chain — the Warded trait, two fired hooks, two
    pending notes, and the narrator seeing the trait it caused.

  - adversarial review (fable subagent, staged diff). Fixed: the Worldkeeper could kill a turn
    after narration by ticking a clockless thread (its moves are applied untried — now a
    `ModelRetry` in `_thread_moves`); `AdvanceThread.tick` accepted negatives and drained a clock
    (refused in the validator, not `Field(ge=0)`, which would move two schema fixtures); a pack
    file whose stem is not a slug loaded and then crashed the creation page (skipped with the
    other unreadable ones); dead `Engine.extra_packs` attribute; `Rolled` collapsed to
    `tuple[int, Fact]` (every caller read one field); `EXAMPLES` → `WORLD_EXAMPLES`, which names
    the shared world-effect file beside `_examples()`, which reads each engine's own. Verified
    clean: rng order, `once` semantics and `fired_hooks` uniqueness, save round-trip, the
    validate/seed split closing the `offers()` hazard, layering, every comment and docstring.
    Kept as is with reasons: `parse_effect` + `apply_effect` (a `TypeAdapter[Frozen]` attribute
    fails on invariance; a covariant return does not), `Binding`, `check_hooks`/`check_overlay`
    placement, `seed_created` at end of turn, `twist_table`'s SRD fallback.
    Two accepted gaps: a resumed save's hooks are parsed at fire time only (the scenario they were
    copied from is checked at load in the same session), and the `hooks` step trace records the
    first hook pass only — the Worldkeeper-pass fires reach `turn.facts` but no step.

  - verified end to end: 117 tests, ruff, format, basedpyright green; `Runtime` opens the shipped
    game from a clean temp save dir. Prod LOC 4,881 against REFACTOR's 4,780–4,880 band, before
    phase 8's trim.

## Next

- Phase 4 step 8 (docs + trim: CLAUDE.md/AGENTS.md roster and validate/seed wording, README,
  superseded PLAN entries, comment trim, LOC audit) then step 9 (the 24XX engine as the proof).
  Step 8 also moves PLAN.md's phase 5 section out — it shipped inside step 5 — and renumbers what
  follows. Still owed from step 2: the live gpt-oss-120b probe of the merged Director schema.
