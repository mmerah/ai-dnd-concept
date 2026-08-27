# PLAN — SRD fidelity, engine shape, and two new engines

Five phases, in order. Each has a self-standing plan under `plans/`, concrete enough to implement
from. This file is the authority where those plans disagreed.

Progress is tracked in `PROGRESS.md`, one section per phase. Verify every phase with `uv run pytest && uv run ruff check && uv run ruff format --check &&
uv run basedpyright`, with `UV_CACHE_DIR` unset. Baseline is 253 passing.

Citations like `CAIRN-BAREBONES.md:204` are evidence gathered against the **pre-Phase-0** extractions.
Phase 0 replaces those files, so after it lands follow the official URL in the matching pointer file
(or `git show` the deletion commit) rather than the line number.

Standing rule for all five phases: **SRD fidelity outranks minimality.** Cutting an optional dial
or a GM-advice tool is fine. Cutting a rule a player would notice missing is not, however small the
diff. Every cut is recorded as a deviation.

| # | Item | Plan | Touches core? |
|---|------|--------|---------------|
| 0 | L0 — docs become pointers, not copies | `plans/L0-docs-as-pointers.md` | no |
| 1 | L3 — engine shape before the new engines | `plans/L3-engine-shape.md` | 1 signature + 1 hook |
| 2 | L4 — Loner 3e / 24XX rules compliance | `plans/L4-rules-compliance.md` | no |
| 2.5 | 24XX needs a scenario in its own genre | this file, below | no |
| 2.9 | Simplification pass — **must land before Phase 3** | `SIMPLIFICATION_PLAN.md` | yes: advisor deleted, one turn lifecycle, `SavedGame` folded, launch loses `engine` |
| 3 | L6 — Cairn Barebones engine | `plans/L6-cairn-barebones.md` | no |
| 4 | L5 — Fate Condensed engine | `plans/L5-fate-condensed.md` | no |

## Phase 0 — docs become pointers, not copies

See `plans/L0-docs-as-pointers.md`. `docs/24XX.md`, `docs/LONER-3E.md`, `docs/CAIRN-BAREBONES.md`
and `docs/FATE-CONDENSED.md` are near-verbatim SRD extractions (367 / 946 / 1476 / 1408 lines).
Each becomes a ~50–70 line file: official source URLs, explanatory guides, licence and the exact
required attribution string, per-pack source URLs, and this repo's deviation list carried over whole.

Why first, not after the phases that transcribe packs out of these files: transcribing a pack out of
*our* extraction bakes in whatever drifted during extraction. An implementer should build a pack
from the official page. Losing the transcription source is the point.

One blocking sub-step: Fate Condensed's CC BY 3.0 attribution paragraph exists only in the file
about to be deleted. Move it into `README.md` first, in the same commit.

## Phase 1 — L3

Behaviour-preserving. Three steps, down from five — two proposed steps were cut on review as
out-of-scope or not worth the churn, and the plan records why so they are not re-proposed.

1. `CharacterCreation.create(..., rng: Random)`, plus a page-held seed and a Reroll button in
   `ui/create.py` — Cairn rolls its whole character, and `create()` runs on every preview keystroke.
2. **A post-command engine hook**: `Engine.settle(draft) -> tuple[Fact, ...]`, merged into what
   `apply_to_draft` returns. It must **return facts** — `apply_play` builds every trace line, card
   and ledger entry from that tuple, so a `-> None` hook would drop the player to 0 HP silently —
   and it must be rng-free and idempotent, because the command's trial run executes it twice.
3. `ENGINES`/`ANSWERS`/`WON` **and the pinned `SCENARIO_ID`** in `evals/turn_eval.py` → reflected.
   `unless_lost` passes whenever an outcome is not in `WON`, so Cairn's and Fate's outcome words
   would make three of five shared cases vacuously pass.

The plan's other headline stands: the contract already carries per-engine mechanics state, seeding
of entities made in play, chained decisions and reflective discovery. It lists what needs no change,
so the next reader does not re-propose it.

## Phase 2 — L4

No drastic base-shape change; every gap is local to one engine's `rules.py`, `engine.py` or
`packs/srd.json`. Two are load-bearing:

1. **24XX gear does not exist in the pack** — costs, bulk and break budgets are printed rules, but
   today the Director invents item and price through `change_credits` + `gain_improvised_item`,
   which resolves rules model-side, and the project forbids that. Transcribe from the official SRD,
   not from `docs/24XX.md` (Phase 0 deleted it). `buy_gear` must slug against
   `draft.world.all_ids()` and call `draft.add`, or a second pistol collides on id. Break budgets
   ride an item trait `breaks-1..3`, **not** a `Mechanics` dict: `Engine.seed` never sees the pack
   entry, and `begin_game` appends starting kit with no seed call at all, so a dict leaves starting
   and authored gear at zero budget.
2. **24XX fires the defence decision on any failed attempt instead of on a hit** — code and our own
   `director.md:43` already disagree. Add `hit: bool` to `Attempt` as a **required** field: with a
   default of `False` a weak model quietly never fires the printed rule.

Everything else is a pack rename, a `breaks` counter, a dead-payload deletion, or a deviation line.
Both engines' dice maths is compliant as printed.

## Phase 2.5 — 24XX needs a scenario in its own genre

No plan file: the whole design is here, and it is one authoring conversation, not a code change.

**The problem.** 24XX's SRD pack is science fiction — cyber-ears, cranial jacks, hardsuits, low-G
jetpacks, flamethrowers, tranq guns. `drowned-road` is a tide-bell pilgrimage down a flooded
causeway. That mismatch was harmless while scenarios named several engines and 24XX also ran on
`whispering-vault`. Since the single-engine change it is load-bearing, because `drowned-road` is now
24XX's **only** scenario:

1. `buy_gear` ships the full catalogue in its tool description, so every Director prompt in that
   scenario offers a hardsuit and a cyber-limb to a pilgrim at a chapel. The model is being asked to
   choose from a list its own scene forbids.
2. `evals/turn_eval.py` therefore measures a weak model's tool choice against a catalogue the
   fiction cannot contain — the one place 24XX's numbers are supposed to be trustworthy.
3. The combat and defence coverage runs against `deel-hask`, a wrecker with a knife. The break
   budgets that Phase 2 built (`breaks-1..3`, vest through hardsuit) can never fire in that fiction.

**The work.** Re-author `drowned-road` as a 24XX-genre scenario, or author a replacement and retire
it. Use the `authoring-aidm` skill, which now takes `packs` and tells the author to read the pack
files before writing entity `rules`. The premise is free; the shape is not — it must keep everything
the eval and the engine already depend on:

- `engine: "twentyfourxx"`, `packs: ["srd"]`, `grows: true`.
- Four or so locations, with a far one reachable from the start, since the shared eval cases walk and
  climb between them.
- A companion NPC, a hostile, and an item the player carries.
- Any authored actor `rules` use skills drawn from the selected pack. 24XX opposition may omit a
  sheet and be expressed through behavior, risks, and obstacles.
- At least two `detail.when_reached` stage directions naming a real thread and stage, which the
  `Canon` record's stage expectations read.
- Gear the catalogue can actually sell, so `buy_gear` and the break budgets are reachable in play.

Then update that engine's entry in `evals/turn_eval.py`'s `CANON` with the new ids and stages.

**Not in scope.** `whispering-vault` stays loner3e and stays `settings.authoring.worked_example`.
`characters/kael/twentyfourxx.json` stays: Kael's brief was made scenario-agnostic — someone who
"comes wherever something old lies sealed" reads as well on a dead colony as in an abbey.

## Phase 2.9 — simplification before the new engines

`SIMPLIFICATION_PLAN.md` runs whole before Phase 3 starts. Two of its steps change what L6 and L5
write: an engine's advancement is one `advance_command(self.advancement)` line, not an
`advancement.md` plus a proposal fixture (Step 3); and `Engine.pack_type` is required (Step 2c). Read the
L5/L6 plans through that file where they disagree.

## Phase 3 — L6, Cairn Barebones

Five files under `src/aidm/engines/cairn/`, ~1,250 lines including the pack — not the 4,100–5,600
its doc estimated. Six commands. Most of Cairn is free: one `roll_save` covers every d20-under check
in the game, deprivation is a core trait plus one `if`, spellcasting is fatigue plus a save.

Restored on review, all printed rules a player would notice missing: **"all ten slots filled reduces
you to 0 HP"** (what the Phase 1 hook is for), and **multi-attacker and dual-wield keep-highest** —
without them three attackers deal three separate hits and Cairn fights are far deadlier than the
game. `roll_pool` already keeps the highest of a mixed pool, so that one is nearly free. NPCs get
rolled sheets from **both** `seed` and `opening_mechanics`; overriding only `seed` leaves every
scenario-authored monster at identical stats.

**Cairn is the proof Phase 1 worked:** it ships with no edit outside its own package except the
`create(..., rng)` signature, `characters/kael/cairn.json`, and `"cairn"` in two `world.json`s.

## Phase 4 — L5, Fate Condensed

Last because it is the largest. Two design calls carry it: a Fate aspect **is** a core `Trait` (so
consequences, boosts and situation aspects are free, and a Fate scenario is today's `world.json`),
and opposition is **judged by the Director on the call**, not statted. Five commands, three
decisions.

Five fidelity failures were caught across two review rounds and corrected in the plan before it got
here: **three** free stunt slots (not one); concede offered **before** the roll, and as a
`Concede(Action, Decision)` so declining still has an action to roll; create-an-advantage keeps its
second branch; the **reroll** half of invoke ships (cutting it halves the mechanic Fate is named
for); and one hit can be absorbed across **two** consequences. Steps 4, 5, 6, 8 and 14 carry them.

## Where the plans disagreed

These three are settled; the plans below already reflect them. Recorded so they are not re-litigated.

1. **`Engine.advancement` optional?** No — but not for the reason first recorded here. The Cairn doc
   was not "wrong about its own game": it correctly frames Training as a *downtime procedure* gated
   by Master, Costs and Milestones, which L6 cuts. Mandatory `advancement` still stands; what needs
   fixing is L6's chapter command granting a free ability per expedition with no master and no cost
   while its own `occasion` string says "has trained between expeditions". Fix the string, record
   the deviation.
2. **Where do the dice and decision changes land?** Split. The summed-dice work is Fate's alone and
   stays in Phase 4. The `Decision` default option is **deleted outright**: `turn/run.py:291-302`
   already hands the consumed decision back as `deps.answered` on free text, which is exactly how
   `twentyfourxx/engine.py:82 _settle_defence` turns "I raise my medkit" into the right item. A
   default option would override that with "take the hit" — a 24XX regression, not a self-paying
   cleanup. Fate copies the settle shape instead, which revives L3's `answered_as` prediction.
3. **Post-command engine hook for carried items?** **Reinstated** — I cut this and was wrong. I read
   two "nice-to-haves"; it is the printed encumbrance rule, cut only because `Engine.validate` may
   refuse but never write. Three lines at `engines/core.py:388`. Now Phase 1 item 2.

## Settled: the Cairn trait-slug convention

**Approved.** Cairn item mechanics are read off a slug convention on `Entity.traits` —
`^(petty|bulky|d(4|6|8|10|12)|armor-[1-3])$` — so authored canon, starting kit and improvised items
all get weapon dice, armour and slot size through the channel that already exists; 24XX already does
this with `bulky`/`broken`. Two guards ship with it, because core `add_trait` is in the Director's
vocabulary and the model could otherwise write `d12` onto a dagger: `CairnEngine.validate` refuses
more than one die-mark per item, and `director.md` reserves the mark slugs. The `Mechanics.items`
fallback is not built.

## Scenarios

**Superseded by the single-engine decision (2026-08-26).** This section previously read "`Scenario`
has no per-engine field, so a per-engine scenario is the same JSON with a different `engines` list
... There is nothing to design", and kept `whispering-vault` multi-engine as the shared fixture.
That is no longer true and the reasoning is recorded here so it is not re-proposed.

A scenario names exactly one engine (`Scenario.engine`), and its entities carry that engine's
authored values (`Entity.rules`). The multi-engine form could not express mechanics at all: every
non-player entity was born with a blank sheet, so a trained scribe and a bloated rat rendered
identically to the Director. Item 3 below already saw half of this — a scenario carrying `d8` or
`armor-2` leaks meaningless traits into every other engine's prompt — and the answer is structural,
not a matter of which scenario ships where.

1. `whispering-vault` is `loner3e` and stays `settings.authoring.worked_example`. `drowned-road` is
   `twentyfourxx` and gained a hostile actor so the engine has combat and defence eval coverage.
2. Still true: author one single-engine scenario per new engine, after that engine's phase ships and
   its `characters/kael/<engine>.json` overlay exists. Cairn takes `grows: true` and the opening
   slice only. `characters/kael/cairn.json` and `kael/fate.json` stay mandatory in L6 and L5 —
   `settings.authoring.starter_character = "kael"` needs them for any authoring run, not only play.
3. `evals/turn_eval.py` holds a per-engine `Canon` record naming each engine's scenario and the ids
   its shared cases reach for. A new engine adds one entry; `cases_for` still raises for an engine
   that declares nothing.
4. `Scenario.packs` always includes `srd` and names every additional pack used by the scenario.
   Authoring receives the selected, validated pack content; game startup rejects packs that are no
   longer installed, and each engine validates the authored vocabulary it owns.
5. `SheetBase.packs` does the same per entity and may name several selected packs. A mechanically
   singular choice gets its own accurate field; Loner uses `twist_pack` for its Oracle table.

## Not in scope

Tests are not a focus of any phase: correct them minimally to keep the suite green, and do not
design test work into a plan. L1, L2, L7, L8, L9 and I1–I5 stay in `IDEAS.md` at their existing
positions; L7 onward follows Phase 4.
