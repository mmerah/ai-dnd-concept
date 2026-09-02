# PROPOSALS — conceptual simplification (round 2, 2026-09-02)

Round 1: six independent reads of `src/aidm` (the lead and five reviewers, each with a
different emphasis) inventoried every concept and gave a verdict per concept; what at least one
proposed as a change became P1 to P11 plus a tier of single-voice ideas. Round 2: three
adversarial reviewers attacked the file for correctness (file:line evidence), coverage (every
engine, role, page, Track G) and over-engineering (is the replacement smaller than what it
replaces), and each listed simplifications the round had missed. This file is round 2's result:
every proposal corrected, two dropped, one shrunk, and the missed ones added as M1 to M8.

Each entry is written to become a spec: what exists, what replaces it, what is deleted, what is
lost, which goldens move, and the one decision it needs. Line counts were recounted with `wc` and
`grep` in round 2; round 1's were about twice too high on P1, P2 and P5.

## Standing corrections from round 2

- The narrator never receives a recap. `NextDraft.recap` "may name the secret"
  (`drafts.py:36`). Every history proposal has a narrator variant that prints revealed
  narration only, without the `> prompt` lines, or the `BEGUN`/`CROSSED` markers would read as
  the player's words.
- Track G is next. P3 deletes the chain G.3 needs (one level-up decision per goon, "answering one
  opens the next"); P6 deletes the runtime net G.2 and G.3 add about fifteen `entity_fact` sites
  behind; P5's shared `kill` arm meets G.2's succession. Each says so below; none is blocked.
- NEXT-SPECS decision 2 says `recent_exchanges` stays at 20. P1 deletes the setting and keeps
  20 as a constant cap; that is a change to a recorded decision and is flagged.
- Anything that changes a stored shape stales saves, which the design allows, and also rewrites
  the shipped `scenarios/*/world.json` (eight files) and the fixtures under `tests/core/fixtures`
  where named. "Saves go stale" alone was too cheap a sentence in round 1.

## Decisions taken (maintainer, 2026-09-02)

- P4 cold spawns: yes. CLAUDE.md's "the app resumes its session each turn" is reversed when
  it lands.
- P10 delete the settings page: no. The page stays; the proposal is removed from this file.
- P6 delete the duplicated guards: yes, now, before Track G.

## Tier 1 — consensus, corrected

### P1. One history, one renderer, scene by scene

Round 1: 6/6. Round 2: sound with fixes. About −50 lines net (not −150), −5 concepts. One day.
Do after P4, which rewrites the same `render_picture`.

Today the same exchanges are rendered four ways: the master's RECENT PLAY (last
`recent_exchanges`, with a `[at where]` tag), the narrator's WHAT THE PLAYER HAS READ (last N
narrations), the worldsmith's SCENES SO FAR (`scene_history(job_runs())`: recap if closed, all
exchanges if open, scoped to the open job) and Tunnel Goons' return prompt (every visit of the
job, last three exchanges each). `Exchange.where` is excluded from the save and rebuilt by the job
walk with a `model_copy` per exchange on every read (`scenes/world.py:209`,
`tunnelgoons/world.py:273`), five or six times a turn.

Proposal: the engine's `history()` keeps returning the flat exchanges (`unopened`, `_newest`,
`_latest_narration`, the journal, `Reader.clip` and `test_store` need it) and gains `scenes()`:
a frozen record per scene with `title`, `question`, `recap` (empty while open or where none was
written) and `exchanges`. Scene engines map runs; Tunnel Goons builds one per visit, resolving
the title through the world. One function renders it for every role: a `SCENE: title` heading
per scene; the current and the previous scene printed whole, capped at 20 exchanges each
(the hub scene and Tunnel Goons have no turn cap, so "whole" must be bounded); every older scene
as its recap, or where it has none (the scene the player came home from, since `ReturnDraft` is
a `HubDraft` and writes no recap; every Tunnel Goons visit; the opening before it is left) as its
title and last three exchanges, which is what `_told_tail` does today. The window is the current
job (`job_runs()`, `job_visits()`); older jobs reach the master and the worldsmith through the
ledger, as `recap_rows` and `master_tail` do now. The narrator's variant prints narration only,
scene-bounded, never a recap. The chat's heading loop and the launcher's "where" read the last
record's title. `question` is on the record because SCENES SO FAR is the only place the
worldsmith sees the current scene's question.

Deleted: `_recent`, `_recent_exchange`, `told_passages`, `scene_history`, `_told`,
`recap_rows`, `_told_tail`, `TAIL_EXCHANGES`, `hub.heading`, `Exchange.where` and both
`exchanges()` stampers, `Settings.recent_exchanges`, `Turn.recent` and the `recent` argument
threaded through `GameService.play`, `Turn.begin` and `render_picture`, `GameService.settings`
(its only two uses), `NarratorView.art_prompt` (both builders are title + situation + subjects;
`media.py` builds it).

Lost: the master's flat "last 20 across scenes" becomes "this scene and the last one, then
recaps"; the recap the worldsmith writes on the crossing is the compaction, as the seed asked.

Goldens: `prompts/*/picture.txt`, `narrator.txt`; `test_scenes.py:57`,
`test_launcher.py:171-181`, `test_settings.py:28` read what goes.

Decision: keeping 20 as a constant reverses NEXT-SPECS decision 2's "setting"; the number
stays.

### P2. Jobs are one stored list

Round 1: 5/6. Round 2: broken as written for Tunnel Goons; sound as one list. About −80 lines
net (not −150); seven of `test_hub.py`'s 22 tests go. One day. Do with M8 or not at all.

Today a job is a pattern over the scene list: `Scene.debrief` and `Scene.job` (scenes) or
`Visit.job`, `Visit.debrief` and `TunnelWorld.job_done` (Tunnel Goons) are read into a `Stop`
adapter, then `job_titles`, `job_start` and `closed_jobs` rebuild the ledger on every read, and
two `check_hub` validators police placement. The verdict lives in five places
(`NextScene.job_done`, `SceneRun.job_done`, `SceneWorld.job_done`, `TunnelWorld.job_done`,
`Debrief.finished`), and 24XX has a tool also named `job_done` that means the SRD's after-job
step, not the verdict.

Proposal: `world.jobs: list[Job]`, one list, no second field. `Job` carries `title`, `place`,
`terms`, `started` (the index of the first run or visit away from the hub; `None` until the
player walks out, which is Tunnel Goons' "a stamp still sitting at the hub is not yet taken",
`tunnelgoons/world.py:317`), `finished` (set by `next_scene(job_done)` or `level_up`) and
`debrief: Debrief | None`. The open job is `jobs[-1]` while its debrief is `None` and it has
started. `job_runs()` and `job_visits()` stay as `runs[jobs[-1].started:]`; mid-job tavern
visits (`test_hub.py:49-56`) are allowed by that. The scene keeps title, question, situation and
secret only. Rename 24XX's `job_done` tool `after_job` so the master reads one word for the
verdict.

Deleted: `Stop`, `job_titles`, `job_start`, `closed_jobs`, `heading`, `stops()`,
`Scene.debrief`, `Scene.job`, `Visit.job`, `Visit.debrief`, the three `job_done` flags and the
`job` property, `job_open()`, the placement arms and the "job with no hub" arms of both
`check_hub`. G.2's `JobDone.raises` "one call per job" gets a `raised` flag on the same record
later.

Lost: one derived source of truth becomes an append-only list written at two sites (job
install, return install) plus one `started` write on the first move out; a five-line validator
still checks it.

Goldens: `fixtures/state/*.json` (eight) and `fixtures/save/*.json` (four) carry `debrief`
and `job`; the shipped scenarios do not.

Decision: the tool rename touches `docs/24XX.md` and Track G.2.

## Tier 2 — majority, corrected

### P3. Delete the dead suspension path; fold `resumed` into a note

Round 1: 4/6. Round 2: sound; best ratio in the file. About −35 lines, −3 concepts. Half an
hour.

`during_suspension` (nine mentions, six files) and `Turn.suspended_at_start` exist so a world
change can land in a turn whose option answer re-suspended. `consume_answer` clears `pending`
on every input (`run.py:195`); the flag matters only when an option's own resolution opens a
new decision, and no shipped resolver does that (loot options resolve flat, a level-up option
arrives with both args, the Loner conflict decision is text-only). Only the synthetic
`CHAIN_THE_HIT` in `test_decisions.py:39` reaches it. `Turn.resumed` and the "THE PLAYER'S
DECISION, ALREADY RESOLVED" section are a second channel for what the notes already carry in the
text-answer case; `consume_answer` runs before `turn.notes` is read, so a note lands this turn.
`ANSWERED_BY_OPTION` stays as PLAYER ACTION, or `test_context_boundary.py:103` breaks.

Lost: nothing shipping. G.3's level-up chain ("answering one opens the next") is exactly the case
this deletes for; record in NEXT-SPECS that G.3 re-adds a re-suspension path when it needs it.

Goldens: `picture.txt` (the section goes).

### P4. Cold spawns: no session resume, no `start_turn`

Round 1: 4/6. Round 2: sound with fixes; the strongest argument was missing. About −180 source
lines and `test_session.py`, −9 concepts. One day. Reverses a CLAUDE.md decision.

Today `Conversations` keeps a `.sessions` sidecar with a fingerprint per role, retries cold when
a resumed role fails, and is forgotten on every failure path. Because the master is resumed, its
spawn prompt holds no world, and it calls `start_turn` over MCP to get the picture; `scene`
recovers after mid-turn compaction; `started`, `START_FIRST` and `ALREADY_OPEN` police the
order. The missing argument: `render_master` sends YOUR ROLE and THE RULES OF THIS GAME on every
resumed turn (`context.py:24-32`), so a resumed master's transcript at turn N is the cold prompt
plus N−1 stale copies of the rules and N−1 pictures with their tool traffic. Cold is fewer tokens
from turn 2 onward, and the ROLE + RULES prefix is the same bytes every spawn, so prompt-cache
reads are available cold too. The narrator gets its history twice, once by resume and once as
WHAT THE PLAYER HAS READ. Codex already runs the master cold.

Proposal: every spawn is cold; the picture is the spawn prompt. `answered` keeps its
within-retry session (`RunResult.session`), which is the CLI's concept and saves re-sending a
30k-token worldsmith prompt on a refusal. Keep `nothing_landed`: `_act`'s except branch decides
raise-versus-commit with it (`runtime.py:210`, two pipeline tests). Keep one cold retry of the
master when nothing landed; today `cold_retry` is its only retry.

Deleted: `app/sessions.py`, `FileStore.sessions_path`, the `cold_retry` argument, four `forget`
calls, `TurnTool`, `TURN_TOOLS`, `start_turn`, `scene`, `Turn.started`, the two constants, the
`render_master`/`render_picture` split, the Codex master special case, `master.md`'s first
paragraph. `published_tools()` returns `()` with no turn open (`test_tool_surface.py:546`).
One class of bug goes with it: a role that remembers a turn that was thrown away.

Lost: the master's own refusals and intentions from the prior turn (it may repeat a bad id once);
`Game.notes` survives. Stale `saves/.sessions/*.json` on disk are harmless.

Goldens: `master.txt` (four), `picture.txt`.

Decision: taken, yes. The over-engineering reviewer held no measurement is needed; the
correctness reviewer held the cache claim is doubtful either way; the maintainer decided on
memory, not tokens.

### P5. Three zero-hook chores in the scene engines (was: fold into `SceneEngine`)

Round 1: 4/6. Round 2: over-engineered; the hook version re-proposed the `SceneRules` surface
NEXT-SPECS refused. About −60 lines. Two hours.

`breathless/worldsmith.md` and `twentyfourxx/worldsmith.md` are byte-identical; Loner's adds one
rule and replaces one paragraph, both restating its `_AUTHORING`, which the prompt already
carries under ENGINE GUIDANCE. `CHANGE_WORLD` is redefined verbatim in Tunnel Goons. Both
`record` implementations build the same `Exchange`. The three `master_sections` differ by one
section each in different positions (Loner's glossary sits between HIDDEN and SECRET; GEAR and
BACKPACK follow YOU PLAY FOR), so one hook cannot hold them without moving a section; the shared
arm dispatch is eight lines each and a generic `ChangeWorld` over a per-engine union would need
a runtime-parametrised discriminator with the `master_tools.json` goldens required not to move.

Proposal: (a) one `scenes/worldsmith.md`, Loner's two sentences into its `_AUTHORING`; (b)
Tunnel Goons imports `CHANGE_WORLD` from `engines.core`; (c) `close_segment` builds the
`Exchange` and `Engine.record(state, exchange)` appends it. Leave `master_sections` and the
dispatch: twenty readable lines in the engine's own file is what "self-contained under
`engines/<id>/`" means.

Goldens: none for (b) and (c); worldsmith prompt goldens for (a).

### P6. Delete the guards that duplicate a gate already in code

Round 1: 3/6. Round 2: sound with fixes; the bolder "derive `told` centrally" rests on a false
count (`narrate=` has one call site, `tunnelgoons/tools.py:180`). About −55 lines, −2
concepts, plus M-style: eight `PLAYER_DEAD` guards.

`entity_fact` computes `told` from `known` at all 41 sites and every `reveal` precedes it; all
fourteen hand-built `Fact(...)` sites carry no `entity_id`. So the `apply_to_draft` check "a
told fact names an entity the player has not met" is unreachable in shipped code, and
`Engine.known` (two implementations) exists for it. `apply_scene` re-runs `scene_refusal` on
the same object in the same coroutine as `write_next` (only Loner's `close_conflicts` runs
between, and it refills luck). Eight `if not player.alive: raise ValueError(PLAYER_DEAD)` sites
are dead too: `Turn.call` refuses every tool once `engine.over()` (`run.py:84`) and
`consume_answer` refuses first.

Deleted: the loop in `apply_to_draft`, `Known`, `Engine.known` and both implementations, the
second bar in `apply_scene` (not `merged_cast`, which is the write), the eight guards and the
constant.

Lost: the runtime net for a future engine bug. Track G adds about fifteen `entity_fact` sites
(`actor_id`, `take_lead`) whose reveal-before-tell order the gate is the only check for.
Six tests call `apply_scene` directly for the refusal and one pins "refused before the first
write" (`loner3e/test_world.py:261`, `breathless/test_worldsmith.py:30`,
`twentyfourxx/test_worldsmith.py:90, 200`); they move up to `write_next`, or the failure
surfaces at `committed()` as a pydantic error with the state still safe.

Decision: taken, now. Track G re-checks its new `entity_fact` sites in its own tests.

## Tier 3 — split, corrected

### P8. The payload is the world (half of it)

Round 1: 2/6. Round 2: keep the wrapper deletion, drop the empty-class replacement. About −60
lines. Half a day.

`SceneState`/`SceneScenario` and `TunnelGoonsState`/`TunnelGoonsScenario` wrap one field each
(eight lines) and cost fifty `.payload.world` hops; the state wrapper exists for Loner's `twist`
alone, and G.2 wants a 24XX world subclass for the ship anyway. Delete the four wrappers;
`twist` moves onto a `LonerWorld` subclass; `new_state` is already `new_world(canon,
player_X(character))` in all three engines, so no new hook. The twelve empty
`XGame`/`XScenarioFile`/`XCharacterFile` classes stay: pyright rejects `isinstance` on a
parametrised generic, and 24XX and Breathless share `Scenario[SceneScenario[Person]]`, so the
class is the only tag.

Goldens: eight `scenarios/*/world.json`, twelve fixtures, seven generics typed on `SceneState`
(`check_game`, `way_open`, `player_over`, `narrator_view`, `player_view`, `install_scene`,
`build_scenario`).

### P9. Poll instead of callbacks; one phase instead of three flags

Round 1: 2/6 (+1 missed proposal folded in). About −60 lines. Half a day. After P4.

`on_step`, `on_fact` and `on_commit` thread through `runtime.py`, `run.py` and `game.py`;
`_announce` already writes `session.step`, and the page runs a one-second timer. Poll
`(session.step, len(turn.facts), len(history))` against a stored triple; `live_prompt` is
`session.turn.prompt`; the ticker restarts on a step edge. `GameService.busy`, `step` and
`turn` encode one state machine three ways (`extend` sets `busy` without `step`; `play` clears
`turn` before commit): one `phase: TurnStep | None`, `busy` is `phase is not None`.

Deleted: the three callback parameters through `play`/`open`/`extend`, `Turn.on_fact` (turn stops
importing a UI callable), `GameView.live_prompt/live_facts/step_started/ticker`, `_announce`,
`busy`, the three-way clears in four `finally` blocks.

Lost: sub-second card arrival. `test_golden_turn.py:34` captures untold facts through
`on_fact` and `Exchange.facts` is `cards()` only, so the fixture needs a new source; "the page is
told to refresh before the worldsmith is asked" becomes "the save is on disk when the worldsmith
is spawned".

### P7, P10 and P11: dropped

P10 (delete the settings page): the maintainer keeps the page; the knobs it edits are read at
one site each and are not concepts, so nothing of P10 survives except `busy_refusal` staying
what it is, the guard on the shared MCP surface. P7 (launcher reads headers) needs a
denormalised title on core `Game` written at every commit, which is core learning a world fact, and it strands a player behind an unopenable save with no
delete path (restart lives on the game page). Under P1 the choice is a ten-minute edit: drop
`SaveOption.where` from the card, or leave the restore (fewer than ten saves per render). P11's
merges are churn or broken: unifying the slug grammars hides every existing save
(`scenario--character` is refused by `Slug`; `FileStore.slugs()` would list none); merging
`Speaker` into `Subject` stores `brief` per line in every save and, with `alive`, changes which
NPCs may speak in three engines; `Fact.kind` is written at 55 sites and asserted in about 45
test lines; `_Worldsmith` reorders positionals, which a `partial` cannot, and `authored()` is
the bar loop, not glue. `art_prompt` moved into P1.

## Tier M — missed in round 1, found in round 2

Ranked by concepts removed per day. None has a vote count; each was found by one adversarial
reviewer and checked by the lead.

### M1. `SceneRun.hidden` is derived from `known`

About −30 lines, −2 concepts (a second store, and the invariant between the stores). Half a
day.

`check_named` (`scenes/world.py:538`) enforces hidden ⟹ `known=False` and present ⟹
`known=True`, so `hidden` is exactly "listed here and not known". One `here: list[EntityId]` on
`SceneRun` and `SceneCanon`; `present` and `hidden` become filters over `cast[x].known`. The
draft keeps `present`/`hidden` as the worldsmith's vocabulary; install marks `present` known.
Tunnel Goons already works this way (`Npc.known` + `at(place)`).

Deleted: two fields, the two consistency arms of `check_named`, `reveal_hidden`'s list move,
`enter`'s "hidden here; reveal them instead" branch, the present/hidden overlap check in
`_consistent`.

### M2. One run status; no spent note

About −30 lines, −3 concepts. Two hours.

`SceneRun.settled`, `.pursuit` and `.spent` (`pursuit` implies `settled`), two facts
(`SCENE_SETTLED`/`SCENE_LEFT`), three branches in `scene_rows`, `SPENT_NOTE`,
`SCENE_TURN_CAP` and the `someone_dead` keyword threaded through `record` are three heuristics
nudging the master toward `next_scene`; the master reads "(dead)" in HERE, the exchange count in
the history, and has the tool. `left: str | None` (`None` open, `""` settled here, text when
left for elsewhere) replaces `settled`/`pursuit`; the spent note is deleted, not moved to a row.
Loner's `run.spent = "the conflict … is settled"` (`loner3e/tools.py:400`) becomes nothing.

Lost: an unmeasured nudge; `test_tool_surface.py:323` guards a defect the deletion also
removes.

### M3. The write failure is a card, not a flag

About −15 lines, −1 concept. One hour.

`GameService.write_failure` is read only by truthiness (`ui/panels.py:35`, `ui/game.py:431`),
its text goes to the log, and it is lost on reload. `_grow` files a told fact "The way on could
not be written" on the exchange it would have appended. Deleted: the field, `NO_WAY_ON` in two
places, four assertions.

### M4. Media has no "pending" state

About −25 lines, −1 concept. One hour.

`Illustrator.scene_pending`, `Reader.pending`, `GameService.scene_pending`/`clip_pending`,
`GameView.shown_art`/`shown_clip`, the skeleton branch in `_scene_art` and `poll_media`'s
diffing exist to show a grey box while art generates. `generating` (the claim set) stays; it
prevents paying twice. The three-second poll compares the cached path only. Lost: the loading
skeleton.

### M5. `LaunchTarget.slug` is derived

About −8 lines, −1 concept. One hour.

`slug = f"{scenario_id}--{character_id}"` (`launch.py:62`) and the route
`/game/{slug}/{scenario}/{character}` carry the slug beside its two parts. A property and a
two-segment route; the reconstruction at `launch.py:120` goes. This is also the answer to P11's
slug question: the two grammars encode one real difference, and a comment says so.

### M6. One board rule

About −20 lines. One hour.

Two-or-three offers is enforced in `check_board`, `HubDraft.offers`, Tunnel Goons'
`ReturnDraft.offers`, `_hub_unmet` and the canon's validator. One `Board` annotated type with
the bounds on the world, the canon and the drafts; `check_board` keeps only "no board without a
hub".

### M7. Character, Here and Trail panels built once

About −40 lines. Two hours.

`scenes/views.py` and `tunnelgoons/views.py` each build the three from `rows()`, `here()` and a
run or visit list. `engines/core.py` gains the three builders beside `party_panel`. The only
alternative is Tunnel Goons as a scene engine, which stays refused.

### M8. `Scene` folds into `SceneRun`

About −35 lines, −1 class. Half a day. Only with P2; rule-shaped cost.

Under P2 `Scene` is (place, title, question, situation, secret). `SceneCanon` carries
`opening: Scene` beside `present`/`hidden`, which is a `SceneRun` spelled as three fields;
`check_hub` builds a `SceneRun` to check it and `new_world` rebuilds it. Deleting `Scene` loses
the frozen/mutable split between a scene's text and its run state, which CLAUDE.md's "value
models are frozen" would no longer say in the type.

## Recorded, not recommended

- Packs not a player choice (lead, round 1): sound; user packs under `packs_dir` already work.
- Source text out of saves: drop it from the world only, keep it on the canon; the stored text is
  `given_text`'s combined string and `meta.premise` is overwritten when empty, so it cannot be
  rebuilt from file plus meta. Nothing reads `scenarios/<id>/source.*`.
- Delete `ScenarioMeta.kind`: it is the only world-shape-free place the launcher badge can read;
  keep it.
- Delete character creation: conflicts with G.2's android case; keep.
- Tool-written notes as untold facts: broken. `SPENT_NOTE`, `finished_note`, the text-answer
  note, `defeat_note` and the loot notes steer the next picture, and facts are not carried
  forward (only `cards()` are filed).
- Media scene-art only, one speech voice, one CLI driver, delete `Exchange.decision`: real
  feature losses; the maintainer's word each.
- Tunnel Goons as a scene engine: a room change is a master `move` in seconds; as a scene it
  becomes a worldsmith crossing in minutes.

## Doc fixes (no code)

- CLAUDE.md "a role returns typed proposals only" is true of the narrator and the worldsmith and
  false of the master, whose tools mutate a transactional draft; what protects state is `_apply`
  (candidate copy, rng copy, `committed()` revalidation). Say that.
- P4 reverses "the app resumes its session each turn when the CLI allows it"; edit the line in
  the P4 phase.
- NEXT-SPECS: G.3 re-adds a re-suspension path (P3); decision 2's number stays as a constant
  (P1); `JobDone.raises` gets `raised` on the job record (P2); the `Kill` arm stays per engine
  because of succession (P5).
- `NarratorView.party` and the party arms in 24XX and Breathless are Track G.1, not a gap.

## Where the reviewers disagreed with the seed examples (unchanged from round 1)

- "Context only needs the hidden/revealed split": the split is already the narrator's whole
  input; the fat is the history rendered four ways (P1) and the picture delivered through a tool
  because of resume (P4).
- "Everyone gets the narrator's full history": everyone except the narrator gets the recaps.
- "Compaction when a scene is two scenes away": the recap is written on the crossing, so one
  scene old is free; P1 keeps the previous scene whole because the maintainer asked, capped.
- "Tag each message with its scene": already true structurally; P1 exposes the nesting.

## Suggested order (by concepts removed per day, with dependencies)

1. P3 (half an hour; touches `run.py` where P4 lands next).
2. P4 (one day; deletes the reason P1's window was unsafe and rewrites the prompt P1 then
   edits).
3. P1 with the `art_prompt` fold (one day).
4. P2 with M8 (one day; `test_hub` rewrite).
5. Half-day chores in any order: P6, P8, P9, P5, M1, M2.
6. One-hour chores: M3, M4, M5, M6, M7.
