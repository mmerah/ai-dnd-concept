# L4 — Loner 3e / 24XX rules compliance

Sources: the farirpgs mirrors of both games (Loner: introduction, make-your-protagonist, start-your-game,
consulting-the-oracle, conflicts, determine-the-mood; 24XX: rules, characters), checked against the official
SRDs at <https://24xx-srd.carrd.co/> and <https://lonersrd.zotiquestgames.com/core/loner-3e.html>. L0 has
replaced `docs/24XX.md` and `docs/LONER-3E.md` with pointer files, so transcribe from the official pages.

Verify with `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`.
Tests are not a focus: correct them minimally to stay green.

## Headline

**No drastic contract change is needed.** Every compliance gap found is local to one engine's `rules.py`,
`engine.py`, or `packs/srd.json`. The one contract-shape hole L4 surfaced (step 1) is not a gap in either
shipped engine — it is a Cairn blocker, so it belongs in L3 while the contract is open.

The reason nothing else reaches `engines/core.py`: a `Mechanics` subclass may already add any field
(`loner3e.rules.Mechanics.twist` proves it), `Engine.seed` already fires for **every** created entity of any
kind (`core._seed_created`), and engines already declare their own commands. Per-item mechanics — 24XX break
budgets, Cairn slots and damage dice — and a gear-purchase command all fit inside an engine today.

## Contract shape (do inside L3)

1. **Character creation cannot roll dice.** `CharacterCreation.create(name, brief, picks)` in
   `src/aidm/engines/core.py` takes no `Random`, and `state/creation.py` offers only pick and text steps.
   Loner and 24XX both create without rolling, so both are compliant — but Cairn Barebones rolls 3d6 for
   STR/DEX/WIL, d6 for HP, and rolls starting gear. Add `rng: Random` to `create` while L3 is already in the
   contract — three definitions (`core.py`, both engines) and two calls, both in `ui/create.py:86,109` —
   rather than after L6 forces it.

## 24XX — gaps, most load-bearing first

2. **The gear catalogue does not exist.** SRD: "Take a comm and ₡2. Most items and upgrades cost ₡1 each",
   then four lists (Armor, Cybernetics, Tools, Weapons) with costs, bulk, and break budgets.
   `packs/srd.json` ships `starting_kit` (comm) and specialty kits only; nothing is purchasable and no price
   is resolver-side. Today the Director invents both the item and its cost through `change_credits` +
   `gain_improvised_item` ("ordinary, unimportant object") — model-side rules, which the project forbids.
   Minimal: add `gear: tuple[GearItem, ...]` to `twentyfourxx.rules.Pack`, where `GearItem` is `KitItem`
   plus `cost: int = 1` and `breaks: int = 0`. Transcribe the four gear lists (Armor, Cybernetics, Tools,
   Weapons) from the official SRD at <https://24xx-srd.carrd.co/> § Gear into `packs/srd.json`, keeping the
   printed costs, `bulky` marks and break budgets; the SRD's `₡1` default and its "ignore microcredit
   transactions" line set `cost`'s default. Add a `buy_gear` command in
   `src/aidm/engines/twentyfourxx/engine.py` that charges `cost` through `apply_change_credits` and writes
   the item's `bulky` and `breaks-N` marks as traits (step 3).
   **Do not land the item through `_carried` as-is** (`twentyfourxx/engine.py:246`): it returns
   `Entity(id=EntityId(entry.id), …)` and nothing else, and `Game.add` (`state/model.py:232`) raises on a
   duplicate id, so buying a second pistol fails. Follow `actions.improvise` instead — slug against
   `draft.world.all_ids()`, then call `draft.add(item)` so the purchase lands as an `entity_created` fact.
   Why: prices and bulk are rules, so they belong in the pack.

3. **Armour that breaks up to 3× cannot.** SRD: vest breaks once; battle armor (₡2, bulky) and hardsuit (₡3,
   bulky) "break up to 3×"; the Android's case "breaks harmlessly for defense". `rules.BROKEN` is a boolean
   trait and `resolve_defence` refuses an already-broken item, so every item breaks exactly once.
   Minimal: carry the budget as a **reserved item trait** `breaks-1` / `breaks-2` / `breaks-3`, the same
   mark convention 24XX already uses for `bulky` and `BROKEN` and that L6 formalises for Cairn.
   `resolve_defence` rewrites `breaks-N` → `breaks-(N-1)` and writes `BROKEN` at zero; `_defence_decision`
   filters on a remaining `breaks-N` rather than on the absence of `BROKEN`. Reserve the slugs in
   `director.md` so the model does not write them as flavour.
   **Not `Mechanics.breaks: dict[EntityId, Counter]`**, which an earlier draft proposed: `Engine.seed`
   receives an `Entity`, not a `GearItem`, so it cannot recover `GearItem.breaks`, and `begin_game` appends
   `character.profile.items` straight into `world.entities` (`engines/registry.py:60`) with no fact and no
   `seed` call — so starting kit and scenario-authored gear would be born at zero budget and be unusable.
   A trait travels with the entity through all three paths (bought, starting, authored) for free.
   Why: the break budget is a number the rules print; a boolean cannot hold it.

4. **The defence decision fires on every failed player attempt, not on a hit.** SRD: "Say how one of your
   items breaks to turn a hit into a brief hindrance." `rules.resolve_attempt` suspends on any player
   `disaster`/`setback`, so a botched hack offers "break the medkit" against a triggered alarm. Our own
   `director.md` already says "When the player suffers a hit" — code and instruction disagree.
   Minimal: one **required** field on `Attempt` — `hit: bool`, described as "True when a bad roll means
   physical harm to the actor" — and gate the `draft.pending = _defence_decision(...)` line
   (`twentyfourxx/rules.py:364`) on it. Required, not `= False`: a weak model omits an optional flag, and the
   printed defence rule would then quietly never fire — the opposite failure to the one being fixed.
   Files: `src/aidm/engines/twentyfourxx/rules.py`. Why: the printed trigger is a hit, not a failure.

4b. **Delete `Defence.outcome`** (`twentyfourxx/rules.py:229`). Written at `:335`, read nowhere. Free.

5. **The Android's case** — half of deviation 1. Steps 2 and 3 make it representable (an item carrying
   `breaks-1`), but it is **not** a one-line pack edit as an earlier draft implied: `Origin`
   (`twentyfourxx/rules.py:118-125`) has `increases`, `traits` and `invents` and **no `kit` field at all**,
   unlike `Specialty`. The SRD also prints it as an either/or — "Take synth skin (looks human) **or** a case
   (breaks harmlessly for defense)" — so it needs a choice step too.
   Decide one of two, do not leave it implicit: **(a)** add `kit: tuple[GearItem, ...]` to `Origin` plus a
   kit-choice creation step, which also unblocks Muscle's sword/firearm/cyber-arm pick and closes deviation 1
   entirely; or **(b)** keep deviation 1 whole and say in `docs/24XX.md` that origin and specialty kit picks
   are the Director's fiction. (b) is the transcription-phase answer; (a) is right if you want deviation 1
   gone. Why: the case is the one piece of that deviation the gear work nearly removes for free.

6. **Starships are not modeled** and are not listed as a deviation. SRD gives a ship six functions with ₡10
   upgrades and "in an emergency, players pick a function to do or help with".
   Minimal: no code — one entry under **Deviations in this repo** in the L0 pointer file `docs/24XX.md`,
   saying a ship is a world entity with traits and its functions are the Director's fiction. Why: that file
   states nothing diverges silently, and this diverges silently.

7. **"If killed, make a new character to introduce ASAP" has no path.** `turn/run.py` refuses to continue
   ("the player is dead. The only way on is to restart"). Minimal: no code — record it as a deviation in
   `docs/24XX.md`. Why: a replacement-character flow is a core feature, not a 24XX rules fix.

8. Compliant as printed, one line each: skill die d6/d8/d10/d12 with d4 when hindered (`pool_faces`); take
   highest (`roll_pool`); 1–2 disaster / 3–4 setback / 5+ success (`outcome_for`); one help die, ally's own
   skill die or a flat d6 (`_one_help_die`); advancement = one skill step plus d6 credits
   (`TwentyfourxxAdvancement.grant`); bad-luck test 1–2 trouble / 3–4 signs (`_bad_luck`); revise-before-
   committing (`stake_attempt`); specialties, origins and the 17-skill list (`packs/srd.json`); ₡2 start.

## Loner 3e — gaps, most load-bearing first

9. **`packs/srd.json` is labelled as the SRD's own tables but is not.** Its `name` is "Core tables" and its
   `source` is `lonersrd.zotiquestgames.com`, yet Loner 3e publishes **no** concept, skill, frailty or gear
   tables — those five/six/five/six entries were written for this repo. Only `twist_subjects` and
   `twist_actions` are the SRD's (and the `license` line correctly says so).
   Minimal: rename the pack to something like "Starter tables", set `source` to this repo, keep the twist
   table's CC BY-SA credit unchanged, and note it under **Deviations in this repo** in `docs/LONER-3E.md`.
   Zero code. Why: attribution accuracy, and the next engine copies whatever this pack does.

10. **Non-living characters have no sheet, so no conflict can be fought against one.** SRD "Everything is a
    Character" gives objects, vehicles and curses a Concept, Skills, Frailties and Luck; `resolve_question`
    routes `opponent_id` through `require_actor_here`, so a Harm & Luck conflict against a ship or a curse is
    refused. This is deviation 2 in `docs/LONER-3E.md`, so it is known, not silent.
    **Note the reverse problem:** deviation 2 as written claims a non-living character *gets* a sheet the
    first time an engine needs one. It never does — `SheetEngine.seed` returns early unless
    `entity.kind == "actor"` (`engines/core.py:330`). So either take this step and make the claim true, or
    reword the deviation in L0. One of the two is mandatory; the step itself stays optional.
    Minimal if taken: `SheetMechanics.sheets` is already keyed by `EntityId`, so override `opening_mechanics`,
    `seed` and `validate` in `src/aidm/engines/loner3e/engine.py` to cover items too (all three currently
    filter on `of_kind("actor")`), and swap the `opponent_id` lookup to an "entity here" check. No core
    change. Optional — the deviation is defensible; take it only if you
    want vehicle and object conflicts. Why: it is the one printed Loner rule the engine refuses outright.

11. **Two sources disagree on the tie result; we follow the official one.** The farirpgs mirror reads "If
    both are equal, the answer is **Yes, and...**", downgraded to "Yes, but..." only while the Twist Counter
    is under 3. The official SRD (<https://lonersrd.zotiquestgames.com/core/loner-3e.html> — Step 1, the
    Resolution Breakdown, the Appendix B matrix and the Cheatsheet, four places) reads equal → **Yes,
    but... +1 Twist** unconditionally, which is what `rules.outcome_for` does. Minimal: one line under
    **Deviations in this repo** in the L0 pointer file `docs/LONER-3E.md` recording the mirror's divergence.
    Why: so it is not re-litigated when someone reads the mirror next.

12. **The "twists land one turn late" note is stale — they do not.** `rules._twist` writes to
    `world.pending_notes`, and `core.apply_play` appends `pending_notes[already_pending:]` to the same tool
    call's answer, so the Director gets the pairing in the call that rolled it, as deviation 3 says. No change.

13. Compliant as printed, one line each: 1 Chance d6 vs 1 Risk d6, advantage/disadvantage adds one die of
    that colour, keep highest, hard cap of two and no stacking (`_pair` + the `Position` literal, which makes
    cancellation structural); both ≤3 → but / both ≥4 → and (`RULES.but_at` / `and_at`); the six outcomes;
    Harm & Luck 3/2/1 (`Outcome.harm`); the Twist Counter at 3 with a 2d6 subject × action table read from
    the player's pack; ties never tick the counter inside a Harm & Luck exchange; Luck 6, defeat at 0, and
    both pools reset after the conflict (`_strike`, `apply_restore_luck`); the 8-step protagonist recipe;
    post-adventure growth of up to four changes.

## Deliberate deviations we keep

- The GM is an AI. Every judgment the SRD hands the solo player — when to ask the Oracle, whether a tag gives
  an edge, the next scene's mood, Sibylline reinterpretation, when a job or adventure has closed — lives in
  the Director's `director.md`, not in a die roll.
- Every table resolves resolver-side. The model names the question and the position; dice, twist pairings,
  bad-luck tests and credit payouts are rolled in Python and handed back.
- Loner: Goal, Motive and Nemesis are world threads and entities, not sheet fields.
- Loner: one game-wide Twist Counter, hidden from the player.
- Loner: a twist arrives inside the answer to the call that rolled it, not as a scene interruption.
- Loner and 24XX: the SRD's inspiration tools (Adventure Maker, 5W+H frame, open-ended tables, d20 detail
  tables, the d6 job-finding roll) stay authoring-time — scenarios here are authored ahead of play.
- 24XX: help is one die at most, and "more than one bulky item **may** hinder you" stays a Director ruling.
