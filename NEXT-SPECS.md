# NEXT-SPECS — after the hub

What comes after `PLAN.md` (campaigns with a home base) finishes with Phase 5. This file is a list
of proposals, each with enough shape to become a `PLAN.md` phase; it is not a plan. Tracks are
ordered; a track's "Done when" is what its future phase is judged on. Written 2026-09-02 from a
read of all of `src/`, two Fable opinion rounds and one adversarial review.

Counts at writing: `src` 10,115 lines (24XX 1,460, Loner 1,418, Breathless 1,341, Tunnel Goons
1,285, `scenes.py` 385, `hub.py` 216); 437 tests. Phase 4 adds about 130 to Tunnel Goons.

## Decisions made in the brainstorm (the maintainer's, 2026-09-02)

1. **One scene engine, three payloads.** `engines/scenes.py` may take pydantic type parameters
   on the cast and player types. PLAN.md settled 7 ("no type parameter") is retired with PLAN.md.
   Loner's player leaves the cast and lives as `world.player`, as in 24XX and Breathless; Loner
   saves go stale, which the design allows.
2. **Memory is a recap the worldsmith writes on the crossing.** No summarizer role. The
   platform's `recent_exchanges` stays at 20.
3. **Voices are an HTTP provider on the illustration pattern**: off by default, the OpenRouter
   key the player already has, a local endpoint through `providers.local` if they run one. No
   in-process model.
4. **The tool cap stays fifteen, counted as tools plus `change_world` arms.** Small folds are
   fine. An engine that plays a crew (Track G) may go to twenty; its `docs/<ENGINE>.md` says so.
5. **Campaign refinements are all built**, except moving home, which stays in `IDEAS.md`.
6. **`VISION.md` is deleted** after its non-goals and turn steps move. `COMPETITOR-RESEARCH.md`
   stays as a reference to other projects.
7. **Crew play (IDEAS 16) is in scope**, 24XX first, designed to play as the SRD prints it.
8. Ponytail audit: dropped. Eval loop (IDEAS 4): stays in `IDEAS.md`.

Standing rules from `CLAUDE.md` bind every track: engines self-contained under 2,000 lines; one-way
imports; `core`/`turn`/`app`/`ui` know no world shape; only the narrator writes player-facing
text from revealed facts; only resolver code changes state or rolls; a bad answer is re-prompted
once; saves carry no version; no abstraction until two things need it; no building for later.

---

## Track A — one scene engine, three payloads

**What.** The three scene engines are one design copied three times: measured by `diff` after
renaming, Breathless' `worldsmith.py` differs from 24XX's by 18 lines of 256, Loner's by 49;
`views.py` by 12 and 34 of 118; `world.py` by 65 and 97 of 265; `engine.py` by 8 and 10 of 109.
Move the shared design into `engines/scenes.py` once, generic over the cast and the player.

**Why.** About 830 lines of `src` go, and the next engine or feature (Tracks B, D, G) is written
once instead of three times. Phase 3b stopped at the world-free part because settled 7 forbade a
type parameter; decision 1 lifts it. `core/model.py` is already generic on the payload.

**Shape**, all in `engines/scenes.py` unless named:

```python
class Person(Mutable):                       # what every cast entry and every player sheet has
    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    alive: bool = True
    def rows(self) -> Rows: return ()        # the sheet, as the master's entity line prints it

class Npc(Person): ...                       # 24XX and Breathless: the identical class, once

class SceneCanon[C: Person](Mutable):        # cast, opening, present, hidden, source, hub, board
class SceneWorld[C: Person, P: Person](Mutable):
    cast: dict[EntityId, C]
    player: P                                # id == PLAYER_ID, known, never listed in a run
    runs, source, hub, board                 # as today
    # require, require_here, require_alive_here, here (player first), label, reveal: today's
    # 24XX bodies. Two hooks, overridable, no callback:
    def travellers(self) -> tuple[EntityId, ...]: return ()      # Loner: its companions
    def authored_unmet(self, cast: Mapping[EntityId, C]) -> list[str]: ...  # alive; Loner adds full luck

class SceneDraft[C: Person](Frozen): ...     # today's fields; cast: dict[EntityId, C]
class JobDraft[C](SceneDraft[C]): job: str = Field(min_length=MIN_JOB)
class HubDraft[C](SceneDraft[C]): offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)
class ReturnDraft[C](HubDraft[C]): debrief: str = Field(min_length=1)
```

Shared functions, each today's 24XX body with the engine's constants as parameters:
`opening_draft(cast_type, kind)`, `opening_canon`, `apply_scene` (uses `travellers()` for the
followers kept in every scene, so Loner's companion block goes), `write_next(world, intent,
answer, *, role, guidance)`, `install_scene(world, written, *, finished_note: str)` (24XX passes
`JOB_DONE_NOTE`, Loner `GROWTH_NOTE`, Breathless `""`; Loner's `close_conflicts` stays in its own
four-line wrapper), `render_worldsmith`, `render_opening(role, source, guidance, kind, hub_phrase,
cast_type)`, `build_scenario(file_type, engine_id, ...)`, `scene_unmet` (`cast_unmet` +
`authored_unmet` + `hub_unmet`), `narrator_view(world)`, `scene_panels(world, sheet_panels)` (the
`player_view` frame: Character, the engine's own panels, This scene, Board, Here, Trail, Jobs;
"Travelling with" comes from `travellers()`), `entity_line(world, one, detail)` (reads
`Person.rows()`; "travels with the player" from `travellers()`), `new_game(canon, player,
world_type)`, `check_game(packs, state, engine_title)`, and the four world arms `Reveal`,
`Enter`, `Leave`, `Kill` with `reveal_hidden/enter/leave/kill(world, id)`. `CHANGE_WORLD`,
`sentence`, `PLAYER_DEAD` move to `engines/core.py`. `Entity` (the protocol) gains `brief`.

Each engine keeps: its `Person` subclasses (`Operator`, `Survivor`, `LonerCharacter`), its
`State`/`Game`/`ScenarioFile`/`CharacterFile`, `player_*` builders, `WORLDSMITH`, `HUB_PHRASE`,
its note, `BOARD_GUIDANCE`, its SRD tools and arms, its own panels, and a `build()` that wires
`partial`s. `Loner3eState.twist` stays.

Loner: `LonerWorld(SceneWorld[LonerCharacter, LonerCharacter])` with `companions`; `player_id`
goes; `new_game` stops listing `PLAYER_ID` in `present`; `travellers()` returns the companions;
`roll_question` on the player resolves through `require_alive_here(PLAYER_ID)`, which the base
answers with `player`.

Dead code, same phase: `ui/settings.py _without_none`, the `places` guard in Tunnel Goons
`walk`, 24XX `SRD_PACK`, `Known[G]` re-spelled in `engines/core.py`, `other_than` ×2 and
`pack_options` ×3 (to `core/creation.py`).

**Done when.** Green; the one-shot `narrator.txt` and `picture.txt` goldens unchanged; `master.txt`
unchanged; Loner `state/` and `save/` fixtures re-keyed; each scene engine under about 1,150;
`scenes.py` about 700; `src` about 9,300. Every worldsmith test rewritten once against
`scenes.py`; the engines' own tests keep only what the engine owns.

**Cost and risk.** About one implementer-day, split A (scenes.py, opus) then B (the three
engines, parallel, sonnet). Risk: pydantic generics with a validator on the base and subclass
fields (already done by `SceneWorld` today, one level deeper here); `basedpyright` strict on
`dict` invariance is what makes the parameter necessary, and it is exact typing, not `Any`.

---

## Track B — memory: the scene recap

**What.** When the worldsmith writes the next scene it also writes one paragraph on the scene the
player is leaving. That paragraph replaces the scene's exchanges in every later prompt.

**Why.** Today the master's RECENT PLAY is the last 20 exchanges across the save, and the
worldsmith's SCENES SO FAR keeps 3 exchanges per scene. A three-scene job at `SCENE_TURN_CAP`
is 36 turns, so the job's opening is gone before the return; a one-shot has no ledger at all.
The campaign ledger (`Debrief`) already compacts across jobs; this compacts inside one.

**Shape** (after Track A; engine-owned, `core`/`turn`/`app`/`ui` untouched):

```python
MIN_RECAP = 80
class NextDraft[C](SceneDraft[C]):          # any scene written in play
    recap: str = Field(min_length=MIN_RECAP, description="One paragraph on the scene the player "
        "is leaving: what they did, what it cost, what they learned, what they missed. Read by "
        "the game master and by you, never by the player, so it may name the secret.")
class JobDraft[C](NextDraft[C]): ...
class ReturnDraft[C](NextDraft[C]): offers; debrief
class HubDraft[C](SceneDraft[C]): offers     # the campaign opening only: nothing to recap
class SceneRun(Mutable): ...; recap: str = ""   # written when the player left
```

- `apply_scene` sets `world.run.recap = draft.recap` before the append.
- `scene_history`: a run with a recap prints its title, question, job line and `what happened:
  <recap>`; the live run prints its situation and every exchange (today's 3-exchange tail was
  the cap the recap now removes; a scene is at most 12 turns).
- Master: `recap_rows(world) -> Rows` gives `("EARLIER IN THIS JOB" | "EARLIER IN THIS
  ADVENTURE", "- <title>: <recap>" per recapped run of `job_runs()`)`, spliced by
  `master_sections` before `master_tail`. The rows are empty on the first scene.
- The narrator never sees a recap: `NarratorView` does not change. The player's memory is the
  transcript, the debrief card and the `Jobs` panel.
- Tunnel Goons: none. Its worldsmith spawns only at the frontier, and the map (places, `alive`,
  `on`) is most of its memory. Accept.
- `recent_exchanges` stays 20 (decision 2).

**Done when.** A crossing stamps the recap on the run left; a job's third scene's master picture
names the first scene's outcome; `state/` and `save/` fixtures gain `"recap": ""` per run;
`master.txt` unchanged (the rows are empty on turn 1). About +50 lines.

**Cost.** Zero extra spawns; the worldsmith writes one more paragraph; the master reads about 120
tokens per closed scene of the job.

---

## Track C — voices

**What.** Narration and dialogue read aloud, generated after the turn commits, cached beside the
art, played under the newest exchange. Off by default.

**Why.** IDEAS 1. The largest player-experience gain per line left on the list, and the
illustration pattern already answers every design question (optional, provider-keyed, cached,
failures only log).

**Shape.**

- `config.py`: `SpeechConfig(enabled=False, provider: ProviderName = "openrouter",
  model="openai/gpt-4o-mini-tts", voice="alloy", timeout=60.0)`; `Settings.speech`;
  `_keys_present` also checks the speech provider's key. The settings page renders it for free.
- Endpoint: `POST {base_url}/audio/speech` with `{model, input, voice, response_format}`; the
  reply is raw audio bytes. OpenRouter serves it (documented at
  `openrouter.ai/docs/guides/overview/multimodal/tts`, OpenAI-compatible, priced per character);
  a local Kokoro-FastAPI on `providers.local` serves the same shape. One client, both.
- `app/speech.py`, about 120 lines, mirroring `media.py`: `Reader` (not `Speaker`: taken by
  `core.play`) with `config`, `provider`, `saves`, `generating`; `clip(exchange) -> Path | None`,
  `pending(exchange)`, `async read(exchange)`; `open_reader(settings, store)`; held on
  `GameService.voice`. One request per line: narration in `config.voice`, dialogue in a voice
  from a fixed `VOICES` tuple picked by `sha1(speaker.id)`, so a face keeps its voice as it keeps
  its icon. `response_format="wav"`; the lines are joined with the stdlib `wave` module into one
  file keyed `sha1(model|voice|text)[:12].wav` under `store.media_dir(slug) / "speech"`.
- Triggered where `illustrate` is: after `commit` in `play` and after a narrated crossing in
  `_install`. Cards, situations and debriefs are not spoken; a resumed game generates nothing for
  old exchanges (cache only).
- `ui/game.py`: `ui.audio(path, autoplay=True)` under the newest exchange in `chat`, `controls`
  only on older ones; the 3-second `poll_art` timer also watches for the clip. About 15 lines.

**Done when.** With `SPEECH__ENABLED=true` and a key, a turn's narration plays within seconds of
the text; the file is reused on reload; with the provider down, the turn is unaffected and one
warning logs. About +180 lines `src`. No test spawns anything; the request builder and the cache
key are the tested functions.

**Open.** The per-character price of `gpt-4o-mini-tts` versus `google/gemini-2.5-flash-preview-tts`
is the maintainer's call at phase start; the model string is a setting either way.

---

## Track D — campaign refinements, all cheap

Built together in one phase after Track A. About +25 lines.

1. **A retaken job keeps its terms.** Today `TAKE_BRIEF` sends a retaken offer back to its place
   and cast, but the worldsmith rewrites `job` from the pitch, so pay and terms drift. `Stop.job:
   str` from `scene.job`; `Job.job` from the first job stop in `closed_jobs`; `ledger` prints
   `the job: <job>` under an open job's line; `TAKE_BRIEF` says a retaken job keeps the terms
   JOBS SO FAR prints. About 8 lines.
2. **A resumed game opens at its end.** `game_page` never scrolls; a returning player lands on
   turn 1. One `call_later(0.1, transcript.scroll_to(percent=1.0))` at the end of `game_page`.
   This is the "session recap on resume" of `COMPETITOR-RESEARCH.md`: the transcript, under its
   last chapter heading, is the recap. No narrator spawn.
3. **The save card says where you are.** `SaveOption.where: str` from
   `engine.history(engine.restored(raw))[-1].where`; the card reads "Kael · turn 34 · Deck 9 —
   The Loading Bay". `load_catalog` validates each save to get it; seven saves is fine.
4. **Jobs that connect** stay prose: `RETURN_BRIEF` already asks for an offer grown from the
   ledger. No `Offer.follows`.
5. **Moving home** stays in `IDEAS.md` with the design that was sketched: `SceneWorld.hubs`
   tuple, `at_hub = place == hubs[-1]`, the walk tests membership, a `MOVE_HOME` row at the hub,
   `HubDraft` reused, "New home: <title>" card; about 70 lines; no SRD prints it.

---

## Track E — tool folds and the consistency audit

No behaviour change except the three folds, each named. One phase, about -60 lines.

**Folds** (the cap stays fifteen; counts after: 24XX 15, Breathless 12, Loner 12, Tunnel Goons 9):

1. Tunnel Goons `unlock_way` becomes a `change_world` arm: the SRD prints no unlock procedure,
   it is a world verb, and it already runs `during_suspension`. 6 + 3 becomes 5 + 4.
2. Breathless `use_med_kit` folds into `change_stress(med_kit: bool)`: a validator refuses
   `amount` with `med_kit`, the 2 stays in code. The current description's "never a stand-in
   for `use_med_kit`" exists because the master confused the two.
3. `test_luck` ×2 keep their SRD ladders and tools; the roll body becomes `luck_fact(question,
   die, bands)` in `engines/core.py`.

Refused: 24XX `defend` as an arm (the count does not move and the SRD's Defend leaves the tool
list); Loner `restore_luck` as an arm (an arm runs during the conflict pause and would reset the
clock mid-conflict).

**Audit findings to fix** (all grep-traced; the schema audit found every field read):

- Delete: the `hint` on Tunnel Goons' options steps (never shown); the `places` guard in `walk`
  (already in Track A if not done there).
- Defaults nobody uses, made required: `render_picture(resumed, notes, recent)`,
  `render_narrator(passages)`, `write_scenario(source)`, `Turn.begin(on_fact)`,
  `illustration_request(referenced)`. `twentyfourxx.creation.guidance` reads neither argument:
  say so in one line or drop the `partial`.
- Layout: `core/views.py sections()` before its classes; `ui/game.py on_fact` public after
  private; `type` aliases (`core/model.py`, `engines/core.py`) into the constants block. The
  `WorldChange` unions, `DRIVERS`, `TURN_TOOLS` and Tunnel Goons' `Entity` must follow their
  classes: accepted, one comment each.
- Naming: Tunnel Goons `validate` → `check_game`; its `render_map`/`write_extension`/
  `install_extension` keep their names (a map is not a scene) and Phase 4's `way_open` rename
  stands; the local `known` mappings in the worldsmith → `everyone`.
- `Any`: nine sites, all generic bounds or the `Any*` aliases; `Game[P]` is invariant, so they
  are the exact type. Write the exception into `CLAUDE.md` rather than leave the rule false.
- `Counter.clamped` (one user, `adjust`) inlined; docstrings past one line trimmed where the
  code says the what.
- `CLAUDE.md`: "at most fifteen game-master tools, counted as tools plus `change_world` arms;
  twenty for an engine whose SRD plays a crew, named in its `docs/<ENGINE>.md`".

---

## Track F — documentation

One phase, no `src` change. Before it, Phase 5 has deleted `HUB-SPECS.md`, `PLAN.md` and
`PROGRESS.md`.

1. **`VISION.md` is deleted.** What only it says moves first: the non-goals (shared world layer,
   save migration, the built-in loop and the state keeper, retrieval) into `CLAUDE.md`'s design
   decisions, one line; "how a turn runs" into `CLAUDE.md`, three bullets; content paths and
   "play costs the subscription, illustration is the exception" into `README.md`; Maze Rats
   (`2c3e8a5`, `62f95c6`) and the Pokémon–Showdown boundary into `IDEAS.md`. The seam member
   list duplicates `engines/core.py` and goes; MVP0 and the after-MVP0 lists are done or in
   `IDEAS.md`. Then `README.md`'s link, `pyproject.toml`'s `extend-exclude` entries.
2. **`README.md`** gains one architecture paragraph (the three roles, the seam, the one-way
   imports) and the campaign paragraph Phase 5 wrote.
3. **`IDEAS.md`**: delete 15 (done), 12 (item 1 targets a skill that no longer exists, item 2 is
   Track D.2), 3 and 9 (refused by the non-goals), the built-in half of 4; fold 5, 6, 7, 8, 14
   into one "audit" line that Track E closes; keep 4's eval loop, 11, 13, moving home (D.5).
4. **`COMPETITOR-RESEARCH.md`** stays as the reference to other projects; its first table's
   "ours" columns and the `ROADMAP.md`, "code mode" and `.agents/skills` mentions are stale and
   get one dated note at the top rather than a rewrite.
5. **Engine docs, one shape** (IDEAS 14): every `docs/<ENGINE>.md` in the same section order
   (sources, licence, packs, tools, deviations, readings, what the app adds, where the rules
   live). 24XX already has it; the other three are reordered, not rewritten.

**Done when.** Every document says what the code does; no document holds rules text; `grep -r
VISION` finds nothing.

---

## Track G — crew play (IDEAS 16)

The largest track and its own `PLAN.md`. 24XX first, because its SRD prints the crew, the ship,
the help rule and succession; Tunnel Goons second, because its SRD is a party game and its
`Npc` already has Health and walks along. Loner's companions already roll through `actor_id`;
Breathless stays solo (the engine's "the cast carries no dice" decision stands until 24XX has
played). This section is the design; the phase briefs quote it.

### G.0 The SRD, read 2026-09-02 at `24xx-srd.carrd.co` (verify again at phase start)

> Roll a skill die — d6 by default, higher with a relevant skill, or d4 if hindered by injury or
> circumstances. If helped by circumstances, roll an extra d6; if helped by an ally, they roll
> their skill die and share the risk. Take the highest die.

> Starships have basic versions of these functions; upgrades cost ₡10 each. In an emergency,
> players pick a function to do or help with. — Comms, Crafts (includes escape pod), Drive (FTL
> jump), Equipment (crew vac suits), Hull armor (breaks for defense), Sensors, Weapons.

> If killed, make a new character to introduce ASAP. Favor inclusion over realism.

> After a job, each character increases a skill (none→d8→d10→d12) and gains d6 credits.

Deviations 1 (no ally rolls), 2 (no succession) and 5 (no ship) in `docs/24XX.md` close; 3 and 4
stay.

### G.1 The shape (24XX)

- **The party.** `SceneWorld` (Track A) gains `party: dict[EntityId, P] = Field(min_length=1)`
  and `lead: EntityId = PLAYER_ID`; `player` becomes the property `party[lead]`; `here()` yields
  the party first; `travellers()` returns the party minus the lead, so the crew is present in
  every scene, home included, and the worldsmith never lists them. Every engine without a crew
  has a one-entry party; nothing else changes for it. `known()` reads the party.
- **Where crew comes from.** The worldsmith may give an `Npc` a sheet: `Npc.sheet:
  TwentyfourxxCharacter | None = None` (the character file's own payload: specialty, origin,
  traits, skills, kit; the SRD's specialties are the vocabulary). Only a sheeted NPC can be
  hired. The `hire` arm moves a living, present, sheeted NPC from `cast` into `party` as an
  `Operator` (same id, so icon and transcript hold; credits 0; kit from the sheet); `dismiss`
  moves a party member back into `cast` as an `Npc` with the sheet they now have. `PARTY_MAX =
  4` (the lead and three): prompt size, not SRD; a fifth hire is refused.
- **Rolls.** `Attempt.actor_id: CheckedEntityId = PLAYER_ID` (any living party member);
  `Attempt.helped_by: CheckedEntityId | None` names an ally in the party: they roll their own
  die for the named skill (d6 when they lack it, d4 when hindered) beside the actor's, and the
  highest counts; `helped` (circumstance) stays the extra d6; both may apply, as today. "Share the
  risk" is the master's: the consequence lands on the actor by code (`risking_death`, `Maimed`),
  and `rules.md` says the helper takes a hindrance through `change_hindrances` when the fiction
  puts it on them. `Defend.actor_id`, `ChangeHindrances.entity_id`, `GainItem`/`DropItem`/
  `RepairItem`/`Spend` gain `actor_id` defaulting to the lead: gear and credits are per operator,
  as the SRD keeps them.
- **After a job.** `JobDone.raises: tuple[Raise(actor_id, skill), ...]`: one entry per living
  party member, refused when one is missing; each raises the named skill and rolls their own d6
  credits. One call per job, as today.
- **The ship.** `world.ship: Ship | None`; `Ship.functions: dict[ShipFunction, Function(upgraded:
  bool = False, broken: bool = False)]` over the seven printed functions, all present at
  "basic". `ship_upgrade(function)` costs the lead ₡10; `ship_repair(function, cost)`; hull armor
  breaks through `defend(item_id="hull-armor")`, so no arm is added for it. A campaign's opening
  canon may carry a ship (the worldsmith writes `ship: true` when the hub is a ship or the crew
  owns one); a one-shot may too. The sidebar shows a `Ship` panel when there is one.
- **Succession.** When the lead dies with a living party member, `_kill` and `attempt` set
  `PendingDecision(kind="succession", prompt="Who leads now?", options=the living crew,
  allows_text=False)` instead of ending the game; the answer plays `take_lead(actor_id)`, which
  sets `world.lead`. `player_over` fires only when nobody in the party is alive. The dead lead
  stays in the party, dead, as the SRD's sheet would. The narrator's "you" follows the lead:
  `NarratorView.you: Subject` (a core field: who the player is, not a world shape) and
  `render_narrator` says "YOU are <name>; the crew are named".
- **Counts.** Arms added: `hire`, `dismiss`, `ship_upgrade`, `ship_repair`, `take_lead` (an arm,
  so it plays under the decision). 24XX goes 15 → 20, the cap decision 4 allows.
- **Views.** A `Crew` panel (each member's `rows()`, hindrances, "dead"); `Here` lists the party
  first; the master's `YOU PLAY FOR` becomes `THE PARTY (the lead first)`.

### G.2 How it plays (the rules the master reads)

1. The player's words drive the lead. A crew member acts when the player's action names them or
   the fiction makes them act; the master never volunteers crew rolls to soften a scene.
2. Help is one ally per roll, named in `helped_by`; they share the risk in the fiction.
3. A crew member can die like anyone; the lead's death pauses the game on the succession
   decision; a party with nobody alive is over.
4. At the hub, hiring is the fixer's business: a sheeted regular can be hired; the board and
   the jobs do not change shape.
5. The ship is gear: functions break to defend, cost ₡10 to upgrade, and the master names the
   function in an emergency as the SRD says.

### G.3 Tunnel Goons

`Goon` gains nothing; `party: dict[EntityId, Goon]` with `lead`; `Npc.sheet` is the three
abilities; `hire`/`dismiss` arms; `ActionRoll.actor_id`; `move` carries the party without
`with_ids`; `rest` heals the party; `level_up` opens one decision per living party member in
turn; succession as 24XX. 9 → 11. `docs/TUNNEL-GOONS.md` deviation 1 (one goon) closes.

### G.4 Phases, in order

1. `scenes.py`: `party`/`lead`, `NarratorView.you`, `render_narrator`; every engine a one-entry
   party; goldens: `narrator.txt` gains the YOU line, nothing else.
2. 24XX: `Npc.sheet`, `hire`/`dismiss`, `actor_id` on the tools, `helped_by`, `JobDone.raises`,
   `Crew` panel, `rules.md`, `worldsmith.md` (a sheeted regular at the hub), `docs/24XX.md`.
3. 24XX: the ship and succession; `scenarios/amber-tap` gains a sheeted regular and a ship.
4. Tunnel Goons: G.3.
5. Docs; `IDEAS.md` 16 leaves.

**Done when.** A hired regular rolls beside Kael and the highest die counts; Kael dies on a
`risking_death` disaster and the page asks who leads; the new lead plays the return home and
`job_done` raises both survivors; the hull breaks to defend; 24XX at most 1,700 lines after
Track A's cut, twenty verbs. About +450 lines across `scenes.py`, 24XX and Tunnel Goons.

**Risks.** Prompt size grows by one entity line per crew member per role. The narrator must keep
"you" on the lead: the golden and one speakers test guard it. The worldsmith may over-sheet NPCs:
`worldsmith.md` says a sheet is for someone who could plausibly be hired, at most one per scene.

---

## Order, budget, and what each phase leaves behind

| track | phases | `src` after (about) | needs |
|---|---|---|---|
| A — one scene engine | 2 (scenes.py, then the three engines) | 9,300 | Phase 5 done |
| B — recap | 1 | 9,350 | A |
| D — campaign refinements | 1 | 9,375 | A |
| E — folds and audit | 1 | 9,315 | A |
| C — voices | 1 | 9,495 | none |
| F — docs | 1 | 9,495 | E (for `CLAUDE.md`) |
| G — crew play | 5 | 9,950 | A, B, E |

A first: everything after it is written once. C is independent and can slot anywhere. G is its
own `PLAN.md`, written from this file when A through E have landed and the campaign has been
played through once with the recap.

Rules that carry from `PLAN.md`'s "How to work": one action per step, full check per step,
goldens rebuilt once per phase and every changed line read, `src` counted at each phase's start
and end, one commit per phase, an adversarial review of the staged diff, and every rule verified
against the SRD page before it is built on.

## Left in `IDEAS.md`, on purpose

- Moving home (D.5), with its sketch.
- The eval loop (IDEAS 4): a script against live CLIs, the only way to answer "does it play
  better"; the tool cap and Track G's help rule are the first two questions it would settle.
- Pack authoring (13) and the demo GIF (11).
- Crew play for Breathless and Loner beyond what G leaves them.

## Refused in this round, with the reason

- A summarizer role: a fourth spawn per crossing for a paragraph the worldsmith already can
  write in the answer it gives.
- A "Previously…" narrator spawn on resume: the page opening at turn 1 was the bug (D.2).
- In-process Kokoro: torch or onnxruntime plus a 300 MB model in a seven-dependency project,
  untyped under strict pyright; the same model behind its HTTP port is Track C.
- Raising the cap for its own sake: no engine is blocked, and flattening arms is token-neutral
  and unmeasured.
- `Offer.follows`, a reputation counter, a second concurrent home: prose and the ledger do it.
