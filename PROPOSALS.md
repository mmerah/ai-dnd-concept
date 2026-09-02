# PROPOSALS — conceptual simplification (round 1, 2026-09-02)

Six independent reads of the whole of `src/aidm` (the lead and five reviewers, each with a
different emphasis: turn pipeline, seam and world models, information flow, edges, contrarian).
Each built an inventory of every concept (40 to 60 nouns, depending on how they counted) and gave
a verdict per concept. This file keeps only what at least one reviewer proposed as a change, merged
and ranked by how many of the six landed on it. Each entry is written so it can become a spec:
what exists, what replaces it, what is deleted, what is lost, and the one decision it needs.

"Votes" is how many of the six proposed it independently. Line counts are estimates.

## Tier 1 — consensus (five or six of six)

### P1. One history, one renderer, scene by scene

Votes: 6/6. About −150 lines and one setting.

Today the same exchanges are rendered four ways: the master's RECENT PLAY (last
`recent_exchanges`, with a `[at where]` tag), the narrator's WHAT THE PLAYER HAS READ (last N
narrations, no prompts, no place), the worldsmith's SCENES SO FAR (per scene: recap if closed, all
exchanges if open), and Tunnel Goons' return prompt (last three per visit). `Exchange.where` is
excluded from the save and recomputed by the job walk on every read, with a `model_copy` per
exchange, five or six times a turn.

Proposal: the engine's `history()` returns the scenes themselves, each a frozen record with a
title, a recap (empty while open) and its exchanges; exchanges already live inside `SceneRun` and
`Visit`, so the "where" is the nesting, not a field. One function renders it for every role: a
`SCENE: title` heading per scene, the current and the previous scene printed whole
(`> prompt` then narration), every older scene as its recap. The narrator's variant prints
revealed text only and never a recap, because `NextDraft.recap` is specified to "name the secret".
The chat's heading loop and the launcher's "where" both read the last scene's title.

Deleted: `_recent`, `_recent_exchange`, `told_passages`, `scene_history`, `_told`,
`recap_rows`, `_told_tail`, `TAIL_EXCHANGES`, `hub.heading`, `Exchange.where`, both
`exchanges()` stampers, `Settings.recent_exchanges`, `Turn.recent` and the `recent` argument
threaded through `GameService.play`, `Turn.begin` and `render_picture`.

Lost: the master's flat "last 20 across scenes" window becomes "this scene and the last one".
The recap the worldsmith writes on the crossing is the only compaction; that is the maintainer's
seed, and it is already built. Tunnel Goons has no crossing and so no recap: its history is
bounded by the job (`job_visits`) instead.

Decision: none. Goldens regenerate.

### P2. Jobs are stored, not derived from the trail

Votes: 5/6. About −150 lines; `test_hub.py` shrinks by a third.

Today a job is a pattern over the scene list: `Scene.debrief` and `Scene.job` (scenes) or
`Visit.job` and `Visit.debrief` plus `TunnelWorld.job_done` (Tunnel Goons) are read into a
`Stop` adapter, then `job_titles`, `job_start` and `closed_jobs` rebuild the ledger on every
read, and two `check_hub` validators police the placement ("a hub run right after a hub run",
"a debrief with no job before it").

Proposal: `world.jobs: list[Job]` appended at the return install, and `world.open_job: str` set
when the job scene installs and cleared at the return. The ledger is the list. The scene keeps
its title and question only.

Deleted: `Stop`, `job_titles`, `job_start`, `closed_jobs`, `heading`, `Scene.debrief`,
`Scene.job`, `Visit.job`, `Visit.debrief`, `stops()`, the placement arms of both `check_hub`.

Lost: one derived source of truth becomes an append-only list written at one site; a five-line
validator still checks it. Saves go stale, which the design allows.

Decision: none.

## Tier 2 — majority (three or four of six)

### P3. Delete the dead suspension path

Votes: 4/6. About −25 lines. Twenty minutes.

`during_suspension` (five registrations) and `Turn.suspended_at_start` exist so a world change
can land in a turn whose option answer re-suspended. `consume_answer` clears `pending` on every
input, so the flag matters only when an option's own resolution opens a new decision, and no
shipped tool does that (`test_decisions` builds a synthetic chain to reach it). Two reviewers also
fold `Turn.resumed` and the "THE PLAYER'S DECISION, ALREADY RESOLVED" section into the notes
channel, which already carries the text-answer case.

Lost: nothing shipping. Track G's succession chain can re-add it when it needs it.

Decision: none.

### P4. Cold spawns: no session resume, no `start_turn`

Votes: 4/6 (two keep). About −250 lines. Reverses a CLAUDE.md decision.

Today `Conversations` keeps a `.sessions` sidecar with a fingerprint per role, retries cold when a
resumed role fails, and is forgotten on every failure path. Because the master is resumed, its
spawn prompt holds no world, and it must call `start_turn` over MCP to get the picture; `scene`
exists to recover after mid-turn compaction; `started`, `START_FIRST` and `ALREADY_OPEN` police
the order. Codex already runs the master cold (a resumed thread refuses MCP), and the worldsmith
is always cold. Under Claude resume the master's real context grows by one whole picture per
turn, which is the compaction problem the `scene` tool exists to survive. The narrator gets its
history twice, once by resume and once as WHAT THE PLAYER HAS READ.

Proposal: every spawn is cold; the picture is the spawn prompt. `answered` keeps its own
within-retry session. P1's "no limit" is only safe once this lands.

Deleted: `app/sessions.py`, `FileStore.sessions_path`, `cold_retry`, `nothing_landed`, four
`forget` calls, `TurnTool`, `TURN_TOOLS`, `start_turn`, `scene`, `Turn.started`, the two
constants, the `render_master`/`render_picture` split, the Codex master special case. One class
of bug goes with it: a role that remembers a turn that was thrown away.

Lost: prompt-cache hits on the rules, and the master's chain of reasoning across turns. Cost per
turn is unmeasured in both directions.

Decision: the maintainer's. Measure five turns cold against five resumed before committing.

### P5. Fold the three scene engines' duplicates into `SceneEngine`

Votes: 4/6. About −250 lines, two prompt files. No behaviour change; tool goldens unchanged.

`master_sections` is written three times and differs by one sheet row. `breathless/worldsmith.md`
and `twentyfourxx/worldsmith.md` are byte-identical; Loner adds two sentences; each engine also
carries an `_AUTHORING` string. The `Reveal | Enter | Leave | Kill` dispatch and the
`change_world`/`next_scene` registration are copied three times. `CHANGE_WORLD` is redefined
verbatim in Tunnel Goons. Both `record` implementations build the same `Exchange`.

Proposal: `SceneEngine.master_sections` with a `sheet_rows()` hook beside the existing
`panels()` hook; one `scenes/worldsmith.md` plus an engine `authoring` attribute;
`SceneWorld.apply_shared(change)` for the four common arms with the engine's `apply_change`
falling through to its own; `SceneEngine.master_tools` building the two shared tools around the
engine's `world_change` union and `rules_tools()`; the platform builds the `Exchange` in
`close_segment` and the engine appends it. This is deduplication, not the arm flattening that
NEXT-SPECS refused.

Decision: none.

### P6. Delete the guards that duplicate a gate already in code

Votes: 3/6. About −40 lines.

`entity_fact` already sets `told = narrate and entity.known`; the `apply_to_draft` check "a told
fact names an entity the player has not met" and the `Engine.known` abstract method it needs (three
implementations) can fire only on a hand-built `Fact`, and every hand-built one has no
`entity_id`. `apply_scene` re-runs `scene_refusal` and `merged_cast` on the same draft
`write_next` just ran them on, in the same coroutine.

Lost: a guard against a future engine bug. `test_integrity_boundaries` loses two cases.

Decision: none.

### P7. The launcher reads headers, not saves

Votes: 3/6. Falls out of P1 and P2.

`load_catalog` fully restores and validates every save to print one "where" string on a card.
With the scene title on the last scene record (P1), `SaveHeader` plus one field serves the home
page. Stale saves fail on open instead of being skipped on the home page; the design already says
a stale save is invalid.

## Tier 3 — split (two of six); worth a spec if the maintainer agrees

### P8. The payload is the world

Votes: 2/6. About −60 lines and six wrapper classes.

`SceneState`/`SceneScenario` and `TunnelGoonsState`/`TunnelGoonsScenario` wrap one field each, so
every read is `state.payload.world`; the state wrapper exists for Loner's `twist` alone. Twelve
empty `XGame`/`XScenarioFile`/`XCharacterFile` classes exist so `isinstance` narrows in
`new_game` and `preview_character`, which `begin_game`'s engine-id check already guards.

Proposal: the payload is the world; Loner's `twist` lives on its world subclass; a
`player_of(character)` hook on `SceneEngine` makes `preview_character` and `new_state` shared;
parametrised aliases replace the empty classes. Risk: pyright narrowing on parametrised pydantic
generics; try one engine first.

### P9. Poll instead of callbacks in the game page

Votes: 2/6. About −60 lines.

`on_step`, `on_fact` and `on_commit` thread through `runtime.py`, `run.py` and `game.py` to do
what the page's one-second timer already can by reading `session.step`, `session.turn.facts` and
`len(history)`. `GameView` drops `live_prompt`, `live_facts`, `step_started` and `ticker`;
`Turn` stops knowing about the UI. Lost: sub-second card arrival.

### P10. Fewer settings knobs

Votes: 2/6 on the knobs; 1/6 on deleting the page.

`recent_exchanges` (gone with P1), `scene_ratio`, `icon_ratio`, `max_references`,
`sample_rate`, `voices`, `source_max_chars`, per-role `effort` and `timeout`, `server_port`
(hard-coded in two other files anyway) and the four directories become constants; `Providers`
collapses to one `ProviderConfig`. The reflective settings page costs nothing per knob and stays
unless the maintainer wants `.env` edited by hand only, in which case `ui/settings.py`,
`save_settings`, `reload_settings`, `play_refusal` and `busy_refusal` go too (about −300 lines).

### P11. Small merges

Votes: 2/6 each.

- `Fact.kind` is read on one line (Loner's `conflict_lost` check); delete the field.
- `Speaker` merges into `Subject` (add `alive`); `NarratorView.speakers` and `speaker_of` go.
- `NarratorView.art_prompt` is `title + situation + subjects`; `media.py` builds it.
- `_Worldsmith`, `WorldsmithAnswer` and `authored()` collapse to one `partial` passed as the
  answer function.
- Two slug grammars (`Slug` and `_SAVE_SLUG_PATTERN`) become one.

## Tier 4 — single voice; recorded, not recommended yet

- **Packs stop being a player choice** (lead). Three engines ship one table set each (Loner two).
  The creation step, the scenario multiselect, `Game.packs`, `Scenario.packs`, `check_game`'s
  pack rules, `packs_dir` and `pack_options` serve a pack authoring feature that is still IDEAS 13.
  Four reviewers keep packs.
- **Source text is not stored in every save** (lead). `SceneCanon`, `SceneWorld`, `MapCanon`
  and `TunnelWorld` each carry the whole source document, up to 120k characters, into every
  save; the file is already copied to `scenarios/<id>/source.*`. Read it at prompt time. One
  reviewer proposed the opposite: delete the file copy, which nothing reads.
- **`ScenarioMeta.kind` duplicates `hub is not None`** (lead); `check_kind` exists to keep them
  in sync. Delete `kind`.
- **Character creation flow deleted** (edges reviewer). About 350 lines of dynamic form engine
  serve one shipped character; characters become hand-written JSON. Two reviewers keep it as an
  SRD-faithful feature.
- **Media: scene art only, no icon generation; speech: one voice; one CLI driver** (edges
  reviewer). Each is a real feature loss and needs the maintainer's word.
- **`Exchange.decision` deleted** (edges reviewer). Used once, to print "Paused: …" on old
  exchanges.
- **Tool-written notes become untold facts** (pipeline reviewer). They reach the master through
  the tool answer already; `Game.notes` would mean only "for the next picture".
- **The spent note becomes a master row** (seam reviewer). Then `record` returns nothing.
- **Tunnel Goons as a scene engine** (contrarian). A room is a scene whose place is the art key
  and whose ways are `PanelRow.intent` rows, as offers are. Tunnel Goons alone forces
  `crossing: str | None`, `ready()`, `GameService.extend`, the silent branch in `_grow`, the
  untold `region_added` fact, its own `check_hub`, `job_open`, `ReturnDraft`, `_render_return`
  and `_told_tail`. Highest value, highest risk; a blank-page choice, not a refactor.

## Doc fixes (no code)

- CLAUDE.md says "a role returns typed proposals only". It is true of the narrator and the
  worldsmith and false of the master, whose tools mutate a transactional draft; what protects
  state is `_apply` (candidate copy, rng copy, `committed()` revalidation). Say that instead.
- If P4 lands, CLAUDE.md's "the app resumes its session each turn when the CLI allows it" is
  reversed.
- `NarratorView.party` and the `JoinParty`/`LeaveParty` registration in 24XX and Breathless are
  Track G.1, not a gap; one reviewer read the platform share as half-built. Note it in NEXT-SPECS.

## Where the six disagreed with the seed examples

- "Context only needs the hidden/revealed split": the split is already the narrator's whole
  input (`NarratorView` has no field for a secret; `Fact.told` gates evidence). What is fat is
  the history rendered four ways (P1) and the picture delivered through a tool because of resume
  (P4), not the sections.
- "Everyone gets the narrator's full history": everyone except the narrator gets the recaps; the
  narrator gets revealed text only, because a recap may name the secret.
- "Compaction when a scene is two scenes away": the recap is written on the crossing, so
  compaction at one scene old is free today. Showing the previous scene raw as well costs tokens
  and buys little; P1 keeps it because the maintainer asked, and it is one integer to change.
- "Tag each message with its scene": already true structurally (exchanges live inside the
  scene); P1 exposes the nesting instead of stamping a field.

## Suggested order

1. P3 (twenty minutes, warms up the tests).
2. P1 with P7 (one day; the seed, done).
3. P2 (one day; `test_hub` rewrite).
4. P5 and P6 (one day together; pure deletion).
5. P4 after a measurement (two days including it), then P8 to P11 as small follow-ups.
