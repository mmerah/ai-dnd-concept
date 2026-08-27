# L5 — Fate Condensed engine

Source: the official SRD at <https://fate-srd.com/> (CC BY 3.0 Unported, Evil Hat); L0 replaced
`docs/FATE-CONDENSED.md` with a pointer file and moved its required attribution paragraph into
`README.md`. Copy that paragraph verbatim into `packs/srd.json` and the head of `director.md` — CC
BY 3.0 requires it wherever our copyright appears, at the same size.

Assumed: L3 leaves `Engine`/`SheetEngine`/`Decision`/`Command` shaped as today apart from
`create(..., rng)` and the `settle` hook; L4 touches only loner3e/24XX numbers, which nothing here
reads; L6 lands first, so a fourth `engines/*/` package is a proven path. The one core change Fate
needs is at the end and lands in this phase.

Verify with `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`.
Tests are not a focus: correct them minimally to stay green.

## The two design decisions

**A Fate aspect is a core `Trait`.** Character aspects, situation aspects, consequences and boosts
are all `Trait{id, name, text}` on an actor, a location or an item. Free: authored NPC/location
aspects in existing `world.json` files, `add_trait`/`remove_trait` already in the Director's
vocabulary, aspects already rendered per entity in both prompts (`turn/context.py: entity_state`),
trait badges already in `ui/panels.py`. **No scenario overlay is needed** — a Fate scenario is an
ordinary `world.json` declaring `"fate"` in `engines`, with its aspects authored as traits. (It
should declare Fate *alone*: aspect traits rendered into another engine's prompt are noise. See
step 17.) A trait cannot hold a free-invoke count, so
`Mechanics` keeps `invokes: dict[EntityId, dict[Slug, int]]` and `validate()` refuses an orphan.

**Opposition is judged, not statted.** Only the player carries skills; for any other actor the
Director names a ladder rating on the call (`opposition`, `rating`) — the SRD's own "set difficulty
/ minor NPCs get one or two skills", collapsed into the judgement the model already makes for
`position` (loner3e) and `hindered` (24XX). NPC sheets hold stress and consequence slots only, so
the inherited `seed()` covers actors made in play.

## Steps

1. `src/aidm/engines/fate/rules.py` — `Sheet(SheetBase)`: `high_concept: Slug = HIGH_CONCEPT`
   (trait id of the one aspect a breakthrough may not rewrite; aspects are traits, so the sheet keeps
   no copy). **It needs a default**: `SheetEngine.seed` (`engines/core.py:333`) and
   `opening_mechanics` (`:302`) build `self.sheet_type()` for every non-player actor and `Slug`
   rejects `""`, so an undefaulted field raises on the first NPC made in play.
   `skills: dict[str, int]`, `stunts: tuple[str, ...]` (**three**, see step 14), `fate: Counter`,
   `refresh: int = 3`, `physical: Counter`,
   `mental: Counter` (current = marked boxes), `consequences: dict[Severity, Slug]` naming the trait
   in each filled slot, `breakthroughs: Counter`. `def rows(self) -> tuple[tuple[str, str], ...]`
   renders Skills as `Fight +4 (Great)` / Stunts / Fate Points / Stress / Consequences; the aspects
   are already the trait badges above the rows. `def rating(self, skill: str) -> int`.
2. Same file — `Severity = Literal["mild", "moderate", "severe"]`, absorbed shifts `2 * (index + 1)`
   off `get_args` as 24XX derives `LADDER`; `Mechanics(SheetMechanics[Sheet])` adds `invokes`;
   a `Rules` frozen dataclass holds the numbers, as both engines do.
3. Dice — `def roll_fate(reason: str, rng: Random, label: str) -> tuple[DiceEvent, Fact]`, four
   dice summed. Do the core change at the end of this file first: `DiceEvent` requires `kept in
   rolled` and `_dice_group` renders `d{face}` per die, so 4dF has no honest representation today.
4. `Action(Frozen)` — the Director's one roll: `actor_id`, `action: Literal["overcome",
   "create_advantage", "attack"]`, `goal`, `skill` (player only, must be on the sheet),
   `rating: int` (non-player actor's ladder value), `target_id: CheckedEntityId | None`,
   `opposition: int` (static difficulty, or the target's defence rating), `defence_skill: str`
   (when the target is the player), `stunt: str` (must be one of the sheet's three stunts, +2), and
   **both** branches of create-an-advantage: `aspect: str` (title-case name a new aspect would take)
   **and** `aspect_id: Slug | None` (an existing, possibly unknown, aspect the roll takes advantage
   of). The SRD prints both branches with their own four outcomes; an earlier draft had only the
   first and did not list the second as a cut. The second branch is short because `Mechanics.invokes`
   already exists. Exactly one of the two is set for `create_advantage`. A `model_validator`
   refuses `skill` and `rating` together, as `Attempt._one_help_die` does. Defend is never called:
   the resolver rolls it whenever `target_id` is set — the SRD's own removal of active opposition.
   **Write the three cases out as a table in the field descriptions and refuse every other combination
   in the `model_validator`** — this is model-facing schema text, i.e. runtime behaviour:
   | case | `skill` | `rating` | `target_id` | `opposition` | `defence_skill` |
   |---|---|---|---|---|---|
   | player acts vs static difficulty | set | — | — | set | — |
   | player acts vs an NPC | set | — | set | — | — (NPC defence rating goes in `opposition`) |
   | NPC acts vs the player | — | set | player | — (derived from the sheet) | set |
   Four overlapping rating fields with one validator is the single most likely place a weak model
   produces a wrong roll.
5. `def resolve_action(draft: Game, one: Action, rng: Random) -> tuple[Fact, ...]` — **first**, if
   the player is the target and could concede, pend the concede offer *before rolling* (step 8) as
   `class Concede(Action, Decision)` with `kind = "concede"`, mirroring `StakedAttempt(Attempt,
   Decision)` (`twentyfourxx/rules.py:189-197`). It **must** subclass `Action`: a plain `Frozen`
   payload leaves declining the concession with nothing to roll from, and the action is simply lost.
   Its `resolve` on the decline option runs the roll below;
   then reveal actor and target, roll both sides, land the dice facts, then: if the player is on
   either side and has a fate point or a free invoke in reach, set `draft.pending` to `Invoke(...)`;
   otherwise call `_finish`. `rule("roll_action", ..., Action, resolve_action)`.
   Pausing on nearly every roll while the player holds a fate point is rules-faithful and is what
   Fate is. It will exceed `SEGMENT_CAP = 4` — **raise that**: it lives only at `evals/turn_eval.py:27`
   and nothing in `src/` reads it, so it is a test-harness number, not a product limit, and this plan
   does not trade a printed rule for one. If the pause is still narrowed for turn pacing, justify it
   as UX and record it as a deviation — never cite the cap as the reason.
6. `class Invoke(Action, Decision)` — `kind = "invoke"`, carrying `actor_roll: DiceEvent`,
   `defence_roll: DiceEvent | None`, `bonus: int`, and `candidates: tuple[InvokeOption, ...]`
   (entity id + trait id + free or paid); `DecisionOption.id` is the candidate's index
   (`invoke-0`), so an aspect held by another entity is unambiguous. **Two options per candidate**,
   `invoke-0` and `invoke-0-reroll`: the SRD prints both halves of the same mechanic — "you can
   either gain a +2 bonus to your roll or reroll all four dice". `def resolve(self, draft,
   option_id, rng)` spends a fate point or decrements `invokes`, then either adds +2 or re-rolls the
   4dF, and re-pends itself with the remaining candidates (a second invoke is one more click, no
   extra code) or `_finish`es. The reroll branch costs nothing extra because the re-pend loop already
   exists. Cutting it would halve the one mechanic Fate is named for.
7. `def _finish(draft: Game, roll: Invoke, rng: Random) -> tuple[Fact, ...]` — effort minus target
   gives shifts and one of fail / tie / success / success-with-style, then per action: overcome
   writes facts only (SwS adds a boost trait); `create_advantage` calls `state.actions.add_trait`
   for `roll.aspect` on the target (or the location, for a situation aspect) with 1 or 2 free
   invokes, tie gives a boost, fail gives the opposition the free invoke; attack on success calls
   `_absorb`. One `MechanicEvent(badges=skill+difficulty, dice=both rolls, outcome=...)` attached
   to the outcome fact, exactly as `resolve_question` does.
8. `def _absorb(draft, defender, shifts, rng) -> list[Fact]` — mark stress boxes first (`adjust`);
   if any shift is left, the player gets `Absorb` pending (one option per free consequence slot
   covering the remainder, plus `taken-out`) while an NPC takes the mildest slot that covers it or
   is taken out. `class Absorb(Decision)` carries `defender_id`, `left`, `why`; `resolve` writes the
   consequence trait (named after `why`, e.g. `Gaping Chest Wound`), fills the slot, and hands the
   attacker a free invoke on it. **Then it re-pends itself with the remaining shifts and the still-free
   slots**, exactly as `Invoke` re-pends — the SRD allows absorbing one hit across two consequences
   ("even if he were to take a mild and a severe consequence at once, absorbing eight shifts"), and
   without it a hit two slots could survive takes the player out instead. Three lines; `left` already
   carries the remainder. `taken-out` stays the last option. Taken-out writes a `pending_note` naming who sets the terms of the
   exit, mirroring `defeat_note`.
   **Concede is NOT an option here.** The SRD § Conceding: "You must concede before your opponent
   rolls the dice… that's poor form." Offered inside `Absorb` — after the shifts are known — it is a
   paid undo of a bad roll, which inverts the rule. Offer it in step 5 before the roll, in the shape
   `resolve_stake` (`twentyfourxx/rules.py:287`) already has, or cut it and record the cut. Concede
   pays 1 fate point plus one per consequence **taken in the current conflict** — not per consequence
   carried — so the conflict's consequences must be distinguishable from older ones.
9. `class Compel(Decision)` — `kind = "compel"`, `aspect_id`, `complication`. Options `accept`
   (+1 fate point and a `pending_note` to develop the complication) and `refuse` (spend 1, offered
   only when the player holds one), set by `command("offer_compel", ..., CompelOffer, ...)`.
   The only fate-point income in v1, so not optional.
10. `action("clear_stress", "Clear an actor's stress once the scene is over.", ...)` calling
    `adjust` back to zero, twin of `apply_restore_luck`. `rule("treat_consequence", ...,
    Treatment, resolve_treatment)` — an overcome roll against 2/4/6 by severity, +2 treating
    yourself; success rewrites the trait (`remove_trait` + `add_trait`) and clears a mild slot,
    moderate and severe wait for the breakthrough.
11. The engine's own chapter command, not `chapter_command`: `complete_chapter(draft, "the story
    arc has closed")` plus `adjust` of `fate` up to `refresh` — the SRD's per-session refresh, on
    this app's only session boundary.
12. `src/aidm/engines/fate/engine.py` — `class FateEngine(SheetEngine[Sheet])` with
    `id = EngineId("fate")`, `badge = ("FATE", "deep-purple-7")`, `engine_dir`, `sheet_type`,
    `mechanics_type`, `decisions = (Invoke, Absorb, Compel)`; `def validate(self, state: Game) ->
    None` calls `super()` then checks every `invokes` entry and filled consequence slot still names
    a live trait — which is also what refuses a Director `remove_trait` on a consequence, with a
    message pointing at `treat_consequence`.
13. `class FateAdvancement(SheetAdvancement)` — `grant` must **resize the stress tracks** when a
    breakthrough moves Physique or Will across a band (+0 → 3 boxes, +1/+2 → 4, +3/+4 → 6), the same
    banding step 14 applies at creation. `proposal_type = Breakthrough`, `ledger_key =
    "breakthroughs"`, `occasion = "reaches a breakthrough"`, `def ledger(self, state, subject_id)
    -> Counter`, `def grant(self, draft, subject_id, proposal, rng) -> tuple[Fact, ...]`.
    `Breakthrough(ProposalBase)`: `lateral: Lateral` (swap two skills / replace an Average skill /
    rewrite an aspect other than the high concept / rewrite one stunt), `raise_skill: str`, `why`.
    `grant` refuses a raise breaking the column rule and clears moderate/severe consequences.
14. `class FateCreation(PackCreation[Pack])` — `steps_for` yields `TextStep`s for high concept,
    trouble and two free aspects, four `CreationStep`s over `pack.skills` choosing 1 Great /
    2 Good / 3 Fair / 4 Average, and **three** `TextStep`s for stunts — the SRD: "Your character
    begins with three free stunt slots." One stunt is not Fate; a player sees the difference before
    play starts, and `stunts: tuple[str, ...]` costs under ten lines over `stunt: str`. **Set
    `max_length` on those three `TextStep`s** — it defaults to 100 (`state/creation.py:40`) and a
    stunt sentence does not fit. `create` must also refuse the same skill being chosen in two of the
    four pyramid steps: `_check_chosen` only de-duplicates within a single step.
    `create` writes the pyramid into
    `skills`, sizes `physical`/`mental` from Physique/Will (+0 → 3, +1/+2 → 4, +3/+4 → 6), sets
    `fate` and `refresh` to 3, and returns each aspect as a `Trait` on the `CharacterProfile`, so
    every aspect is invokable from turn one.
15. `src/aidm/engines/fate/packs/srd.json` — `Pack(Frozen)`: `name`, `source`, `license`, the 19
    skills as `CreationOption`s with their SRD blurbs, `ladder: dict[str, str]` (rating to
    adjective). No adjective table in Python; a later pack swaps the skill list without touching a
    resolver.
16. `director.md` (~90 lines) — fiction first; when to roll; the four actions and their outcome
    tables; aspects are true and are traits, so `add_trait` writes a situation aspect the scene
    already has; one exchange per turn; locations are zones; compel the trouble when the story
    turns on it; a thread clock is how a contest runs. The breakthrough's rules text is a `text`
    class var on `FateAdvancement` (a `GROWTH`-style constant in `rules.py`), not a separate file.
17. `characters/kael/fate.json` — mandatory, since `settings.authoring.starter_character` is `"kael"`
    (`config.py:70-71`), so every future authoring run needs it. Add an `engines/fate/` row (CC BY 3.0,
    Evil Hat) to the README licensing table (`README.md:129-131`) and drop "planned" at
    `README.md:14-17`. Do **not** add `"fate"` to the two existing multi-engine scenarios: aspects are
    traits, so a Fate scenario's aspect traits would render into every other engine's prompt. Fate gets
    its own single-engine scenario, authored with the `authoring-aidm` skill after this phase — see
    PLAN.md § "Scenarios". Correct the existing tests minimally to stay green; do not design new ones.

## Cut from v1 (add when …)

Nothing here is a rule a player would notice missing. Five things earlier drafts cut or dropped
*were*, and all five are back: three free stunt slots (step 14), conceding before the roll (steps 5
and 8), the take-advantage-of-an-existing-aspect branch (step 4), the reroll invoke (step 6), and
absorbing one hit across two consequences (step 8).

- **Hostile invocations** — add when compels alone prove too thin an income; needs a deferred
  payout the save must carry.
- **GM fate-point pool, stunts beyond the free three, buying stunts with refresh, the SwS
  shift-for-boost trade** — add when the first long game shows the sheet or a fight wanted them.
  (The Superb+ extra mild slot is **not** cut: it is printed and step 1's `consequences` already
  holds it. Nor are the reroll invoke or absorbing one hit across two consequences — both are
  printed core and ship in steps 6 and 8.)
- **Milestones** (only breakthroughs ship, one per chapter) — add when the app grows a boundary
  smaller than a chapter.
- **Challenges, contests, turn order, teamwork bonuses, zones-as-a-map** — thread clocks already
  run a contest and locations already are zones; add only if play proves otherwise.
- **Relationship aspect** (one-PC game), **conditions, scale, weapon/armor ratings, extreme
  consequences, countdowns, big-bad rules** — pack dials, per the SRD's own framing.

## Core change this phase carries

Surfaced by L3 and deferred to here: Fate is its only consumer, so it lands with its caller rather
than as speculative contract work three phases early.

**Summed dice.** `state/actions.py: roll_pool` keeps the highest die and `DiceEvent` validates
`kept in rolled`; `ui/game.py: _dice_group` renders `d{face}` per die. Fate needs a summed result
and a signed face. Be explicit about the representation, because the halfway version does not work:
- `faces = (3, 3, 3, 3)` and `rolled` stays `1..3`, so the per-die range check in
  `_rolled_matches_faces` (`state/facts.py:28`) keeps passing — **keep that check**, only the
  `kept in rolled` clause goes.
- `kept = sum(die - 2 for die in rolled)`, so it may be zero or negative. `DiceEvent.kept` stops
  meaning "the die that was kept"; say so where it is defined.
- Add the combine mode to `roll_pool` and a face label that renders `+ 0 − +`.
- `_dice_group` highlights `value == die.kept` (`ui/game.py:118`), which matches nothing once `kept`
  is a sum — drop or re-key that highlight.
Cairn's dice are all single, so nothing before this phase needs it.

**Deliberately NOT done: a default option on `Decision`.** An earlier draft asked for one so a
free-text answer could complete a pending roll. It is unnecessary and it regresses 24XX:
`turn/run.py:291-302` already hands the consumed decision back as `deps.answered` on free text, and
`twentyfourxx/engine.py:82 _settle_defence` uses exactly that to turn "I raise my medkit" into the
right item. A default option would override that with "take the hit". Copy the `_settle_defence`
shape for Fate's three settle points instead, then lift `answered_as(deps, kind)` as L3 predicts.

Nice to have, not blocking: a hook letting an engine refuse or clean up a core `remove_trait`.
Without it, `validate()` raising a clear message is the refusal path, which works today.
