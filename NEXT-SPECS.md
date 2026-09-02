# NEXT-SPECS — after the hub

What comes after `PLAN.md` (campaigns with a home base) finishes with Phase 5. A list of
proposals, each with enough shape to become a `PLAN.md` phase; not a plan. Tracks are ordered; a
track's "Done when" is what its future phase is judged on. Written 2026-09-02 from a read of all
of `src/`, two Fable opinion rounds and two adversarial reviews, folded.

Counts at writing: `src` 10,115 lines (24XX 1,460, Loner 1,418, Breathless 1,341, Tunnel Goons
1,285, `scenes.py` 385, `hub.py` 216; the rest 5,510); 437 tests. Phase 4 adds about 130, so
the tracks start from about 10,245.

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

## Track A — one scene engine, three payloads

**What.** The three scene engines are one design copied three times: by `diff` after renaming,
Breathless' `worldsmith.py` differs from 24XX's by 18 lines of 256, Loner's by 49; `views.py` by
12 and 34 of 118; `world.py` by 65 and 97 of 265; `engine.py` by 8 and 10 of 109. Move the shared
design into `engines/scenes.py` once, generic over the cast and the player, and make Loner's
companions the party every scene engine has.

**Why.** About 700 lines of `src` go, and the next feature (Tracks B, D, G) is written once
instead of three times. Phase 3b stopped at the world-free part because settled 7 forbade a type
parameter; decision 1 lifts it. `core/model.py` is already generic on the payload.

**Shape**, all in `engines/scenes.py` unless named:

```python
class Person(Mutable):                       # every cast entry and every player sheet; 24XX's
    id: CheckedEntityId                      # and Breathless' cast type is Person itself
    name: str
    brief: str
    known: bool = False                      # player builders pass known=True; no override
    alive: bool = True
    def rows(self) -> Rows: return ()        # the sheet, as the master's entity line prints it
    def unwritten(self) -> str: return "" if self.alive else "alive"   # Loner adds full luck

class SceneCanon[C: Person](Mutable):        # cast, opening, present, hidden, source, hub, board
class SceneScenario[C: Person](Mutable):     # world: SceneCanon[C]; the scenario payload
class SceneWorld[C: Person, P: Person](Mutable):
    cast: dict[EntityId, C]
    player: P                                # known, never in cast, never listed in a run
    runs, source, hub, board                 # as today
    party: list[EntityId] = []               # Loner's `companions`, for every engine: in cast,
                                             # alive, unique; a subset of run.present in every
                                             # scene, home included
    # require, require_here, require_alive_here, here (player, then present), label, reveal:
    # Loner's bodies, which read the id off `player`, so nothing spells PLAYER_ID but new_game
class SceneState[C: Person, P: Person](Mutable):   # each engine's State subclasses it
    world: SceneWorld[C, P]                        # Loner adds `twist`

class SceneDraft[C: Person](Frozen): ...     # today's fields; cast: dict[EntityId, C]
class JobDraft[C](SceneDraft[C]): job: str = Field(min_length=MIN_JOB)
class HubDraft[C](SceneDraft[C]): offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)
class ReturnDraft[C](HubDraft[C]): debrief: str = Field(min_length=1)
```

Seam functions that take the state are typed on a function-level bound, `def known[S:
SceneState[Any, Any]](state: Game[S], entity_id) -> bool | None`, because `Game[P]` is
invariant. The `Any` is a generic bound; this track writes the exception into `CLAUDE.md`'s
"Do not use `Any`" line. Each engine's `build()` then passes them straight, with no adapter.

**The party, on plain values in `engines/core.py`** (Tunnel Goons reuses them in Track G):
the `JoinParty`/`LeaveParty` arm models (Loner's today), `join_party(party, one)` (alive, not
already in), `leave_party(party, one)`, `check_party(party, cast)` (in cast, alive, unique),
`party_rows(members) -> Rows` for the master's `THE PARTY (led by the player)` section and
`party_panel(members) -> Panel` for the sidebar; both replace Loner's "travels with the player"
line and "Travelling with" row. In this track only Loner registers the arms.

Shared functions in `scenes.py`, each today's body with the engine's constants as parameters:
`opening_draft(cast_type, kind)`, `opening_canon`, `apply_scene` (seeds `present` with the
party; refuses a draft that names a party member or the player; the trace of the crossing says
"and <names> travel there with the player", today Loner's only), `write_next(world, intent,
answer, *, role, guidance)` (24XX joins `BOARD_GUIDANCE` into `guidance` on every campaign
write, as Phase 2 did), `install_scene(world, written, *, finished_note: str)` (24XX
`JOB_DONE_NOTE`, Loner `GROWTH_NOTE`, Breathless `""`; Loner's `close_conflicts` stays in a
four-line wrapper), `render_worldsmith`, `render_opening(role, source, guidance, kind,
hub_phrase, cast_type)`, `build_scenario(file_type, engine_id, ...)` over `SceneScenario[C]`,
`scene_unmet` (`cast_unmet` + `Person.unwritten` + `hub_unmet`), `narrator_view(world)`,
`scene_panels(world, sheet_panels)` (the `player_view` frame: Character, the engine's panels,
This scene, Board, Party, Here, Trail, Jobs), row helpers for the master (`here_lines`,
`hidden_lines`, `entity_line` reading `Person.rows()`; each engine keeps its own ten-line
`master_sections` tuple, since 24XX's GEAR and Loner's glossary sit in different slots),
`new_game(canon, player, world_type)`, `check_game(packs, state, title)`, and the four world
arms `Reveal`, `Enter`, `Leave`, `Kill` with `reveal_hidden/enter/leave/kill(world, id)`:
`Leave` on a party member is refused ("leaves through `leave_party`"), `kill` drops one.
`CHANGE_WORLD`, `sentence`, `PLAYER_DEAD` move to `engines/core.py`.

Each engine keeps: its `Person` subclasses (`Operator`, `Survivor`, `LonerCharacter`), its
`State`/`Game`/`ScenarioFile`/`CharacterFile`, `player_*` builders, `WORLDSMITH`, `HUB_PHRASE`,
its note, `BOARD_GUIDANCE`, its SRD tools and arms, its panels and `master_sections`,
`pack_options`, and a `build()` that wires `partial`s.

Loner: `LonerWorld(SceneWorld[LonerCharacter, LonerCharacter])`; `companions` becomes `party`
and `player_id` goes; `new_game` stops listing the player in `present`; `roll_question` on the
player resolves through `require_alive_here`, which the base answers with `player`;
`conflict_prompt`, `close_conflicts`, `meanings` and the twist counter read `here()` and the
sheet as today.

Dead code, same phase: `ui/settings.py _without_none`, the `places` guard in Tunnel Goons
`walk`, 24XX `SRD_PACK`, `Known[G]` re-spelled in `engines/core.py`, `other_than` ×2 (to
`core/creation.py`).

**Docs that go false here**: the three `worldsmith.md` lines "the cast does not follow the
player from scene to scene" become "the party does; nobody else"; `docs/LONER-3E.md`'s
companion wording says `party`.

**Done when.** Green; the one-shot `narrator.txt` and `picture.txt` goldens unchanged;
`master.txt` unchanged but for the `THE PARTY` section; 24XX and Breathless `state/` and `save/`
fixtures gain `"party": []`; every Loner fixture re-read; each scene engine about 1,050;
`scenes.py` about 700; `src` about 9,550.

**Cost and risk.** About one implementer-day, split A (scenes.py and `engines/core.py`, opus)
then B (the three engines, parallel, sonnet). Risk: pydantic generics with a validator on the
base and subclass fields (already done by `SceneWorld` today, one level deeper here).

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
MIN_RECAP = 60
class NextDraft[C](SceneDraft[C]):          # a scene written in play, away from a return
    recap: str = Field(min_length=MIN_RECAP, description="One paragraph on the scene the player "
        "is leaving: what they did, what it cost, what they learned, what they missed. Read by "
        "the game master and by you, never by the player, so it may name the secret.")
class JobDraft[C](NextDraft[C]): ...
class SceneRun(Mutable): ...; recap: str = ""   # written when the player left
```

- `write_next` picks `ReturnDraft`, `JobDraft` or `NextDraft`; `HubDraft` and `ReturnDraft` do
  not recap: after a return `job_runs()` starts at the hub run, so the last job scene's recap
  would never be read, and the debrief covers it. A `JobDraft` recaps the hub visit like any
  scene ("paid the tab, took the crate run"): one sentence meets `MIN_RECAP`.
- `apply_scene` sets `world.run.recap = draft.recap` before the append.
- `scene_history`: a run with a recap prints its title, question, job line and `what happened:
  <recap>`; the live run prints its situation and every exchange (at most `SCENE_TURN_CAP`,
  about 1.8k tokens; today's 3-exchange tail was the cap the recap now removes). `told_tail`
  and `TAIL_EXCHANGES` then have one user, Tunnel Goons, and move there.
- Master: `recap_rows(world) -> Rows` gives `("EARLIER IN THIS JOB" | "EARLIER IN THIS
  ADVENTURE", "- <title>: <recap>" per recapped run of `job_runs()`)`, spliced by each engine's
  `master_sections` before `master_tail`; empty on the first scene.
- The narrator never sees a recap: `NarratorView` and `told_passages` do not change. The player's
  memory is the transcript, the debrief card and the `Jobs` panel.
- Tunnel Goons: none. Its worldsmith spawns only at the frontier, and the map (places, `alive`,
  `on`) is most of its memory. `recent_exchanges` stays 20 (decision 2).

**Done when.** A crossing stamps the recap on the run left; a job's third scene's master picture
names the first scene's outcome; `state/` and `save/` fixtures gain `"recap": ""` per run;
`master.txt` unchanged. About +50 lines. Zero extra spawns; the master reads about 120 tokens
per closed scene of the job. Built in one phase with Track D.

---

## Track C — voices

**What.** Narration and dialogue read aloud, generated after the turn commits, cached beside the
art, played under the newest exchange. Off by default. The narrator's voice is the scenario's.

**Why.** IDEAS 1: the largest player-experience gain per line left, and the illustration pattern
answers every design question (optional, provider-keyed, cached, failures only log).

**Shape.**

- `config.py`: `SpeechConfig(enabled=False, provider: ProviderName = "openrouter",
  model="openai/gpt-4o-mini-tts", voice="alloy", voices=("alloy", "ash", "coral", "onyx",
  "sage"), sample_rate=24_000, timeout=60.0)`: `voices` is the pool dialogue draws from, so a
  Kokoro user lists Kokoro's names; `Settings.speech`; `_keys_present` also checks the speech
  provider's key; `ProviderName` gains `"kokoro"` with `Providers.kokoro =
  ProviderConfig(base_url="http://localhost:8880/v1", api_key="none")`, because `local` is
  Ollama's port and serves no speech (`MediaConfig.provider` shares the literal; accepted). The
  settings page renders all of it for free.
- `Scenario.voice: str = ""` on the envelope (`core/model.py`, beside `art_style`), an input on
  the create page ("Narrator voice, empty for the default"), passed through `Authoring.build`
  with `art_style` (the shared `build_scenario` and Tunnel Goons'); `open_reader` takes
  `scenario.voice or settings.speech.voice`. A string, never a `Literal`.
- Endpoint: `POST {base_url}/audio/speech` with `{model, input, voice, response_format}`; the
  reply is raw audio bytes. OpenRouter serves it (`openrouter.ai/docs/guides/overview/multimodal/
  tts`, OpenAI-compatible, per character) with `response_format` `mp3` or `pcm`; Kokoro-FastAPI
  serves the same shape. Request `pcm` and wrap it with the stdlib `wave` at
  `speech.sample_rate`, 16-bit mono, so one client serves both; verify the format list and that
  `ui.audio` takes a local `Path` at phase start.
- `app/speech.py`, about 100 lines: `Reader` (not `Speaker`: taken by `core.play`) with
  `config`, `provider`, `saves`, `voice`, `generating`; `clip(exchange) -> Path | None`,
  `pending(exchange)`, `async read(exchange)`; `open_reader(settings, store, scenario)`; held on
  `GameService.voice`. `media.py`'s `_claim`, `_existing`, `_write` and the bearer POST become
  module functions both files import: two users now. One request per line: narration in the
  scenario's voice, dialogue in a voice from `voices` picked by `sha1(speaker.id)`, so a face
  keeps its voice as it keeps its icon; the lines are joined into one file keyed `sha1(model +
  "\n".join(f"{voice}|{text}"))[:12].wav` under `store.media_dir(slug) / "speech"`.
- Triggered where `illustrate` is: after `commit` in `play` and after a narrated crossing in
  `_install`. Cards, situations and debriefs are not spoken; a resumed game generates nothing
  for old exchanges (cache only).
- `ui/game.py`: `ui.audio(path, autoplay=True)` under the newest exchange in `chat`, `controls`
  only on older ones; `GameView.shown_clip` beside `shown_art` so the 3-second poll refreshes
  once, not on every tick; the timer runs when `media` or `voice` is set. About 20 lines.

**Done when.** With `SPEECH__ENABLED=true` and a key, a turn's narration plays within seconds of
the text in the scenario's voice, or the settings' when it names none; the file is reused on
reload; with the provider down, the turn is unaffected and one warning logs. About +180 lines.
No test spawns anything; the request builder, the wav wrap and the cache key are the tested
functions. The model (`gpt-4o-mini-tts` versus a Gemini TTS) is the maintainer's call at phase
start; the model string is a setting either way.

---

## Track D — campaign refinements, all cheap

Built in one phase with Track B. About +25 lines.

1. **A retaken job keeps its terms.** `TAKE_BRIEF` sends a retaken offer back to its place and
   cast, but the worldsmith rewrites `job` from the pitch, so pay and terms drift. `Stop.job:
   str` from `scene.job` (`""` in Tunnel Goons, whose job is the map); `Job.job` from the first
   job stop in `closed_jobs`' walk; `ledger` prints `the job: <job>` under an open job's line
   only; `TAKE_BRIEF` gains "with its cast and its terms".
2. **A resumed game opens at its end.** `game_page` never scrolls; a returning player lands on
   turn 1. A `ui.timer(0.5, lambda: transcript.scroll_to(percent=1.0), once=True)` in
   `game_page`, after the client connects. This is the "session recap on resume" of
   `COMPETITOR-RESEARCH.md`: the transcript under its last chapter heading. No narrator spawn.
3. **The save card says where you are.** `SaveOption.where: str`; `load_catalog` restores each
   save through `engine.restored(raw)` (its `ValueError` is already skipped; the home page now
   validates every save in full, seven today) and reads `history[-1].where if history else
   ""`; the card reads "Kael · turn 34 · Deck 9 — The Loading Bay".
4. **Jobs that connect** stay prose: `RETURN_BRIEF` already asks for an offer grown from the
   ledger. No `Offer.follows`.
5. **Moving home** stays in `IDEAS.md` with the sketch: `SceneWorld.hubs` tuple, `at_hub = place
   == hubs[-1]`, the walk tests membership, a `MOVE_HOME` row at the hub, `HubDraft` reused, a
   "New home: <title>" card; about 70 lines; no SRD prints it.

---

## Track E — the consistency audit

No behaviour change. Rides in one phase with Track F, about -25 lines. No tool fold: Breathless
`use_med_kit` into `change_stress` would make `amount` optional behind a flag for a count no
engine needs; Tunnel Goons `unlock_way` as an arm moves no count; 24XX `defend` and Loner
`restore_luck` stay tools (an arm runs during the conflict pause and would reset its clock).

- Delete the `hint` on Tunnel Goons' options steps (never shown).
- Layout: `core/views.py sections()` before its classes; `ui/game.py on_fact` public after
  private; `type` aliases (`core/model.py`, `engines/core.py`) into the constants block. The
  `WorldChange` unions, `DRIVERS`, `TURN_TOOLS` and Tunnel Goons' `Entity` must follow their
  classes: accepted, one comment each.
- Naming: Tunnel Goons `validate` → `check_game`; its `render_map`/`write_extension`/
  `install_extension` keep their names (a map is not a scene); the local `known` mappings in
  the worldsmith → `everyone`. `twentyfourxx.creation.guidance` reads neither argument: one
  line says it is kept for `partial` parity.
- `Counter.clamped` (one user, `adjust`) inlined; docstrings past one line trimmed where the
  code says the what.
- `CLAUDE.md`: "at most fifteen game-master tools, counted as tools plus `change_world` arms,
  the two shared party arms not counted; twenty in all for an engine whose SRD plays a crew,
  named in its `docs/<ENGINE>.md`".

Refused: making the platform's optional parameters required (`render_picture`,
`render_narrator`, `write_scenario`, `Turn.begin`, `illustration_request`): every one is used
in `tests/`; eight test edits for no behaviour.

---

## Track F — documentation

Same phase as Track E, after Phase 5 has deleted `HUB-SPECS.md`, `PLAN.md` and `PROGRESS.md`
(and skipped 5.2, decision 6).

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

## Order, budget, and what each phase leaves behind

| track | phases | `src` after (about) | needs |
|---|---|---|---|
| A — one scene engine, the party | 2 (scenes.py and core.py, then the three engines) | 9,550 | Phase 5 done |
| B + D — recap and campaign refinements | 1 | 9,625 | A |
| E + F — audit and docs | 1 | 9,600 | A |
| C — voices | 1 | 9,780 | none |
| G — the party, then crews | 5 | 10,400 | A, B, E |

A first: everything after it is written once. C is independent and can slot anywhere. G is its
own `PLAN.md`, written from this file when A through F have landed and the campaign has been
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
