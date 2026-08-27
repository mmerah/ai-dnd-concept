# PROGRESS

Tracks `PLAN.md`. One section per phase; done items stay so the next reader sees what landed.

## Phase 0 — docs become pointers, not copies — DONE

- Fate Condensed's CC BY 3.0 attribution paragraph moved into `README.md` **before** the deletion,
  quoted verbatim (the licence breach risk of this phase).
- `docs/24XX.md` 367 → 60 lines, `docs/LONER-3E.md` 946 → 80, `docs/CAIRN-BAREBONES.md` 1476 → 48,
  `docs/FATE-CONDENSED.md` 1408 → 53. Each carries: official source URLs + guides, the archive or
  commit the old extraction came from, licence and exact attribution string, per-pack source URLs,
  deviations, and where the mechanics live.
- Deviations carried over whole, unnumbered preambles included (24XX help/bulky/shares-the-risk/
  invent-branch; Loner Adventure Maker/5W+H/mood-roll/Appendix A). Cairn and Fate get an empty
  Deviations section for their own phases to fill.
- Loner deviation 2 reworded per the plan's reverse case: a non-living character is refused, not
  given a sheet on demand.
- `Planned engine package` / `Engine package sketch` sections deleted — superseded by `plans/L5-*`
  and `plans/L6-*`.
- Prose references updated: `README.md` engine-shelf paragraph and licensing table (per-doc rows
  dropped, one line points at the pointer files), `loner3e/rules.py:25`, `twentyfourxx/rules.py:27`,
  `IDEAS.md:7-8`. README's "next engine" order now matches the plan: Cairn, then Fate.
- Verified: `pytest` 253 passed, `ruff check`, `ruff format --check`, `basedpyright` clean.
- Adversarial review round (every URL fetched, licences checked live, deviations diffed byte-wise).
  Fate's attribution confirmed byte-identical to the archive copy — no breach. Nine findings fixed:
  Cairn's Scars table is on `barebones-core-rules`, not the three pages named; Cairn's "required
  attribution" was a composed string the source does not print (relabelled); the Loner explanatory
  guide covers 2e, now caveated; the dead `faterpg.com/licensing` bullet dropped; the Loner
  extraction pinned to commit `2946f2f`; the AP01 footer quoted exactly (`© 2021-2026`, and the page
  carries no CC declaration at all); the 24XX credit condition includes the version number;
  `plans/L3-engine-shape.md:71` retargeted off the deleted section; `PLAN.md` now points here.

## Phase 1 — L3 engine shape — DONE

- `CharacterCreation.create(name, brief, picks, rng)` plus `rolls: ClassVar[bool] = False`; both
  existing creators `del rng` — neither rolls. `ui/create.py` holds a page-level `seed` that
  `preview()` and `create()` both read, so what was previewed is what is written, and renders a
  `Reroll` button beside `Create` only when `creation.rolls`.
- `Engine.settle(draft) -> tuple[Fact, ...]` returning `()` on the base, merged into `landed` in
  `apply_to_draft` before `_seed_created` and `validate`. A settle that opens a decision is refused
  there: it would silently discard the one the command opened.
- `evals/turn_eval.py` reflects instead of listing: `ENGINES = engine_ids()`; `ANSWERS` and
  `Case.answers` deleted in favour of `pending.options[-1].id` (stake offers only `proceed`, defence
  ends on `take-it`), breaking out when a hand-back carries no options; `unless_lost` takes the
  winning outcomes from a per-engine branch in `cases_for` that raises for an engine declaring none.
- Deviation from the plan: `SCENARIO_ID` / `CHARACTER_ID` are unpinned to `authoring.worked_example`
  and `authoring.starter_character`, without the planned per-engine fixture search. `cases_for`
  raises for an unknown engine before `begin()` runs, and every case body names whispering-vault
  canon, so the search was 25 unreachable lines that would have failed inside `staged()` anyway.
- The plan's stated reason for `settle` idempotence was wrong and is corrected in
  `plans/L3-engine-shape.md`: the trial run is a `deepcopy`, so the real hazard is a turn's several
  commands each settling.
- Verified: `pytest` 254 passed (253 baseline + the settle test), `ruff check`, `ruff format
  --check`, `basedpyright` all clean. The eval itself needs a live model and was not run.

## Phase 2 — L4 rules compliance — DONE

Two open questions in `plans/L4-rules-compliance.md` were decided by the maintainer, both toward
fidelity: step 5 takes branch **(a)** (kit picks become real gear), step 10 is **taken** (a
non-living character can be fought). An adversarial review then cut the first implementation down;
what is described here is the state after that pass, not before it.

### 24XX

- **Gear catalogue (step 2).** `KitItem` renamed `GearItem` and given `cost` (ge=1, default 1) and
  `breaks` (1-3, default 1) — one model for `starting_kit`, `Specialty.kit`, both `kit_choice`
  fields and the new `Pack.gear`, rather than the plan's KitItem/GearItem split. **22 entries**
  transcribed from <https://24xx-srd.carrd.co/> § Gear in printed order (Armor 3, Cybernetics 7,
  Tools 6, Weapons 6), then re-verified against the live page and corrected: four inserted
  disjunctions were removing the SRD's cumulative ₡1 upgrade *menus* ("echolocation, vocal stress
  detector") by rewriting them as a choice, `3x` was restored to the printed `3×`, hardsuit's
  clauses to printed order, and the pack's spelling to the printed "defense". Code identifiers stay
  British (`resolve_defence`). `Pack.gear` defaults to `()`: a hack pack that sells nothing is
  legitimate, so `buy_gear` errors at buy time instead.
- **`buy_gear`.** An `action`, built in `TwentyfourxxEngine.__init__` because it needs `self.packs`.
  Charges through the existing `apply_change_credits` (which already refuses a dead or absent actor
  and an overdraw), slugs the item against `draft.world.all_ids()` and lands it with `draft.add`, so
  a second pistol becomes `pistol-2` and records `entity_created`. `_carried(entry, item_id,
  owner_id)` is shared by creation and purchase. It resolves the entry across **every installed
  pack**: the tool description is built once in `__init__` and can never be per-game, so a
  per-character catalogue would have advertised gear the command then refused — a guaranteed wasted
  retry on a weak model, caused by the prompt itself. `Sheet.packs` records every table set used by
  a character or authored sheet; it does not narrow the global shop. Duplicate gear ids across
  installed packs are refused when the engine loads, so a purchase is never order-dependent.
- **Break budgets (step 3).** `breaks-1..3` reserved item traits, never a `Mechanics` dict.
  **Absence of a mark means one break** — that is the SRD's printed default for any item, so
  authored, starting and improvised gear all keep working untouched; only `breaks > 1` writes a
  mark. `resolve_defence` rewrites `breaks-N` to `breaks-(N-1)` by trait id and emits one fact and
  one card per break; the last break falls through to the existing `add_trait(BROKEN)` path.
  `_defence_decision`'s `BROKEN` filter is unchanged — a partly-spent item is correctly still
  offered. `director.md` reserves the three slugs against flavour writes.
- **Actor-scoped attempts and `Attempt.hit` (step 4).** `Attempt` and `LuckTest` name the acting
  entity. `stake_attempt` and Defence remain player-only; an NPC's attempt rolls directly and never
  offers the player their gear. Required `hit` opens Defence only when the player's failed attempt
  means physical harm; a tripped alarm does not offer "break the medkit". The `fight-the-wrecker`
  eval looks specifically for a failed player attempt before requiring a settled Defence.
- **`Defence.outcome` deleted (step 4b).** Field, parameter and call site.
- **Kit picks (step 5a).** `kit_choice` on both `Specialty` and `Origin`, with `specialty-kit` /
  `origin-kit` creation steps (hyphens: `CreationStep.id` is a `Slug` and rejects underscores).
  Muscle picks sword / firearm / cyber-arm; Android picks synth skin / case. **Deviation 1 deleted**
  from `docs/24XX.md` — it is closed, not documented.
- **Deviations added (steps 6, 7):** starships are not modeled; a killed character ends the game.
  Both are features, not rules fixes, so both were correctly documented rather than built. The
  catalogue's "Upgrade with …" strings would have been a third, silent one — `director.md` now says
  an upgrade is not a catalogue entry: charge ₡1 with `change_credits`, record it with `add_trait`.

### Loner 3e

- **A non-living character can be fought (step 10).** `resolve_question` seeds a blank `Sheet` for
  the opponent the first time one is asked for. A first implementation overrode `opening_mechanics`,
  `seed` and `validate` to sheet every item eagerly; it was deleted — ~20 lines (one a near-copy of
  `core.py`), 60 lines of fixture, a dead `advancement.ledger` write for every item, and a
  `luck: 6/6` row on every item in **both** the Director and Narrator prompts, including on an
  entity the player did not know existed.
- **`_require_opponent_here`** in `loner3e/rules.py` (not `state/actions.py`: 24XX must not inherit
  it) accepts an actor — delegating to `require_actor_here`, so the dead-actor refusal is reused —
  or an item that `draft.is_here`, so a carried object counts. A location is refused.
  `Question.opponent_id`'s description and the `Conflicts` section of `director.md` now say so.
- **Pack renamed (step 9).** `name` is now "Starter tables": Loner 3e publishes no concept, skill,
  frailty or gear tables — those entries were written here. `source` now identifies this repository
  and the official origin of the twist columns; the two other places in `docs/LONER-3E.md` that
  still called the pack an SRD transcription were corrected.
- **Deviations went 5 → 6, not 5 → 7.** Step 9's provenance is a real deviation and was added. Step
  11's mirror-versus-SRD tie result is **not** one — the code follows the official SRD, so nothing
  in `src/aidm/engines/loner3e/` diverges, and the section's own first line defines it as divergence
  from the official rules. It lives on the existing sources bullet that already warns the farirpgs
  mirror is Loner 2e. Step 12 needed nothing: deviation 3 already says twists land in the same call.
- **Deviation 2 rewritten.** It claimed sheets were actors-only. It now records the real remaining
  gap: the SRD authors a non-living character's Concept, Skills, Frailties and Luck, while here it
  gets a blank sheet on demand and its traits stand in for those tags.

### Review pass

An adversarial review of the first implementation found three must-fixes and five should-fixes, all
applied: the pack-versus-catalogue mismatch above; two stale provenance lines in `docs/LONER-3E.md`;
the unmodelled ₡1 upgrade economy; the three eager-seeding overrides; a docstring attached to
`breaks_trait` that described `breaks_left`; and the `buy_gear` description, cut 702 → 360 chars
(schema size, not output mode, was what broke this weak model's structured output before — the 24XX
tool schema now costs +1325 bytes over baseline instead of +1706). `breaks_slug`, `require_installed`
and two restating comments were deleted as one function and one abstraction too many.

Steps 8 and 13 needed no work: both engines' dice maths is compliant as printed.

## Single-engine scenarios — DONE (out of phase, 2026-08-26)

Supersedes `PLAN.md` § Scenarios, which is rewritten to match. Motivation: every non-player entity
was born with a blank sheet, so the Director read `state: luck: 6/6` for a scribe and for a bloated
rat alike, and nothing a scenario could author changed it.

- **`Scenario.engines` → `engine: EngineId`**, plus `packs: tuple[Slug, ...]` on `Scenario` (not on
  `ScenarioMeta`, which every save carries — authoring metadata has no business there).
- **`Entity.rules: dict[str, JsonValue]`**, opaque to core exactly as `CharacterProfile.rules` is.
  `SheetEngine` sheets the player and entities the engine says use sheets. Loner requires and seeds
  sheets for actors; 24XX may leave opposition un-sheeted and describe it through behavior and risk.
- **Strict at the boundary, engine-owned.** `begin_game` refuses a scenario authored for another
  engine or unavailable packs, then delegates authored-content checks to the engine. Loner refuses
  authored actors without `rules`; 24XX accepts them and validates any authored skills against that
  entity's selected pack.
- **Content.** `whispering-vault` is loner3e with concept/skills/frailties/gear for `mara`, `tomas`,
  `elena` and `cloister-rat`; `drowned-road` is twentyfourxx with pack-label skills for `ovid-sarn`
  and `mara-voss`, plus `deel-hask`, an authored hostile, and two `when_reached` stage directions.
  Loner luck stays 6/6 everywhere: the SRD prints 6 for every character, its own examples being an
  NPC and a damaged spacecraft. Lowering a rat's luck would have been a new deviation.
  `specialty`/`origin` are authored for the player only — nothing reads them mechanically, and a
  village bell keeper is not built from a player-character package.
- **Pack meanings reach the prompt.** `SheetEngine.meanings` + `pack_meanings` render a published
  tag's `detail` on its own lines under the row that names it, so the Director judging Loner's
  `position` match reads more than a bare noun phrase and never has to guess which row a bullet
  belongs to. A freehand tag has no pack entry and stays bare — naming it well is the author's job.
  The concept blurb is skipped as generic where the entity's `brief` is not. Only loner3e overrides
  `meanings`: 24XX's specialty and origin `detail` are character-creation menu copy ("Take climbing
  gear and night vision goggles"), which reads as an order in the Director's own state block, so
  that override is deleted and `SheetEngine.meanings` is the default for that engine.
- **Prompt cost, measured against `git show HEAD:<fixture>`** — the figures this bullet carried
  before were taken against a half-applied working tree and were wrong in both directions. Real:
  loner3e director 2985 → 3765 bytes (+26.1%), narrator 2118 → 2781 (+31.3%), advisor 570 → 948
  (+66.3%). Meanings are 388 bytes of each loner3e prompt (378 of the advisor's); the rest is the
  authored NPC `rules` this change added. 24XX director 2937 → 3147 (+7.2%), narrator 2129 → 2099
  (−1.4%), advisor unchanged — no meanings at all now, so all of it is authored NPC `rules`. The
  loner3e advisor's +66.3% is the largest number here and the least alarming: that prompt is one
  sheet and a sentence, so five tag explanations nearly double a very small thing.
- **Plumbing:** `read_scenarios` drops its engines element, authoring collapses to one engine, and
  every scenario and sheet names at least `srd`. An entity may combine several selected packs;
  Loner keeps the one mechanically singular choice as `twist_pack`. Both authoring harnesses select
  installed packs and receive their validated content plus engine-specific vocabulary guidance.
  Characters record their creation packs; 24XX rejects ambiguous duplicate shop ids across
  installed packs.
- Verified: 268 passing, `ruff check`, `ruff format --check`, `basedpyright` clean.
- Adversarial review round closed the remaining integration gaps: pack selection and content now
  reach built-in and code-mode authoring; user pack directories are loaded; growth uses the
  scenario's recorded packs; engine-owned checks replaced the Loner-specific core guard; 24XX
  Defence is player-side; and the eval no longer confuses another roll with a failed attempt.
  `SheetEngine.seed` preserves authored rules, and opening validation still reports the full
  `sheets.<entity id>.<field>` path for invalid overlays.
- **Not fixed, needs a scenario rather than an edit:** 24XX's shipped pack is science fiction
  (cybernetics, hardsuits, night vision goggles) and `drowned-road` is a tide-bell pilgrimage. The
  engine plays, but nothing in its content matches its world.

**Settled:** the narrator prompt renders NPC sheet state, and that stands. It now carries an NPC's
concept, skills and frailties as well as their luck. The maintainer's call: it helps the narrator
write better prose, and a tag is characterisation before it is a number. Read `CLAUDE.md`'s
revealed-canon rule as covering plot canon — which entity is in the prompt at all — not the
mechanical colour on an entity the player can already see.

## Phase 2.5 — 24XX needs a scenario in its own genre — DONE (2026-08-27)

`drowned-road` re-authored **in place** as science fiction (retiring the slug would have touched the
golden save fixtures that pin it): a maglev causeway the raised sea swallowed, out to Relay Nine and
its sealed vault deck. Four locations, companion `mara-voss`, wrecker `deel-hask`, hidden
`cipher-spike`, and an outfitter (`verrin-ade`) so `buy_gear` and the `breaks-1..3` budgets are
reachable in the fiction. Eval `Canon` retargeted; the old fantasy `source.md` deleted so growth
cannot extend the wrong genre. All actor skills verified against the pack.

## Tightening round — DONE (2026-08-27, unstaged for review)

A four-agent adversarial review of the Phase 2 + single-engine diff, findings verified against the
code, then fixes. Verified: 271 passing, `ruff check`, `ruff format --check`, `basedpyright` clean.

- Bugs: worked example now follows the authored engine (none shown when the engine has no scenario
  yet — the first-authoring path for a new engine); a fully broken sturdy item no longer keeps a
  stale `breaks-N` mark; an un-sheeted 24XX NPC attempt errors with a redirect instead of a dead
  end; growth packs route through `selected_packs`; `restored` validates the save at load.
- Consistency: per-entity sheet validation + packs-subset check lifted to
  `SheetEngine.check_scenario` (with a `check_sheet` hook 24XX overrides for skills), reporting
  `sheets.<id>.<field>`; `describe` matches meanings per row exactly; Loner deviation 2 reworded.
- Trims: create.py engine+packs select deduplicated; the tripled "follow the engine guidance" prompt
  line cut to one; pack dump compacted (`exclude_defaults`, no indent); `pack_meanings` moved into
  loner3e; `run.authoring_context` renamed `draft_context`.
- **Refuted, not a deviation:** conflict-exchange ties tallying the Twist Counter. The SRD prints
  "The Twist Counter does NOT apply to Harm & Luck"; the code is compliant as printed.
- **Scenario-shipped content packs built.** One loading concept (`PackSources`,
  `engines/sources.py`); authoring gains `write_pack`, validated against the engine's `pack_type` at
  write time and confined to the draft; packs land in `scenarios/<slug>/packs/` via
  `write_scenario`; engines memoised per `(engine, scenario)`. Growth publishes the tool but refuses
  it with an explanation — a live game plays on the packs its scenario named.
- **24XX starships closed as printed:** the SRD's seven ship functions and ₡10 upgrades transcribed
  into the pack, bought with `buy_gear onto_id` into a ship (a `location`); no new kind, no sheet.
- **24XX death closed in the taking-over-a-companion form** (maintainer's call, same day):
  `Game.player_id`/`SavedGame.player_id` replace `PLAYER_ID` reads everywhere behavior follows the
  current player — nine creation-scoped reads of the constant survive, each audited. A committed
  turn that leaves the played character dead opens a core-owned `Succession` decision in
  `close_segment`; eligibility is "the swap leaves a game the engine still validates", checked by
  trial run, so there is no second rule table and Cairn plays it without writing a line. `take_over`
  moves only the played id; sheets, items and history keep pointing where they point. Dying alone
  still ends the game. `docs/24XX.md` deviation 1 re-narrowed to exactly the residue (mid-game
  character creation is not modelled), quoting the SRD's "Favor inclusion over realism".
- **Eval:** new `twentyfourxx/buy-the-vest` case (vest carried + credits charged, at the outfitter).
  Live smoke, 6 repeats: **6/6, 0 errors, 1.0 director calls** — the ship-enlarged `buy_gear`
  description passed the weak-model probe the schema-size lesson called for.
- **Eval rebuilt as the trust instrument, then baselined.** A review pass fixed a real vacuous-pass
  bug (`lost_a_roll` counted luck-test and NPC outcomes, silently forgiving `unless_lost` checks —
  now only the played character's own resolved rolls count) and grew the suite to 26 cases (12
  loner3e, 14 twentyfourxx) covering conflicts across hand-backs, non-living opponents, position,
  luck restore, locked ways, break budgets through Defence, help/hindrance, luck tests, the shop and
  ship upgrades, and death→succession; failing runs keep full director/narrator traces.
  **`phase2-baseline`: 220/234 (94%), 20/26 cases perfect** (`evals/results/phase2-baseline.json`).
  The misses are single-run model-judgment noise plus four provider-lottery errors (retry blowout,
  empty narrator, segment cap); the one weak expectation was `wait-out-the-tide`'s `bad-luck-rolled`
  at 44% — the Director narrated waiting without rolling the luck test. Fixed with one directive
  sentence at the decision point in `twentyfourxx/director.md` ("that turn is not free … call
  `roll_luck_test` instead of narrating the wait as safe"): re-run at 9 repeats, **44% → 100%**,
  0 errors (`evals/results/tide-directive.json`).

## Phase 3 — L6 Cairn Barebones — not started
## Phase 4 — L5 Fate Condensed — not started
