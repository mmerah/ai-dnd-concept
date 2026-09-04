# NEXT-SPECS — after the hub

Tracks A through F of the 2026-09-02 brainstorm became `PLAN.md` and were cut from this file;
Track R (the seam refactor) became PLAN.md Phase 5 the same day and was cut too. What stays:
the maintainer's decisions, Track G (the party, then crews), and what was left in `IDEAS.md`
or refused. Track G becomes its own `PLAN.md` when PLAN.md's seven phases have landed and the
campaign has been played through once with the recap. Counts and names below are as written
on 2026-09-02; the code after Phase 2 is the reference for the party helpers Track G quotes
(`check_party`, `join_party`, `leave_party`, `Person`).

## Decisions made in the brainstorm (the maintainer's, 2026-09-02)

1. **One scene engine, three payloads.** `engines/scenes.py` may take pydantic type parameters
   on the cast and player types. PLAN.md settled 7 ("no type parameter") retires with PLAN.md.
   Loner's player leaves the cast and lives as `world.player`, as in 24XX and Breathless; Loner
   saves go stale, which the design allows.
2. **Memory is a recap the worldsmith writes on the crossing.** No summarizer role. The
   window is `SCENE_EXCHANGES` in `core/views.py`, 20, a constant and not a setting. The
   summary at the return and the three depths landed 2026-09-03; "no summarizer role" stands.
3. **Voices are an HTTP provider on the illustration pattern**: off by default, the OpenRouter
   key the player already has, a local server if they run one, and the narrator's voice chosen
   per scenario as its art style is. No in-process model.
4. **The tool cap stays fifteen, counted as tools plus `change_world` arms**, the two party
   arms every engine carries (Track A) not counted. An engine whose SRD plays a crew (Track G)
   may go to twenty in all; its `docs/<ENGINE>.md` says so. No fold is made for the count's
   sake. Since 2026-09-04 the cap reads: at most fifteen engine tools plus `commission`, the
   platform's, counted as tools plus `change_world` arms, the two shared party arms not counted.
5. **Campaign refinements are all built**, except moving home, which stays in `IDEAS.md`.
6. **`VISION.md` is deleted** after its non-goals and turn steps move. `COMPETITOR-RESEARCH.md`
   stays as a reference to other projects. PLAN.md Phase 6.2 (rewrite VISION's architecture)
   is skipped: Track F deletes the file.
7. **Party play (IDEAS 16) is in scope, in two layers.** A minimal party every engine gets:
   an NPC joins and follows the player, is interacted with, and every role reads it as part of
   the party the player leads; the master applies the engine's own help knob. Then engine
   layers on top: 24XX sheets, help dice, the ship and succession; Tunnel Goons goons who roll
   and level. Retires PLAN.md settled 17 (no companions gained) and 19's "no crew list"; closes
   `docs/24XX.md` deviations 1, 2, 4 and the ship half of 5, and `docs/BREATHLESS.md` 5.
8. Ponytail audit: dropped. Eval loop (IDEAS 4): stays in `IDEAS.md`.

Standing rules from `CLAUDE.md` bind every track: engines self-contained under 2,000 lines; one-way
imports; `core`/`turn`/`app`/`ui` know no world shape; only the narrator writes player-facing
text from revealed facts; only resolver code changes state or rolls; a bad answer is re-prompted
once; saves carry no version; no abstraction until two things need it; no building for later.


---

## Track G — the party, then crews (IDEAS 16)

Two layers. **The party** is the platform's minimum and every engine has it after G.1: an NPC
joins the player, follows them everywhere, can be talked to, hurt and lost, and every role reads
them as part of the party the player leads, not as someone who happens to be present; the
master turns a member's help into the engine's own knob. **A crew** is what an engine builds on
top when its SRD prints it: 24XX (sheets, help dice, the ship, succession) and Tunnel Goons
(goons who roll and level). Loner's companions are the party already; Breathless gets the party
and no crew (its "the cast carries no dice" stands until 24XX has played). G is its own
`PLAN.md`; this section is the design the briefs quote.

### G.0 The SRD, read 2026-09-02 at `24xx-srd.carrd.co` (verify again at phase start)

> Roll a skill die — d6 by default, higher with a relevant skill, or d4 if hindered by injury or
> circumstances. If helped by circumstances, roll an extra d6; if helped by an ally, they roll
> their skill die and share the risk. Take the highest die.

> Starships have basic versions of these functions; upgrades cost ₡10 each. In an emergency,
> players pick a function to do or help with. — Comms, Crafts (includes escape pod), Drive (FTL
> jump), Equipment (crew vac suits), Hull armor (breaks for defense), Sensors, Weapons.

> If killed, make a new character to introduce ASAP. Favor inclusion over realism.

> After a job, each character increases a skill (none→d8→d10→d12) and gains d6 credits.

### G.1 The party (all four engines)

- **Platform share, one thing, as the hub had two.** `NarratorView.party: tuple[Subject,
  ...]`, the player first then who travels with them, with a validator `party ⊆ subjects` (who
  the player is, not a world shape); `render_narrator` prints `YOUR PARTY: you are <name>; with
  you: <names or nobody>`. The `Illustrator` takes the player from it. Nothing else in `core`,
  `turn`, `app` or `ui` changes: the panel is a `Panel`, the arms are `change_world` arms. Not a
  gap today: `NarratorView.party` and the two arms in 24XX and Breathless land here.
- **Registration.** 24XX and Breathless register `JoinParty`/`LeaveParty` (15 → 17, 12 → 14,
  the pair not counted per decision 4); Tunnel Goons gets `TunnelGoonsWorld.party: list[EntityId]`
  through Track A's `check_party`/`join_party`/`leave_party`, `move` carries the party with
  the player (`with_ids` stays for an NPC who follows once), and registers the pair (9 → 11).
  Loner has them. The player's death ends the game as today until an engine adds succession.
- **What the master reads**, one shared paragraph in each `rules.md`: a party member is the
  player's to command in the fiction and yours to voice; when one plainly helps, that is the
  engine's help — 24XX `helped`, Loner `position`/`edge`, Tunnel Goons a lower `difficulty` or
  a named item, Breathless nothing (the SRD prints no help rule; the fiction carries it); a
  member cannot act on their own dice unless the engine gives them some (G.2, G.3); never
  volunteer a member's action to soften a scene.
- **Docs that go false**: `tunnelgoons/rules.md` "nobody follows on their own" (the party
  does); `docs/BREATHLESS.md` deviation 5 closes; `docs/TUNNEL-GOONS.md`'s "only the player
  has abilities" paragraph under "what the app adds" says the party has none until G.3.

### G.2 24XX crew

- **One cast type, an optional sheet.** `Operator(Person)` gains `sheet: Sheet | None = None`
  where `Sheet(Mutable)` is specialty, origin, traits, skills, credits, items, hindrances (what
  `Operator` carries today); the player's sheet is required by the world's validator; the
  worldsmith may give a regular one (the character file's own payload shape; the SRD's
  specialties are the vocabulary). 24XX is then `SceneWorld[Operator, Operator]`, Loner's shape,
  and Track A's party invariant holds untouched: a sheeted member rolls, an unsheeted one
  follows and helps as G.1. In a campaign, joining a sheeted regular is refused away from the
  hub: hiring is the fixer's business.
- **Rolls.** `Attempt.actor_id: CheckedEntityId` defaulting to the player (any living sheeted
  party member); `Attempt.helped_by: CheckedEntityId | None` names one sheeted member: they
  roll their own die for the named skill (d6 when they lack it) beside the actor's, and the
  highest counts; `helped` (circumstance) stays the extra d6; both may apply. A hindered helper
  is the master's call, as the actor's `hindered` is: `rules.md` says a member who is hurt does
  not help. "Share the risk" is the master's too: the consequence lands on the actor by code
  (`risking_death`, `Maimed`), and the helper takes a hindrance through `change_hindrances`
  when the fiction puts it on them. `Defend`, `ChangeHindrances`, `GainItem`, `DropItem`,
  `RepairItem`, `Spend` gain `actor_id` defaulting to the player: gear and credits are per
  operator, as the SRD keeps them.
- **After a job.** `AfterJob.raises: tuple[Raise(actor_id, skill), ...]` covers the player and
  every living sheeted party member, refused when one is missing or a stranger is named; each
  raises the named skill and rolls their own d6 credits. One call per job: a `raised: bool` on
  the `Job` record refuses the second.
- **The ship is gear.** `world.ship: dict[EntityId, Item] | None` over the seven printed
  functions (an `Item` breaks and is repaired already), plus `world.upgraded: set[str]`; the
  worldsmith answers `ship: bool` on the opening draft and code builds the seven; after PLAN
  Phase 5 `SceneEngine` picks the opening draft type, so `ship` either leaves the draft or
  `SceneEngine` gains an opening-draft attribute, and this phase decides. `Defend` and
  `RepairItem` resolve an id in the actor's items or the ship; one arm `ship_upgrade(function)`
  costs the player ₡10. A `Ship` panel shows when there is one.
- **The android body** (deviation 4): `srd.json`'s android `case` option carries a `Kit`;
  `create_character` adds it to the items, and `defend` then breaks it as the SRD prints.
  About 6 lines; verify the case text at phase start.
- **Succession.** When the player dies with a living sheeted member, the death site sets
  `PendingDecision(kind="succession", prompt="Who leads now?", options=one PendingOption per
  such member with name="change_world", args={"change": {"verb": "take_lead", "actor_id":
  ...}}, allows_text=False)` instead of ending the game; `take_lead` swaps the objects: the
  chosen member becomes `world.player` and the dead one goes into `cast`, both keeping their
  ids, and is refused while the player lives. `Engine.over` fires only when the player and every
  sheeted member are dead. `NarratorView.party` carries the new "you" with no further change.
- **Counts.** Arms: `join_party`, `leave_party` (G.1), `take_lead`, `ship_upgrade`. 24XX goes
  15 → 19.
- **Views and prompts.** The `Party` panel shows a sheeted member's `rows()`; the master's `THE
  PARTY` prints sheets; `worldsmith.py AUTHORING` ("the cast carries no dice") and the `attempt`
  description are rewritten; `worldsmith.md` says a sheet is for someone who could plausibly be
  hired, at most one per scene. `docs/24XX.md`: deviations 1, 2, 4 close; 5 splits into "the
  priced gear table is not transcribed" (stays) and the ship (closes).

### G.3 Tunnel Goons crew

`Goon` folds into `Npc` with `sheet: Abilities | None` (brute, skulker, erudite, inventory,
level); the player is an `Npc` whose sheet the validator requires. A sheeted member is a goon:
`ActionRoll.actor_id`, `rest` heals the party, `level_up` opens one decision per living goon in
turn (the option args carry `actor_id`; answering one opens the next), `take_lead` swaps
objects as 24XX. This re-adds the re-suspension path PLAN Phase 1 deleted: a tool that may run
while the rules wait, and a turn that knows it opened suspended. `Dungeon._consistent`'s item-holder check reads the party. 11 → 12.
`docs/TUNNEL-GOONS.md`: the "one goon" paragraph under "what the app adds" is rewritten;
deviation 1 (the level-up cadence) stays.

### G.4 Phases, in order

1. The party: `NarratorView.party`, `render_narrator`, the arms in 24XX, Breathless and Tunnel
   Goons, `TunnelGoonsWorld.party` and `move`, the shared `rules.md` paragraph; goldens:
   `narrator.txt` gains the YOUR PARTY line, `master.txt` the paragraph, `master_tools.json`
   the two arms, nothing else.
2. 24XX: `Sheet`, `actor_id` on the tools, `helped_by`, `AfterJob.raises`, the android case, the
   panel rows, `rules.md`, `AUTHORING`, `worldsmith.md`, `docs/24XX.md`.
3. 24XX: the ship and succession; `scenarios/amber-tap` gains a sheeted regular and a ship.
4. Tunnel Goons: G.3.
5. Docs; `IDEAS.md` 16 leaves.

**Done when.** In every engine a named NPC joins, walks into the next scene and is read as the
party by all three roles; a hired regular rolls beside Kael and the highest die counts; Kael dies
on a `risking_death` disaster and the page asks who leads; the new lead plays the return home
and `after_job` raises both survivors; the hull breaks to defend; 24XX at most 1,600 lines after
Track A, nineteen verbs. About +600 lines across `core/views.py`, `turn/context.py`, 24XX and
Tunnel Goons.

**Risks.** Prompt size grows by one entity line per member per role; no cap until a prompt shows
it needs one. The narrator must keep "you" on the player: the golden and one speakers test
guard it. The crew must not soak every risk: `helped_by` is one ally, and the shared paragraph
forbids volunteered member actions.

---

## Left in `IDEAS.md`, on purpose

- Moving home (D.5), with its sketch.
- The eval loop (IDEAS 4): a script against live CLIs, the only way to answer "does it play
  better"; the tool cap and Track G's help rule are the first two questions it would settle.
- Pack authoring (13) and the demo GIF (11).
- 24XX's priced gear table and d20 detail tables as pack data; Breathless and Loner deviations
  (none of the tracks touches a table procedure or a way-back procedure).
- Crew play for Breathless and Loner beyond what G leaves them.

## Refused in this round, with the reason

- A summarizer role: a fourth spawn per crossing for a paragraph the worldsmith already can
  write in the answer it gives.
- A "Previously…" narrator spawn on resume: the page opening at turn 1 was the bug (D.2).
- In-process Kokoro: torch or onnxruntime plus a 300 MB model in a seven-dependency project,
  untyped under strict pyright; the same model behind its HTTP port is Track C.
- Raising the cap for its own sake, or folding a tool for the count's sake: no engine is
  blocked, and flattening arms is token-neutral and unmeasured.
- A separate `crew` store, a `Regular` class, a `Ship` model, a `PARTY_MAX`, a `Scene.crew`
  stamp: each was a second way to hold what the cast, an `Item` or the party already holds.
- `Offer.follows`, a reputation counter, a second concurrent home: prose and the ledger do it.
- The master as its own worldsmith (the first seam review's fourth proposal): the maintainer's
  call. Authoring is a second profession; scenario creation needs the role anyway; the
  fifteen-tool cap is the master's attention budget.
- One flat scene draft with optional `recap`, `job`, `offers`, `debrief`: the five classes are
  the schema the worldsmith answers in, and pydantic enforces which fields a crossing, a job or
  a return owes; a flat draft moves that demand into prose and the bar, and the seven
  `isinstance` sites become seven `if draft.offers` sites.
- A `SceneRules` record and a `scene_engine` factory in place of `SceneEngine` (PLAN 5.1): the
  same surface, with a `partial` per field where the class carries `packs` and `cast` on
  `self`.
- Folding the `Kill` arm into `engines/base.py`: 24XX's succession (G.2) changes what a kill
  does, so the arm stays per engine.
