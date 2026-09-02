# NEXT-SPECS — after the hub

Tracks A through F of the 2026-09-02 brainstorm became `PLAN.md` and were cut from this file.
What stays: the maintainer's decisions, Track R (the seam, from `REFACTOR-PROPOSAL.md`), Track G
(the party, then crews), and what was left in `IDEAS.md` or refused. Track R becomes its own
`PLAN.md` when PLAN.md's six phases have landed; Track G follows it, written when the campaign
has been played through once with the recap. Counts and names below are as written on
2026-09-02; the code after Phase 2 is the reference for the party helpers Track G quotes
(`check_party`, `join_party`, `leave_party`, `Person`); Track R names files as PLAN.md Phase 5
lays them (`engines/seam.py`, `engines/scenes/`).

## Decisions made in the brainstorm (the maintainer's, 2026-09-02)

1. **One scene engine, three payloads.** `engines/scenes.py` may take pydantic type parameters
   on the cast and player types. PLAN.md settled 7 ("no type parameter") retires with PLAN.md.
   Loner's player leaves the cast and lives as `world.player`, as in 24XX and Breathless; Loner
   saves go stale, which the design allows.
2. **Memory is a recap the worldsmith writes on the crossing.** No summarizer role. The
   platform's `recent_exchanges` stays at 20.
3. **Voices are an HTTP provider on the illustration pattern**: off by default, the OpenRouter
   key the player already has, a local server if they run one, and the narrator's voice chosen
   per scenario as its art style is. No in-process model.
4. **The tool cap stays fifteen, counted as tools plus `change_world` arms**, the two party
   arms every engine carries (Track A) not counted. An engine whose SRD plays a crew (Track G)
   may go to twenty in all; its `docs/<ENGINE>.md` says so. No fold is made for the count's
   sake.
5. **Campaign refinements are all built**, except moving home, which stays in `IDEAS.md`.
6. **`VISION.md` is deleted** after its non-goals and turn steps move. `COMPETITOR-RESEARCH.md`
   stays as a reference to other projects. PLAN.md Phase 5.2 (rewrite VISION's architecture)
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

## Track R — the seam, made smaller (`REFACTOR-PROPOSAL.md`)

No behaviour change, no prompt change, no golden moves: `prompts/`, `schemas/`, `turn/`,
`state/` and `save/` are the track's invariant, and a phase that moves one has a bug. Read on
2026-09-02 against the code after Phase 3, where the three `engine.py` are 84–86 lines of the
same wiring, the three scene `worldsmith.py` are 42–50 lines binding a cast type and four
strings, and `GameService` runs `ready → write → install → arrival_brief` as a second state
machine after the turn (`_grow`, `_write`, `_install`, about 90 lines). Two phases, R.1 then
R.2, about two hours of agent time each. `src` from Phase 6's 9,735 to about 9,450.

### Open decisions (the maintainer's; the sketch below assumes the first option of each)

1. **R.2's form: a spec and a factory (`SceneRules` + `scene_engine`), or the proposal's class
   hierarchy (`SceneEngine` with `BreathlessEngine(SceneEngine)`).** Both delete the same
   wiring. The factory keeps `Engine` a frozen dataclass of callables, which the platform reads
   by attribute and the tests rewire with `dataclasses.replace`; the class form moves
   behaviour onto objects, against "write pure functions", and gives the three engines a base
   class whose overridable surface is the abstraction `CLAUDE.md` says not to add.
2. **Proposal 2, one flat draft: refused (below), or kept as an optional R.3.** The sketch
   refuses it.

### R.1 One transaction: `advance` and `author`

The platform asks the engine two things of the worldsmith and stops knowing their stages.

- **`core/model.py`.** `WorldsmithAnswer` becomes a `Protocol` with a generic call,
  `async def __call__[M: BaseModel](self, prompt: str, model: type[M], refusal: Callable[[M],
  str | None]) -> M`; `CheckAnswer` goes. `app/spawn.py`'s `answered` is already generic, so the
  engine's answer is typed end to end: `_is_draft`, its `__pydantic_generic_metadata__` read
  and `install_scene`'s `SceneDraft[Any]` go, and the CLAUDE.md `Any` line loses that clause.
- **`engines/seam.py`.** `Authoring` and `Transition` are deleted; `Engine` gains four fields
  in their place:
  ```python
  author: Callable[
      [str, Sequence[Slug], ScenarioKind, WorldsmithAnswer, Callable[[AnyScenario], str | None]],
      Awaitable[AnyScenario],
  ]                                  # source, packs, kind, the worldsmith, "is it playable"
  ready: Callable[[G], bool]
  advance: Callable[[G, str, WorldsmithAnswer], Awaitable[tuple[Fact, ...]]]
  arrival_brief: Callable[[str], str] | None
  ```
  `advance` writes, then installs on the draft it is given, and raises `ValueError` both when
  nothing usable was written and when the written world no longer fits; the platform never
  holds the written model. `author` composes the engine's own bar with the platform's
  playability check and returns the built file.
- **`app/runtime.py`.** `_write` and `_install` fold into `_grow`: `draft = self.state.draft()`;
  `try: facts = await self.engine.advance(draft, intent, self._ask); self.engine.validate(draft)`
  `except (OSError, ValueError)` sets `write_failure`, logs once, returns; then today's tail
  (silent commit, or the narrated crossing through `close_segment`). `_ask` is one method over
  `answered("worldsmith", ...)`. `new_scenario` becomes `written = await engine.author(source,
  packs, kind, self._ask, playable)` then `write_scenario(..., written.model_copy(update=...))`,
  where `playable` runs `begin_game`. The UI's `transition_available` reads `engine.ready`.
- **`engines/scenes/worldsmith.py`.** `write_next` + `install_scene` become
  `advance[C, P, S](state, intent, answer, *, cast_type, role, guidance, finished_note,
  before: Callable[[Game[S]], tuple[Fact, ...]] | None)`; `before` is Loner's `close_conflicts`,
  run before the install as the wrapper does today. `render_opening` + `opening_draft` +
  `build_scenario` become `author[C](...)`. Each engine's `worldsmith.py` keeps one `advance`
  and one `author` wrapper until R.2 removes them. Tunnel Goons: `write_extension` +
  `install_extension` become `advance`; `render_map` + `opening_draft` + `build_scenario`
  become `author`; the `MapDraft | ReturnDraft` union is typed, no `BaseModel` left.
- **Tests.** `test_a_transition_without_an_arrival_brief_extends_on_a_lineless_exchange`
  rewires `advance` and `arrival_brief`; `test_authoring_build_raises_on_an_unmet_bar` becomes
  a scripted `author` that the bar refuses; the four `test_worldsmith.py` call `advance` and
  `author` where they called the pairs. No test of prose or wiring is added.
- **Done when.** Green; every golden unchanged; `grep -rn "BaseModel" src/aidm/engines/seam.py
  src/aidm/app/runtime.py` finds no written-model parameter; a failed write and an install that
  no longer fits both leave the state untouched and set `write_failure`. About −110 lines.

### R.2 One scene engine

After R.1, a scene `engine.py` wires 24 fields, of which eight are the same `scenes` function
in all three (`validate`, `known`, `record`, `history`, `narrator_view`, `over`, `ready`,
`arrival_brief`), two come from a wrapper that binds four strings, and `new_game` is two
`isinstance` checks around `new_world`. The proposal's litmus, "a fifth scene engine is its
state model, its creation, its tools and its sections", is what this phase buys.

- **`engines/scenes/engine.py`** (a new file in the Phase 5 package):
  ```python
  @dataclass(frozen=True, slots=True, kw_only=True)
  class SceneRules[C: Person, S: SceneState[Any, Any], K: BaseModel]:
      """What one scene engine says for itself; `scene_engine` wires the lifecycle around it."""
      id: EngineId; title: str; art_style: str
      directory: Path                          # rules.md, worldsmith.md, packs/
      pack: type[K]; cast: type[C]
      game: type[Game[S]]; scenario: type[Scenario[SceneScenario[C]]]; character: type[AnyCharacter]
      new_state: Callable[[AnyScenario, AnyCharacter], S]     # today's new_game, minus the two checks
      tools: Callable[[Mapping[str, K]], tuple[MasterTool[Game[S]], ...]]
      creation_steps, create_character, preview_character, pack_options, guidance   # today's, uncurried
      master_sections: Callable[[Mapping[str, K], Game[S]], Rows]
      panels: Callable[[Game[S]], tuple[Panel, ...]]          # 24XX Gear, Breathless Backpack, Loner ()
      hub_phrase: str; finished_note: str
      board_guidance: str = ""                 # 24XX: joined on every campaign write and opening
      before_crossing: Callable[[Game[S]], tuple[Fact, ...]] | None = None   # Loner: close_conflicts

  def scene_engine[C, S, K](rules: SceneRules[C, S, K], user_packs: Path) -> Engine[Game[S]]
      # loads the packs; the two "received an incompatible ..." checks use rules.title;
      # the eight shared functions; player_view = scenes.player_view(state, rules.panels(state));
      # advance/author from R.1 with the four strings bound; instructions from directory/rules.md
  ```
  `S: SceneState[Any, Any]` is the bound the seam functions already spell, so it adds no
  `Any`. Loner's `Loner3eState` carries `twist`, which is why the state is a field and not
  `SceneState[C, P]`.
- **Each scene engine.** `engine.py` is the `SceneRules` literal plus `build(user_packs) =
  scene_engine(RULES, user_packs)`, about 35 lines. `worldsmith.py` is deleted: `WORLDSMITH`,
  `HUB_PHRASE`, `JOB_DONE_NOTE`/`GROWTH_NOTE`, `BOARD_GUIDANCE` move into `engine.py`'s
  constants block. `views.py` keeps `master_sections` and the gear lines, and gains nothing.
  Tunnel Goons is untouched: one engine of its shape is no reason for a second factory.
- **Tests.** `tests/*/test_engine.py` build through `scene_engine`; a test that a fifth
  `SceneRules` with a bare `Person` cast and no tools builds a playable engine is the one new
  behaviour test.
- **Done when.** Green; every golden unchanged; the three `engine.py` under 40 lines; no scene
  `worldsmith.py` exists; `docs/<ENGINE>.md` and `README.md`'s architecture paragraph (PLAN 5.4)
  name `SceneRules` where they named "the wiring file". About −170 lines.

### Refused, with the reason

- **Proposal 4, the master as worldsmith**: the maintainer's note in `REFACTOR-PROPOSAL.md`
  stands. Authoring is a second profession; scenario creation needs the role anyway; the
  fifteen-tool cap is the master's attention budget.
- **Proposal 2, one flat draft with optional `recap`, `job`, `offers`, `debrief`**: the five
  classes are the schema the worldsmith answers in, and pydantic enforces which fields a
  crossing, a job or a return owes; a flat draft moves that demand into prose descriptions and
  the bar, the schema the model reads grows fields it must leave empty, and the eight
  `isinstance` sites become eight `if draft.offers` sites. The ugliest piece, `_is_draft`,
  goes with R.1's typed answer, which is what the proposal was reacting to. A return closing a
  job is a domain distinction, not a leaked output shape.
- **A class hierarchy for R.2** (unless decision 1 goes the other way): see the decision.
- **A generic "role" abstraction over master, narrator and worldsmith**: the proposal's own
  second response refuses it, and so does this track. Nothing in R touches `Turn`, `Fact`,
  `Game.draft/committed` or `NarratorView`.

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
  `turn`, `app` or `ui` changes: the panel is a `Panel`, the arms are `change_world` arms.
- **Registration.** 24XX and Breathless register `JoinParty`/`LeaveParty` (15 → 17, 12 → 14,
  the pair not counted per decision 4); Tunnel Goons gets `TunnelWorld.party: list[EntityId]`
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
- **After a job.** `JobDone.raises: tuple[Raise(actor_id, skill), ...]` covers the player and
  every living sheeted party member, refused when one is missing or a stranger is named; each
  raises the named skill and rolls their own d6 credits. One call per job.
- **The ship is gear.** `world.ship: dict[EntityId, Item] | None` over the seven printed
  functions (an `Item` breaks and is repaired already), plus `world.upgraded: set[str]`; the
  worldsmith answers `ship: bool` on the opening draft and code builds the seven. `Defend` and
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
  ids, and is refused while the player lives. `player_over` fires only when the player and every
  sheeted member are dead. `NarratorView.party` carries the new "you" with no further change.
- **Counts.** Arms: `join_party`, `leave_party` (G.1), `take_lead`, `ship_upgrade`. 24XX goes
  15 → 19.
- **Views and prompts.** The `Party` panel shows a sheeted member's `rows()`; the master's `THE
  PARTY` prints sheets; `creation.py _AUTHORING` ("the cast carries no dice") and the `attempt`
  description are rewritten; `worldsmith.md` says a sheet is for someone who could plausibly be
  hired, at most one per scene. `docs/24XX.md`: deviations 1, 2, 4 close; 5 splits into "the
  priced gear table is not transcribed" (stays) and the ship (closes).

### G.3 Tunnel Goons crew

`Goon` folds into `Npc` with `sheet: Abilities | None` (brute, skulker, erudite, inventory,
level); the player is an `Npc` whose sheet the validator requires. A sheeted member is a goon:
`ActionRoll.actor_id`, `rest` heals the party, `level_up` opens one decision per living goon in
turn (the option args carry `actor_id`; answering one opens the next), `take_lead` swaps
objects as 24XX. `Dungeon._consistent`'s item-holder check reads the party. 11 → 12.
`docs/TUNNEL-GOONS.md`: the "one goon" paragraph under "what the app adds" is rewritten;
deviation 1 (the level-up cadence) stays.

### G.4 Phases, in order

1. The party: `NarratorView.party`, `render_narrator`, the arms in 24XX, Breathless and Tunnel
   Goons, `TunnelWorld.party` and `move`, the shared `rules.md` paragraph; goldens:
   `narrator.txt` gains the YOUR PARTY line, `master.txt` the paragraph, `master_tools.json`
   the two arms, nothing else.
2. 24XX: `Sheet`, `actor_id` on the tools, `helped_by`, `JobDone.raises`, the android case, the
   panel rows, `rules.md`, `_AUTHORING`, `worldsmith.md`, `docs/24XX.md`.
3. 24XX: the ship and succession; `scenarios/amber-tap` gains a sheeted regular and a ship.
4. Tunnel Goons: G.3.
5. Docs; `IDEAS.md` 16 leaves.

**Done when.** In every engine a named NPC joins, walks into the next scene and is read as the
party by all three roles; a hired regular rolls beside Kael and the highest die counts; Kael dies
on a `risking_death` disaster and the page asks who leads; the new lead plays the return home
and `job_done` raises both survivors; the hull breaks to defend; 24XX at most 1,600 lines after
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
