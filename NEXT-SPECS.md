# NEXT-SPECS — after the hub

What comes after `PLAN.md` (campaigns with a home base) finishes with Phase 5. A list of
proposals, each with enough shape to become a `PLAN.md` phase; not a plan. Tracks are ordered; a
track's "Done when" is what its future phase is judged on. Written 2026-09-02 from a read of all
of `src/`, two Fable opinion rounds and one adversarial review, folded.

Counts at writing: `src` 10,115 lines (24XX 1,460, Loner 1,418, Breathless 1,341, Tunnel Goons
1,285, `scenes.py` 385, `hub.py` 216; the rest 5,510); 437 tests. Phase 4 adds about 130.

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
   arms every engine carries (Track G.1) not counted. Small folds are fine. An engine that
   plays a crew (Track G) may go to twenty in all; its `docs/<ENGINE>.md` says so.
5. **Campaign refinements are all built**, except moving home, which stays in `IDEAS.md`.
6. **`VISION.md` is deleted** after its non-goals and turn steps move. `COMPETITOR-RESEARCH.md`
   stays as a reference to other projects. PLAN.md Phase 5.2 (rewrite VISION's architecture)
   is skipped: Track F deletes the file.
7. **Party play (IDEAS 16) is in scope, in two layers.** A minimal party every engine gets:
   an NPC joins and follows the player, is interacted with, and every role reads it as part of
   the party the player leads; the master applies the engine's own help knob. Then engine
   layers on top: 24XX sheets, help dice, the ship and succession; Tunnel Goons goons who roll
   and level. Retires PLAN.md settled 17 (no companions gained) and 19's "no crew list"; closes
   `docs/24XX.md` deviations 1, 2 and 5.
8. Ponytail audit: dropped. Eval loop (IDEAS 4): stays in `IDEAS.md`.

Standing rules from `CLAUDE.md` bind every track: engines self-contained under 2,000 lines; one-way
imports; `core`/`turn`/`app`/`ui` know no world shape; only the narrator writes player-facing
text from revealed facts; only resolver code changes state or rolls; a bad answer is re-prompted
once; saves carry no version; no abstraction until two things need it; no building for later.

---

## Track A — one scene engine, three payloads

**What.** The three scene engines are one design copied three times: by `diff` after renaming,
Breathless' `worldsmith.py` differs from 24XX's by 18 lines of 256, Loner's by 49; `views.py` by
12 and 34 of 118; `world.py` by 65 and 97 of 265; `engine.py` by 8 and 10 of 109. Move the shared
design into `engines/scenes.py` once, generic over the cast and the player.

**Why.** About 700 lines of `src` go, and the next feature (Tracks B, D, G) is written once
instead of three times. Phase 3b stopped at the world-free part because settled 7 forbade a type
parameter; decision 1 lifts it. `core/model.py` is already generic on the payload.

**Shape**, all in `engines/scenes.py` unless named:

```python
class Person(Mutable):                       # every cast entry and every player sheet
    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False                      # player builders pass known=True; no override
    alive: bool = True
    def rows(self) -> Rows: return ()        # the sheet, as the master's entity line prints it

class Npc(Person): ...                       # 24XX and Breathless: the identical class, once

class SceneCanon[C: Person](Mutable):        # cast, opening, present, hidden, source, hub, board
class SceneWorld[C: Person, P: Person](Mutable):
    cast: dict[EntityId, C]
    player: P                                # id == PLAYER_ID, known, never listed in a run
    runs, source, hub, board                 # as today
    party: list[EntityId] = []               # who travels with the player (Loner's `companions`,
                                             # for every engine): in cast, alive, unique, never
                                             # the player; in every scene, home included
    # require, require_here, require_alive_here, here (player, party, present), label, reveal:
    # today's 24XX bodies. One hook, overridable, no callback:
    def authored_unmet(self, cast: Mapping[EntityId, C]) -> list[str]: ...  # alive; Loner: full luck

class SceneState[C: Person, P: Person](Mutable):   # each engine's State subclasses it
    world: SceneWorld[C, P]                        # Loner adds `twist`

class SceneDraft[C: Person](Frozen): ...     # today's fields; cast: dict[EntityId, C]
class JobDraft[C](SceneDraft[C]): job: str = Field(min_length=MIN_JOB)
class HubDraft[C](SceneDraft[C]): offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)
class ReturnDraft[C](HubDraft[C]): debrief: str = Field(min_length=1)
```

Seam functions that take the state are typed on a function-level bound, `def known[S:
SceneState[Any, Any]](state: Game[S], entity_id) -> bool | None`, because `Game[P]` is
invariant; the `Any` here is a generic bound, the exception Track E writes into `CLAUDE.md`.
Each engine's `build()` then passes them straight, with no adapter.

Shared functions, each today's 24XX body with the engine's constants as parameters:
`opening_draft(cast_type, kind)`, `opening_canon`, `apply_scene` (keeps `party` in every
scene, so Loner's companion block goes), `write_next(world, intent, answer, *, role, guidance,
board_guidance="")` (24XX joins `BOARD_GUIDANCE` on a return; computed inside, after the pick),
`install_scene(world, written, *, finished_note: str)` (24XX `JOB_DONE_NOTE`, Loner
`GROWTH_NOTE`, Breathless `""`; Loner's `close_conflicts` stays in a four-line wrapper),
`render_worldsmith`, `render_opening(role, source, guidance, kind, hub_phrase, cast_type,
board_guidance="")`, `build_scenario(file_type, engine_id, ...)`, `scene_unmet` (`cast_unmet` +
`authored_unmet` + `hub_unmet`), `narrator_view(world)`, `scene_panels(world, sheet_panels)` (the
`player_view` frame: Character, the engine's panels, This scene, Board, Here, Trail, Jobs;
"Travelling with" from `party`), `master_rows(world, *, sheet: Rows, extra: Rows)` (the
`master_sections` frame: SCENE, the question heading, YOU PLAY FOR, the engine's section such as
GEAR or BACKPACK, HERE, HIDDEN, Loner's glossary as `extra`, the secret, `master_tail`),
`entity_line(world, one, detail)` (reads `Person.rows()`; "travels with the player" from
`party`), `new_game(canon, player, world_type)`, `check_game(packs, state, title)`, and the six
world arms `Reveal`, `Enter`, `Leave`, `Kill`, `JoinParty`, `LeaveParty` with
`reveal_hidden/enter/leave/kill/join_party/leave_party(world, id)`; `kill` drops a dead member
from `party`. The arm models `JoinParty`/`LeaveParty` (Loner's today) live in `engines/core.py`,
since Tunnel Goons registers them in Track G; in this track only Loner does. `CHANGE_WORLD`,
`sentence`, `PLAYER_DEAD` move to `engines/core.py`. `Entity` (the protocol) gains `brief`.

Each engine keeps: its `Person` subclasses (`Operator`, `Survivor`, `LonerCharacter`), its
`State`/`Game`/`ScenarioFile`/`CharacterFile`, `player_*` builders, `WORLDSMITH`, `HUB_PHRASE`,
its note, `BOARD_GUIDANCE`, its SRD tools and arms, its own panels and master section, and a
`build()` that wires `partial`s.

Loner: `LonerWorld(SceneWorld[LonerCharacter, LonerCharacter])`; `companions` becomes the
base's `party` and `player_id` goes; `new_game` stops listing `PLAYER_ID` in `present`;
`roll_question` on the player resolves through `require_alive_here(PLAYER_ID)`, which the base
answers with `player`; `conflict_prompt`, `close_conflicts`, `meanings` and the twist counter
read `here()` and the sheet as today.

Dead code, same phase: `ui/settings.py _without_none`, the `places` guard in Tunnel Goons
`walk`, 24XX `SRD_PACK`, `Known[G]` re-spelled in `engines/core.py`, `other_than` ×2 and
`pack_options` ×3 (to `core/creation.py`).

**Done when.** Green; the one-shot `narrator.txt` and `picture.txt` goldens unchanged;
`master.txt` unchanged; every Loner fixture (`state/`, `save/`, `turn/`, `prompts/`) re-read: the
world re-keys, the prompts change only if a cast line's shape does; each scene engine about
1,050; `scenes.py` about 700; `src` about 9,400.

**Cost and risk.** About one implementer-day, split A (scenes.py, opus) then B (the three
engines, parallel, sonnet). Risk: pydantic generics with a validator on the base and subclass
fields (already done by `SceneWorld` today, one level deeper here).

---

## Track B — memory: the scene recap

**What.** When the worldsmith writes the next scene it also writes one paragraph on the scene the
player is leaving. That paragraph replaces the scene's exchanges in every later prompt.

**Why.** The master's RECENT PLAY is the last 20 exchanges across the save; the worldsmith's
SCENES SO FAR keeps 3 exchanges per scene. A three-scene job at `SCENE_TURN_CAP` is 36 turns,
so the job's opening is gone before the return; a one-shot has no ledger at all. The campaign
ledger (`Debrief`) compacts across jobs; this compacts inside one.

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

- `write_next` picks `ReturnDraft`, `JobDraft` or `NextDraft`; `opening_draft` alone keeps
  `SceneDraft`/`HubDraft`. A `JobDraft` recaps the hub visit like any scene ("paid the tab, took
  the crate run"): one sentence meets `MIN_RECAP`.
- `apply_scene` sets `world.run.recap = draft.recap` before the append.
- `scene_history`: a run with a recap prints its title, question, job line and `what happened:
  <recap>`; the live run prints its situation and every exchange (at most `SCENE_TURN_CAP`,
  about 1.8k tokens; today's 3-exchange tail was the cap the recap now removes).
- Master: `recap_rows(world) -> Rows` gives `("EARLIER IN THIS JOB" | "EARLIER IN THIS
  ADVENTURE", "- <title>: <recap>" per recapped run of `job_runs()`)`, spliced by `master_rows`
  before `master_tail`; empty on the first scene.
- The narrator never sees a recap: `NarratorView` and `told_passages` do not change. The player's
  memory is the transcript, the debrief card and the `Jobs` panel.
- Tunnel Goons: none. Its worldsmith spawns only at the frontier, and the map (places, `alive`,
  `on`) is most of its memory. `recent_exchanges` stays 20 (decision 2).

**Done when.** A crossing stamps the recap on the run left; a job's third scene's master picture
names the first scene's outcome; `state/` and `save/` fixtures gain `"recap": ""` per run;
`master.txt` unchanged. About +50 lines. Zero extra spawns; the master reads about 120 tokens
per closed scene of the job.

---

## Track C — voices

**What.** Narration and dialogue read aloud, generated after the turn commits, cached beside the
art, played under the newest exchange. Off by default. The narrator's voice is the scenario's.

**Why.** IDEAS 1: the largest player-experience gain per line left, and the illustration pattern
answers every design question (optional, provider-keyed, cached, failures only log).

**Shape.**

- `config.py`: `SpeechConfig(enabled=False, provider: ProviderName = "openrouter",
  model="openai/gpt-4o-mini-tts", voice="alloy", sample_rate=24_000, timeout=60.0)`;
  `Settings.speech`; `_keys_present` also checks the speech provider's key; `ProviderName` gains
  `"kokoro"` with `Providers.kokoro = ProviderConfig(base_url="http://localhost:8880/v1",
  api_key="none")`, because `local` is Ollama's port and serves no speech. The settings page
  renders all of it for free.
- `Scenario.voice: str = ""` on the envelope (`core/model.py`, beside `art_style`), an input on
  the create page ("Narrator voice, empty for the default"), passed through `Authoring.build`
  with `art_style` (one shared `build_scenario` after Track A, plus Tunnel Goons); `open_reader`
  takes `scenario.voice or settings.speech.voice`. Voice names are the provider's (`alloy`,
  `ash`, `coral`, `onyx`, `sage`… for OpenAI's models); a string, never a `Literal`.
- Endpoint: `POST {base_url}/audio/speech` with `{model, input, voice, response_format}`; the
  reply is raw audio bytes. OpenRouter serves it (`openrouter.ai/docs/guides/overview/multimodal/
  tts`, OpenAI-compatible, per character) with `response_format` `mp3` or `pcm`; a Kokoro-FastAPI
  server serves the same shape. Request `pcm` and wrap it with the stdlib `wave` at
  `speech.sample_rate`, 16-bit mono, so one client serves both; verify the format list at
  phase start.
- `app/speech.py`, about 120 lines, mirroring `media.py`: `Reader` (not `Speaker`: taken by
  `core.play`) with `config`, `provider`, `saves`, `voice`, `generating`; `clip(exchange) ->
  Path | None`, `pending(exchange)`, `async read(exchange)`; `open_reader(settings, store,
  scenario)`; held on `GameService.voice`. One request per line: narration in the scenario's
  voice, dialogue in a voice from a fixed `VOICES` tuple picked by `sha1(speaker.id)`, so a face
  keeps its voice as it keeps its icon; the lines are joined into one file keyed
  `sha1(model + "\n".join(f"{voice}|{text}"))[:12].wav` under `store.media_dir(slug) /
  "speech"`.
- Triggered where `illustrate` is: after `commit` in `play` and after a narrated crossing in
  `_install`. Cards, situations and debriefs are not spoken; a resumed game generates nothing
  for old exchanges (cache only).
- `ui/game.py`: `ui.audio(path, autoplay=True)` under the newest exchange in `chat`, `controls`
  only on older ones; `GameView.shown_clip` beside `shown_art` so the 3-second poll refreshes
  once, not on every tick; the timer runs when `media` or `voice` is set. About 20 lines.

**Done when.** With `SPEECH__ENABLED=true` and a key, a turn's narration plays within seconds of
the text in the scenario's voice, or the settings' when it names none; the file is reused on
reload; with the provider down, the turn is unaffected and one warning logs. About +200 lines.
No test spawns anything; the request builder, the wav wrap and the cache key are the tested
functions. The model (`gpt-4o-mini-tts` versus a Gemini TTS) is the maintainer's call at phase
start; the model string is a setting either way.

---

## Track D — campaign refinements, all cheap

Built together in one phase after Track A. About +25 lines.

1. **A retaken job keeps its terms.** `TAKE_BRIEF` sends a retaken offer back to its place and
   cast, but the worldsmith rewrites `job` from the pitch, so pay and terms drift. `Stop.job:
   str` from `scene.job` (`""` in Tunnel Goons, whose job is the map); `Job.job` from the first
   job stop in `closed_jobs`' walk; `ledger` prints `the job: <job>` under an open job's line
   only; `TAKE_BRIEF` says a retaken job keeps the terms JOBS SO FAR prints.
2. **A resumed game opens at its end.** `game_page` never scrolls; a returning player lands on
   turn 1. A `ui.timer(0.5, lambda: transcript.scroll_to(percent=1.0), once=True)` in
   `game_page`, after the client connects. This is the "session recap on resume" of
   `COMPETITOR-RESEARCH.md`: the transcript under its last chapter heading. No narrator spawn.
3. **The save card says where you are.** `SaveOption.where: str`; `load_catalog` restores each
   save through `engine.restored(raw)` (its `ValueError` is already skipped) and reads
   `history[-1].where if history else ""`; the card reads "Kael · turn 34 · Deck 9 — The
   Loading Bay".
4. **Jobs that connect** stay prose: `RETURN_BRIEF` already asks for an offer grown from the
   ledger. No `Offer.follows`.
5. **Moving home** stays in `IDEAS.md` with the sketch: `SceneWorld.hubs` tuple, `at_hub = place
   == hubs[-1]`, the walk tests membership, a `MOVE_HOME` row at the hub, `HubDraft` reused, a
   "New home: <title>" card; about 70 lines; no SRD prints it.

---

## Track E — one fold and the consistency audit

No behaviour change except the fold. One phase, about -40 lines.

**Fold.** Breathless `use_med_kit` folds into `change_stress(med_kit: bool)`: a validator refuses
`amount` with `med_kit`, the 2 stays in code. The current description's "never a stand-in for
`use_med_kit`" exists because the master confused the two. 13 verbs → 12.

Refused: 24XX `defend` as an arm (the count does not move and the SRD's Defend leaves the tool
list); Loner `restore_luck` as an arm (an arm runs during the conflict pause and would reset the
clock mid-conflict); Tunnel Goons `unlock_way` as an arm (9 verbs before and after, only churn);
a shared `test_luck` body (two five-line bodies with different ladders).

**Audit findings to fix** (grep-traced; the schema audit found every field read):

- Delete the `hint` on Tunnel Goons' options steps (never shown).
- Layout: `core/views.py sections()` before its classes; `ui/game.py on_fact` public after
  private; `type` aliases (`core/model.py`, `engines/core.py`) into the constants block. The
  `WorldChange` unions, `DRIVERS`, `TURN_TOOLS` and Tunnel Goons' `Entity` must follow their
  classes: accepted, one comment each.
- Naming: Tunnel Goons `validate` → `check_game`; its `render_map`/`write_extension`/
  `install_extension` keep their names (a map is not a scene); the local `known` mappings in
  the worldsmith → `everyone`. `twentyfourxx.creation.guidance` reads neither argument: one
  line says it is kept for `partial` parity.
- `Any`: nine sites, all generic bounds or the `Any*` aliases; `Game[P]` is invariant, so they
  are the exact type. Write the exception into `CLAUDE.md` rather than leave the rule false.
- `Counter.clamped` (one user, `adjust`) inlined; docstrings past one line trimmed where the
  code says the what.
- `CLAUDE.md`: "at most fifteen game-master tools, counted as tools plus `change_world` arms,
  the two shared party arms not counted; twenty in all for an engine whose SRD plays a crew,
  named in its `docs/<ENGINE>.md`".

---

## Track F — documentation

One phase, no `src` change, after Phase 5 has deleted `HUB-SPECS.md`, `PLAN.md` and
`PROGRESS.md` (and skipped 5.2, decision 6).

1. **`VISION.md` is deleted.** What only it says moves first: the non-goals (shared world layer,
   save migration, the built-in loop and the state keeper, retrieval) into `CLAUDE.md`'s design
   decisions, one line; "how a turn runs" into `CLAUDE.md`, three bullets; content paths and
   "play costs the subscription, illustration is the exception" into `README.md`; Maze Rats
   (`2c3e8a5`, `62f95c6`) and the Pokémon–Showdown boundary into `IDEAS.md`. The seam member
   list duplicates `engines/core.py` and goes; MVP0 and the after-MVP0 lists are done or in
   `IDEAS.md`. Then `README.md`'s link and `pyproject.toml`'s `extend-exclude` entries.
2. **`README.md`** gains one architecture paragraph (the three roles, the seam, the one-way
   imports) beside the campaign paragraph Phase 5 wrote.
3. **`IDEAS.md`**: delete 15 (done), 12 (item 1 targets a skill that no longer exists, item 2 is
   D.2), 3 and 9 (refused by the non-goals), the built-in half of 4; fold 5, 6, 7, 8, 14 into one
   "audit" line that Track E closes; keep 4's eval loop, 11, 13, moving home (D.5).
4. **`COMPETITOR-RESEARCH.md`** stays as the reference to other projects; one dated note at the
   top says the "ours" columns, `ROADMAP.md`, "code mode" and `.agents/skills` are stale.
5. **Engine docs, one shape** (IDEAS 14): every `docs/<ENGINE>.md` in the same section order
   (sources, licence, packs, tools, deviations, readings, what the app adds, where the rules
   live). 24XX has it; the other three are reordered, not rewritten.

**Done when.** Every document says what the code does; no document holds rules text; `grep -r
VISION` finds nothing.

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

- **Platform share, two things, as the hub had two.** `NarratorView.party: tuple[Subject,
  ...]`, the player first then who travels with them, a subset of `subjects` (who the player
  is, not a world shape); `render_narrator` prints `YOUR PARTY: you are <name>; with you: <names
  or nobody>`. The `Illustrator` takes the player from it. Nothing else in `core`, `turn`, `app`
  or `ui` changes: the panel is a `Panel`, the arms are `change_world` arms.
- **Shared engine code** (`engines/core.py`): the `JoinParty`/`LeaveParty` arm models (Track
  A moved them there), `party_lines(members) -> str` for the master's `THE PARTY (led by the
  player)` section, `party_panel(members) -> Panel` for the sidebar. Scene worlds have
  `SceneWorld.party` from Track A; `TunnelWorld.party: list[EntityId]` (npcs, alive, unique)
  is added here, and `move` carries the party with the player, `with_ids` staying for an NPC
  who follows once.
- **Registration.** 24XX and Breathless register the two arms (15 → 17, 12 → 14, the pair not
  counted per Track E's `CLAUDE.md` line); Tunnel Goons too (9 → 11); Loner already has them.
  Joining needs the member alive and present; leaving needs them in the party; `kill` drops
  them. The player's death ends the game as today until an engine adds succession.
- **What the master reads**, one shared paragraph in each `rules.md`: a party member is the
  player's to command in the fiction and yours to voice; when one plainly helps, that is the
  engine's help — 24XX `helped`, Loner `position`/`edge`, Tunnel Goons a lower `difficulty` or
  a named item, Breathless nothing (the SRD prints no help rule; the fiction carries it); a
  member cannot act on their own dice unless the engine gives them some (G.2, G.3); never
  volunteer a member's action to soften a scene.
- **Worldsmith.** `TAKE_BRIEF`'s "anyone from the hub's cast the player names is present" stays
  for non-members; the party is in every scene without being listed.

### G.2 24XX crew

- **Who can roll.** 24XX's cast type becomes `Regular(Npc)` with `sheet: TwentyfourxxCharacter
  | None = None` (the character file's own payload; the SRD's specialties are the vocabulary),
  so `scenes.Npc` stays one class. `join_party` on a sheeted regular also moves them from `cast`
  into `crew: dict[EntityId, Operator]` (same id, so icon and transcript hold; credits 0; kit
  from the sheet); `leave_party` moves an operator back to `cast` as a `Regular` with the sheet
  they now carry. An unsheeted member follows and helps as G.1; only an operator rolls.
  `require()` searches `player`, `crew`, `cast`. `apply_scene` refuses a draft id that is in
  the party or the crew. `PARTY_MAX = 3` members (prompt size, not SRD). In a campaign a
  sheeted join is refused away from the hub: hiring is the fixer's business.
- **Rolls.** `Attempt.actor_id: CheckedEntityId = PLAYER_ID` (the player or a crew operator);
  `Attempt.helped_by: CheckedEntityId | None` names one crew operator: they roll their own die
  for the named skill (d6 when they lack it, d4 when their `hindrances` is non-empty) beside
  the actor's, and the highest counts; `helped` (circumstance) stays the extra d6; both may
  apply. "Share the risk" is the master's: the consequence lands on the actor by code
  (`risking_death`, `Maimed`), and `rules.md` says the helper takes a hindrance through
  `change_hindrances` when the fiction puts it on them. `Defend.actor_id`,
  `ChangeHindrances.entity_id`, and `actor_id` on `GainItem`/`DropItem`/`RepairItem`/`Spend`
  default to the player: gear and credits are per operator, as the SRD keeps them.
- **After a job.** The job's first scene stamps `Scene.crew: tuple[EntityId, ...]` (code, the
  operators as they left the hub). `JobDone.raises: tuple[Raise(actor_id, skill), ...]` covers
  the player and every stamped operator still alive, refused when one is missing or a stranger
  is named; each raises the named skill and rolls their own d6 credits. One call per job.
- **The ship.** `world.ship: Ship | None`; `Ship.functions: dict[ShipFunction, Function(upgraded:
  bool = False, broken: bool = False)]` over the seven printed functions. The worldsmith answers
  `ship: bool` on the opening draft; code builds the seven. `ship_upgrade(function)` costs the
  player ₡10; `ship_repair(function, cost)`; `Defend` takes exactly one of `item_id` or
  `ship_function`. A `Ship` panel shows when there is one.
- **Succession.** When the player dies with a living crew operator, the death site sets
  `PendingDecision(kind="succession", prompt="Who leads now?", options=one PendingOption per
  living operator with name="change_world", args={"change": {"verb": "take_lead", "actor_id":
  ...}}, allows_text=False)` instead of ending the game; `take_lead` swaps the sheets: the chosen
  operator becomes `world.player` and the dead one joins `crew`, both keeping their ids, so the
  invariant becomes `player.id not in cast` and every `PLAYER_ID` read that means "the player"
  (24XX 25 sites, `engines/core.py labeled/counter_fact/reveal`) reads `world.player.id`.
  `player_over` fires only when the player and every operator are dead. `NarratorView.party`
  carries the new "you" with no further change.
- **Counts.** Arms: `join_party`, `leave_party` (G.1), `take_lead`, `ship_upgrade`,
  `ship_repair`. 24XX goes 15 → 20.
- **Views and prompts.** The `Party` panel shows an operator's `rows()`, hindrances, "dead";
  the master's `THE PARTY` prints sheets for operators; `creation.py _AUTHORING` ("the cast
  carries no dice") and the `attempt` description are rewritten; `worldsmith.md` says a sheet is
  for someone who could plausibly be hired, at most one per scene.

### G.3 Tunnel Goons crew

`Npc.sheet` is the three abilities; a sheeted member is a goon: `ActionRoll.actor_id`, `rest`
heals the party, `level_up` opens one decision per living goon in turn, `take_lead` swaps
sheets as 24XX. `Dungeon._consistent`'s item-holder check moves to `TunnelWorld` and reads the
party, and `entity()`/`known()` search it. 11 → 12. `docs/TUNNEL-GOONS.md` deviation 1 (one
goon) closes.

### G.4 Phases, in order

1. The party: `NarratorView.party`, `render_narrator`, `party_lines`/`party_panel`, the arms in
   24XX, Breathless and Tunnel Goons, `TunnelWorld.party` and `move`, the shared `rules.md`
   paragraph; goldens: `narrator.txt` gains the YOUR PARTY line, `master.txt` the section and
   the paragraph, `master_tools.json` the two arms, nothing else.
2. 24XX: `Regular`, `crew`, `actor_id` on the tools, `helped_by`, `Scene.crew` and
   `JobDone.raises`, the panel rows, `rules.md`, `_AUTHORING`, `worldsmith.md`, `docs/24XX.md`.
3. 24XX: the ship and succession; `scenarios/amber-tap` gains a sheeted regular and a ship.
4. Tunnel Goons: G.3.
5. Docs; `IDEAS.md` 16 leaves.

**Done when.** In every engine a named NPC joins, walks into the next scene and is read as the
party by all three roles; a hired regular rolls beside Kael and the highest die counts; Kael dies
on a `risking_death` disaster and the page asks who leads; the new lead plays the return home
and `job_done` raises both survivors; the hull breaks to defend; 24XX at most 1,600 lines after
Track A, twenty verbs. About +500 lines across `core/views.py`, `turn/context.py`,
`engines/core.py`, `scenes.py`, 24XX and Tunnel Goons.

**Risks.** Prompt size grows by one entity line per member per role; `PARTY_MAX` bounds it. The
narrator must keep "you" on the player: the golden and one speakers test guard it. The crew must
not soak every risk: `helped_by` is one ally, and the shared paragraph forbids volunteered
member actions.

---

## Order, budget, and what each phase leaves behind

| track | phases | `src` after (about) | needs |
|---|---|---|---|
| A — one scene engine | 2 (scenes.py, then the three engines) | 9,400 | Phase 5 done |
| B — recap | 1 | 9,450 | A |
| D — campaign refinements | 1 | 9,475 | A |
| E — fold and audit | 1 | 9,435 | A |
| C — voices | 1 | 9,635 | none |
| F — docs | 1 | 9,635 | E (for `CLAUDE.md`) |
| G — the party, then crews | 5 | 10,150 | A, B, E |

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
- Making the platform's optional parameters required: every one is used in `tests/`; eight
  test edits for no behaviour.
- `Offer.follows`, a reputation counter, a second concurrent home: prose and the ledger do it.
