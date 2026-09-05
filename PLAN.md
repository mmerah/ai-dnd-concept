# PLAN — adventure structure belongs to scenarios and engines

Two phases, in order. **Phase 1 deletes**: the shared campaign layer (hub, board, jobs, chapters,
the one-shot/campaign kind), the commission machinery, the editorial validity rules and the
compulsory arc rewrite go; a `scope` field arrives. **Phase 2 adds**: the generation handoff (a
game-master complication that ends the turn and is written after it), 24XX's own job lifecycle,
and the documentation. Self-standing: an implementer needs this file, `CLAUDE.md` and the code.
`REFOCUS-SPECS.md` (2026-09-05, `git show 46b460c:REFOCUS-SPECS.md`) is folded here whole and
deleted.

What stays, everywhere: transactional drafts and the commit gate; strict boundary validation;
code-owned dice and rules; the narrator's view holding revealed facts only; persistence; the three
roles; all four engines and both world families; scenarios and characters authored, stored and
selected on their own. What is not built: a universal `finish_adventure` tool, a completed-save
state, save versioning or migration, a plot-management subsystem, a commission queue under a new
name.

Saves have no version field. Phase 1 changes every stored shape (`ScenarioMeta`, `Game`, both
payloads), so every save from before it is stale: the launcher skips it with its warning and
`restore` refuses it. Nothing reinterprets or deletes an old save. Phase 2 changes `SceneRun` and
`TwentyfourxxWorld` by defaulted fields only, so a Phase 1 save still loads.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action on the files it names. Finish it before the next.
2. **Change a shape and its tests in the same step.** One test per new behaviour; no test of prose
   or wiring. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them at the end of each phase:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line against the phase's "Fixtures" list; anything else is a bug.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file. `src` is 9,367 lines at the start of Phase 1.
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs far past its target, stop and say so.** Never pad.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** A phase's parts may leave the tree red between them; the full check
   is green before the commit. Never leave two versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **The standing limits hold.** At most fifteen engine tools per engine, counted as tools plus
   `change_world` arms, the two shared party arms not counted, twenty for an engine whose SRD
   plays a crew (Phase 1 step 15 rewrites this rule in `CLAUDE.md` without `commission`; Phase 2
   takes 24XX to sixteen under the crew allowance). Every `engines/<id>/` stays under 2,000 lines;
   imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond the `Game[P]` bound;
   every `__init__.py` empty; tests never start a process (`ScriptedSpawner`); `Refusal` stays the
   one message-bearing exception; a bad model answer is re-prompted once, then raises.
10. **Delete, do not preserve.** No hidden routing convention survives (`Go home.`, `Report in.`,
    `I take the job "…".`); no compatibility path reads an old save or scenario; no constant,
    helper or prompt line stays for a caller that is gone. When a step says "delete", grep for
    the symbol across `src/` and `tests/` and remove every use.

---

## Phase 1 — the campaign layer and the commissions go; scope arrives

Target: `src` from 9,367 to between 7,900 and 8,200 lines.

Suggested split for the orchestrator: **A** (steps 1–6: `core/`, `engines/base.py`,
`engines/seam.py`, `turn/`, `app/`, `ui/`, `tests/core/` except `test_scenes.py` and
`test_rooms.py`, `tests/ui/`), then **B** (steps 7–11: `engines/scenes/`, the three scene
engines, `tests/core/test_scenes.py`, `tests/support/`, `tests/{loner3e,breathless,twentyfourxx}/`)
and **C** (steps 12–13: `engines/rooms/`, `engines/tunnelgoons/`, `tests/core/test_rooms.py`,
`tests/tunnelgoons/`) in parallel — C deletes its own imports of `the_campaign` and
`aidm.engines.hub` and adds `scope=` to its own `ScenarioMeta(...)` literals, B owns
`tests/support/table.py` — then **D** (steps 14–17: scenarios, documentation, fixtures) alone.
The tree is red after A and green after D.

### Steps

1. **`core/model.py` — the scenario has a scope, not a kind.** Delete `ScenarioKind`. In
   `ScenarioMeta` delete `kind`; add `scope: str = Field(min_length=1)` between `premise` and
   `art_style`, with the description "How far this adventure reaches, how its consequences
   develop, and whether it tends toward an ending or toward continuing concerns; guidance, not a
   rule." Delete `Game.commissions`, `Game.wanted`, `Game.on_order`, `Game.withdraw`, and the
   `Commission` import. `Game.notes`, `Game.pending`, `draft`, `commit` stay. Every
   `ScenarioMeta(...)` literal that survives in `tests/` gains `scope="..."` (a sentence; the
   value is never asserted): `tests/core/{test_game_service,test_master_tools,test_seam}.py`
   and `tests/ui/test_launcher.py` here; `tests/support/*.py`, `tests/core/test_rooms.py` and
   the engines' test folders in steps 11 and 13.

2. **`core/play.py` — history is a flat sequence of scenes.** Delete `SceneRecord.job`,
   `ChapterRecord`, `Commission` and the `HistoryRecord` alias; every former `HistoryRecord` in
   the codebase becomes `SceneRecord`. `Exchange`, `SceneRecord` (title, focus, recap,
   exchanges), `PendingDecision` and the rest stay.

3. **`core/views.py` — no chapters, no whole-job render.** Delete `render_whole`,
   `_whole_scene`, `_whole_exchange` and the `DICE` import. `render_history(records:
   Sequence[SceneRecord])`: its `_block` loses the `ChapterRecord` branch; the last two scenes
   whole, an older scene by its recap when it has one, else its last three exchanges. `SCENE_EXCHANGES`,
   `WHOLE_SCENES`, `TAIL_EXCHANGES`, `told_narration`, both views and the panel types stay.

4. **`engines/base.py` — the shared world primitives move here; `engines/hub.py` is deleted.**
   Move into `base.py`, after `Person`: `class World[P: Person](Mutable)` with `player: P`,
   `source: str = ""`, abstract `records() -> tuple[SceneRecord, ...]` and `record(exchange)`,
   and `exchanges()`; delete `campaign`, `at_hub` and `scenes()`. Move `named_unmet(text,
   entities)` into `base.py` as a public function, and its one test
   (`tests/core/test_hub.py:185-193`) into `tests/core/test_engines_base.py`. Delete everything
   else in `hub.py` (`Offer`,
   `Board`, `Job`, `Campaign`, `walk_start`, `job_title`, `check_kind`, `place_unmet`,
   `title_unmet`, `question_heading`, every constant and every prompt string) and the file.

5. **`engines/seam.py` — the engine has no commission API and no campaign hooks.** Delete
   `COMMISSION`, `COMMISSION_BRIEF`, `WORLDSMITH_WAIT`, `CommissionArgs`, `Engine.commission`,
   `Engine.reopening`, `Engine.ask_worldsmith`, the abstract `commission_tool` and `fulfil`.
   `__init__` builds `tools` from `master_tools()` alone. `scenes(state)` returns
   `self.world(state).records()`. `World` is imported from `engines.base`. `crossing`,
   `page_word`, `ready`, `advance`, `compose`, `author`, `close`, `commit`, `begin` and the rest
   stay as they are.

6. **`turn/`, `app/`, `ui/` — no commission loop, no campaign routing, scope in the picture.**
   - `turn/run.py`: delete `COMMISSIONS_PER_TURN`, `Turn.commissioned`, the `wanted()` checks in
     `call` and `apply`, and the `COMMISSION`/`WORLDSMITH_WAIT` imports. `call` keeps the
     game-over check, the pending-decision answer, and the one gate.
   - `turn/context.py`: `render_master` adds the section `("THE SCOPE OF PLAY",
     state.scenario.scope)` directly after `SCENARIO`. `render_narrator` is unchanged: the
     narrator never reads the scope.
   - `turn/prompts/master.md`: delete the "## Ask for more" section.
   - `app/runtime.py`: delete `_run_master`, `_fulfil`, `_withdrawing` and the `Commission`
     import; `play` calls `self._act(turn)` where it called `_run_master`. `_grow`, `extend`,
     `_narrate`, `open`, `restart` stay. `new_scenario` is unchanged (`meta` now carries scope).
   - `app/launch.py`: delete `CatalogEntry.kind`, `SaveOption.kind` and the `ScenarioKind`
     import.
   - `ui/create.py`: delete `kind_toggle` and the campaign label. Add `self.scope: ui.textarea`
     after the premise, label "Scope", placeholder "How far does this go, and does it tend toward
     an ending?"; it is required (`write` refuses without it, alongside title and premise or
     document) and lands in `ScenarioMeta(scope=...)`.
   - `ui/app.py`: delete both `campaign` badges.
   - Tests: delete `tests/core/test_hub.py`; in `tests/core/test_turn.py`,
     `test_game_service.py`, `test_master_tools.py`, `test_views.py`, `test_seam.py`,
     `test_decisions.py` and `tests/ui/test_launcher.py` delete every test of commissions,
     chapters, kinds and the hub. New tests, one each: `render_master` prints THE SCOPE OF PLAY;
     `render_history` binds nothing (a run of scenes renders as scenes only).

7. **`engines/scenes/drafts.py` — one scene draft, no hub drafts, no editorial minimums.**
   Delete `HubDraft`, `JobDraft`, `ReturnDraft`, `CastDraft`, `MIN_SITUATION`, `MIN_ARC` and the
   `hub` imports. `SceneDraft`: `question: str = Field(min_length=1, ...)`, `situation: str =
   Field(min_length=1, ...)`, `arc: str = Field(default="", description="The setup beyond this
   scene, for the game master and for you, never the player: pressures, motives, secrets, what
   may come. Revise it only when what happened warrants it; empty keeps it as it stands.")`.
   `NextDraft` keeps only `recap: str = Field(min_length=1, ...)` (the `RECAP` description as it
   is, without `MIN_RECAP`); its `arc` override goes. There is no way to clear an arc: to retire
   a setup, the worldsmith writes the one that now holds.

8. **`engines/scenes/world.py` — the world is runs, cast, party, arc.** Delete `SceneRun.job`,
   `SceneCanon.campaign`, `SceneWorld.campaign` (now absent from `World`), `at_hub`, `walked`,
   `job_runs`, the `hub` imports and every campaign check in `_playable_canon` and
   `_consistent`. `SceneRun.question` and `SceneRun.situation` drop to `min_length=1`: the run
   is built raw by `run_of`, so a minimum the draft no longer has would raise a
   `ValidationError`, not a refusal. `settle(pursuit: str)`: refuses an already-settled run, sets `run.left`,
   returns `[SCENE_LEFT if pursuit else SCENE_SETTLED]`. `apply_scene(draft: SceneDraft[C])`:
   merges the cast, resolves present and hidden, marks present known, sets `run.recap` for a
   `NextDraft`, sets `self.arc = draft.arc or self.arc`, appends `run_of(draft, [*party,
   *present, *hidden])`. `scene_rows`: the question row, then for a settled run the "Go on" row
   (with `intent=left`) or the "Way on" row; nothing else. `run_of` loses `job`. Everything
   about the party, `enter`, `leave`, `kill`, `reveal_hidden`, `merged_cast`, `last_seen`,
   `cast_lines` stays.

9. **`engines/scenes/worldsmith.py` and `worldsmith.md` — integrity, not taste.** Delete
   `COMMISSION_ASK`, `cast_refusal`, `_hub_unmet`, and the `asked`/`reopening` parameters of
   `scene_refusal` and `scene_unmet`. `scene_unmet` keeps: the player or party listed as present
   or hidden; the player in `cast`; misfiled entries; unresolvable ids; present-and-hidden
   overlap; a met entry listed hidden; a new entry written dead (`unwritten`); a hidden
   entity named in `situation`. Delete from `_cast_unmet` the "at least one cast member besides
   the player", the "at least one existing cast member brought back" and the `needs_return`
   parameter; delete the "an `arc`" requirement. `worldsmith_prompt` gains `scope: str` and
   prints `("THE SCOPE OF PLAY", scope)` directly after SOURCE MATERIAL; it loses `hub` and
   `asked`. Rewrite `worldsmith.md`'s "Every scene must have all of these" list as advice: a
   scene usually has someone or something to meet, usually brings back one established thing,
   always has one `question` the player can settle here, and a source detail where a source
   exists; a solitary scene, a new cast, a quiet situation or a short setup is not wrong. Delete
   the sentences on THE GAME MASTER ASKED FOR, `summary`, `debrief`, and jobs ("A job takes
   several scenes"); say `arc` is the setup beyond this scene, revised only when play warrants,
   and that what happened in SCENES SO FAR outranks it: a possibility play resolved or
   contradicted is spent, never restored.

10. **`engines/scenes/engine.py` and `tools.py` — one opening, one next scene.** Delete
    `hub_phrase`, `finished_note`, `commission_tool`, `render_commission`, `fulfil`,
    `install_cast`, `hub_sections`, `opening_draft`, the `reopening` parameters, the `ReturnDraft`
    / `JobDraft` / `HubDraft` branches in `write_next` and `install`, the `check_kind` call in
    `validate`, and every `hub` import. `master_sections` prints `("THE QUESTION THIS SCENE
    SETTLES", scene.question)` and no campaign tail. `player_view` panels: character, the engine's
    own, "This scene", party, here, `trail_panel(run.title for run in world.runs)`. `page_word`
    is `intent == world.run.left`. `ready` is `world.run.left is not None`. `render_opening(source,
    guidance, scope)` uses `SceneDraft[self.cast]` and the one opening intent (the former
    `ONE_SHOT_OPENING`, moved here as `OPENING`, with its last sentence reading "The opening also
    writes `arc`, the setup beyond this scene for the game master and the worldsmith, never the
    player: pressures, motives, secrets, what may come; a few lines, or none."). `render_next`
    passes `scope=draft.scenario.scope`; when `world.arc` is set and the answer is a `NextDraft`
    it appends "The arc as last written: {arc}. Revise `arc` only where what happened warrants it;
    leave it empty to keep it." `write_next` always answers `NextDraft[self.cast]`. `install`
    returns the one `scene_opened` fact (card "New scene: {title}\nAt stake: {question}").
    `guidance(picks)` loses `campaign`. `tools.py`: delete `SceneCommission` and
    `NextScene.job_done`; `NEXT_SCENE` and `NextScene.pursuit` stay.

11. **The three scene engines and their support.** `loner3e/engine.py`: delete `GROWTH_NOTE`,
    `hub_phrase`, `finished_note`; `guidance(picks)`. `breathless/engine.py`: delete `hub_phrase`;
    `guidance(picks)`. `twentyfourxx/engine.py`: delete `JOB_DONE_NOTE`, `hub_phrase`,
    `finished_note`; `guidance(picks)` returns `AUTHORING`; `twentyfourxx/worldsmith.py` loses
    `BOARD_GUIDANCE`. In each of the three `rules.md` delete the "## Campaigns" section; in
    `loner3e/rules.md` delete the sentence "In a campaign, NOTES FROM THE RULES names when a job's
    end counts as the adventure's."; in `twentyfourxx/rules.md` leave "## Job done" for Phase 2.
    Add to each of the three, under "## Let the player choose where the story goes": "THE ARC is
    the worldsmith's setup beyond this scene: what may come, never what must. What happened
    outranks it, and the player's choices are theirs; narrate none of it." Tests: delete
    `tests/support/scenes.py`; in `tests/support/{twentyfourxx,loner,breathless}.py` delete the
    hub fixtures; in `tests/support/table.py` delete `the_campaign` and the `kind` parameter of
    `scenario_for` and `game`; in `tests/core/test_scenes.py` and the three engines' test folders
    delete every test of the hub, jobs, boards, returns, commissions, arc rewrites and the
    editorial bars; every surviving `ScenarioMeta(...)` literal in these files gains `scope=`.
    New tests, one each: a scene naming no one but the player installs; a
    `NextDraft` with an empty `arc` keeps the world's arc; the worldsmith prompt prints THE SCOPE
    OF PLAY at the opening and in play.

12. **`engines/rooms/` — the map, its extension, nothing else.** `world.py`: delete
    `Visit.job`, `Visit.recap`, `RoomCanon.campaign`, `at_hub`, `walked_job`, `walked`,
    `job_visits`, `walked_places`, `apply_return`, `apply_extension`, `Dungeon.has_shortcut`
    (its one caller is the shortcut bar deleted below), the `hub` imports and the
    campaign checks in `_startable` and `_playable`; `move` appends `Visit(place=destination.id)`;
    `records()` builds `SceneRecord(title, focus, exchanges)`. `drafts.py`: delete
    `MapDraft.board`, `NpcDraft`, `ItemDraft`, `ReturnDraft` and the `hub` imports.
    `worldsmith.py`: delete `MIN_PLACES`, `MIN_EXTENSION_PLACES`, `TAVERN_ASK`, `COMMISSION_ASK`,
    `JOB_BRIEF`, `hub_refusal`, `job_refusal`, `return_refusal`, `npc_refusal`, `item_refusal`,
    `_hub_unmet`, `_recaps_unmet`, `_debrief_unmet`, `_board_unmet`, `_asked_unmet`,
    `_has_hidden_thing`, and from `_map_unmet` and `_extension_unmet` the place-count, known-way,
    unknown-way, locked-way, hidden-thing, shortcut and "ways connecting" requirements.
    `map_refusal` keeps `_start_unmet` (start in places, start known, every place reachable);
    `extension_refusal(draft, world)` keeps at least one place, start in places, start hidden,
    every place reachable, and `_overlap_unmet`. `worldsmith_prompt` gains `scope` (printed
    after SOURCE MATERIAL) and loses `hub` and `asked`. `worldsmith.md`: the shortcut, locked way
    and hidden thing become advice ("a map plays best with…"); delete the tavern, job and
    THE GAME MASTER ASKED FOR paragraphs. `tools.py`: delete `RoomCommission`. `engine.py`: delete
    `REPORT_IN`, `REPORT_ROW`, `commission_tool`, `render_commission`, `hub_sections`, `fulfil`,
    `install_commission`, the `check_kind` call, the `reopening` parameters and every `hub`
    import; `render_map(source, scope)` asks `MAP_ASK`; `render_extension(world, intent, scope)`;
    `write_extension` answers `MapDraft` under `extension_refusal`; `install_extension` attaches
    the region hidden (`world.attach(extension, extension.start, known=False)`) and returns the
    untold `region_added` fact; `ready` is `world.frontier() == 0`; `player_view` panels:
    character, here, carrying, ways out, `trail_panel(... for v in world.visits)`;
    `master_sections` has no campaign tail.

13. **`engines/tunnelgoons/engine.py` and its tests.** `level_up` no longer touches a job; its
    description reads "Raise one ability and either Health or Inventory Score by 1, once, at the
    adventure's end." `rules.md`: delete "## Campaigns" and the sentence "In a campaign, call it
    when the job's dungeon is done; the tavern then closes the job as finished."; "## The map's
    end" loses "and at the tavern it offers work". Tests: in `tests/support/tunnelgoons.py`,
    `tests/core/test_rooms.py` and `tests/tunnelgoons/` delete every test of the tavern, jobs,
    returns, recaps, commissions and the deleted map requirements; delete their imports of
    `the_campaign` and `aidm.engines.hub`; every surviving `ScenarioMeta(...)` literal gains
    `scope=`. New tests, one each: a one-place map with no ways is a valid opening; an extension
    of one hidden place installs.

14. **Scenarios.** Delete `scenarios/amber-tap/`, `scenarios/buried-bell/`,
    `scenarios/salt-lantern/` and `scenarios/waystation/`: each opens on employment at a home
    base, and the one-place tavern is no room-crawl opening. (The alternative, rewriting three
    hub openings by hand with a question that settles and the board folded into the fiction,
    is the maintainer's call; this plan deletes.) In the four that remain, delete `meta.kind`
    and add `meta.scope`, verbatim:
    - `whispering-vault`: "One night in the abbey, from the study to the vault and out again. Reaching what is sealed below, or learning why it was sealed, brings the scenario toward an ending; what Kael carries out can follow him into other stories."
    - `drowned-road`: "One crossing, while the tide allows it. Reaching Saint Ferrant, or failing to, ends the scenario; nothing owes a sequel."
    - `silent-relay`: "The relay is one job among many: bring the beacon up, or learn why it went dark, and the work is done. Let what Kael finds at QV-9 create the next job, a debt, or an enemy; no final objective is prescribed."
    - `buried-keep`: "One descent into the keep. The dark below has an end, and reaching it or turning back is the adventure's; a way out that opens onto more of the world is the worldsmith's to write."

15. **`CLAUDE.md`.** In "Design decisions", replace the tool-cap sentence with "with at most
    fifteen engine tools, counted as tools plus `change_world` arms, the two shared party arms not
    counted; twenty in all for an engine whose SRD plays a crew, named in its
    `docs/<ENGINE>.md`." and delete "all four share the hub in `engines/hub.py`"; add "Every
    world subclasses `World` in `engines/base.py`." Replace "the worldsmith's scene titles,
    offers and debrief reach the player on cards and panels" with "the worldsmith's scene titles
    reach the player on cards and panels". Add: "A scenario is a premise, a scope and an
    opening. Scope is prose the master and the worldsmith read; nothing in code branches on it."
    `IDEAS.md`: delete item 20 (moving home).

16. **`README.md` and `docs/`.** `README.md` line 9 loses "and answers the game master's
    commissions". Replace the campaign paragraph (line 27) with one on scenarios: a scenario is
    a premise, a scope and an opening; scope is prose guidance on how far the adventure reaches
    and whether it tends toward an ending, asked for on the create page and read by the game
    master and the worldsmith; no mode, turn budget or ending is enforced. Add one sentence
    where saves are described: a save from before a stored-shape change is stale; the launcher
    skips it with a warning, and nothing migrates or deletes it. `docs/24XX.md`,
    `docs/BREATHLESS.md`, `docs/LONER-3E.md`, `docs/TUNNEL-GOONS.md`: delete the `commission`
    bullets and every "in a campaign" / "per job" / board clause (24XX deviation 3 and the
    `after_job` deviation's campaign half, Loner's growth deviation, Tunnel Goons' `level_up`
    bullet and deviation 1, Breathless' between-runs deviation). `NEXT-SPECS.md` decision 4:
    append "Since 2026-09-05 `commission` is gone; the cap is fifteen engine tools, counted as
    before." Nothing here describes the handoff or 24XX's jobs yet: Phase 2 adds them.

17. **Fixtures.** Regenerate and read. Expected changes, and nothing else:
    `prompts/<id>/master.txt`: THE SCOPE OF PLAY after SCENARIO, the "Ask for more" section gone,
    the question heading, no JOBS SO FAR or THE BOARD; `prompts/<id>/narrator.txt`: unchanged
    unless a golden turn's scene text changed; `schemas/<id>/master_tools.json`: `commission`
    gone, `next_scene` without `job_done`; `turn/<id>.json`: no `commissions`, no `job`, no
    `campaign`, `scope` in `scenario`, and `turn/tunnelgoons.json` visits without `recap`.
    `scenarios/*/world.json` change only as step 14 says; `characters/kael/*.json` do not change.

### Done when

- `grep -rnE "Campaign|Commission|ScenarioKind|at_hub|walked|job_done|hub_phrase|finished_note|reopening|debrief|ledger|Chapter|Board|Offer|GO_HOME|REPORT_IN|TAKE_JOB|question_heading|render_whole" src/ tests/` finds nothing.
- All four engines start from the create page and play a turn; every scene engine settles a
  scene and moves on from the page; Tunnel Goons extends its map from the page.
- `PROGRESS.md` holds the Phase 1 entry with both line counts. Full check green.

---

## Phase 2 — the generation handoff, 24XX's jobs, the documentation

Target: `src` grows by 150 to 250 lines over Phase 1's end.

Suggested split: **A** (steps 1–4: the handoff) and **B** (steps 5–6: 24XX) in parallel; they
share no file. Then **C** (steps 7–8: documentation, fixtures).

### The handoff, in one paragraph

A scene engine's game master may introduce a complication: a newly authored situation in the
place the player stands, written by the worldsmith. The ask is an argument of `next_scene`. It
lands as a pending brief on the current run; every later tool call in that turn is answered with
a wait line and changes nothing; the master exits; the turn narrates only what landed (the ask's
fact is untold, so the narrator cannot assert an uninstalled scene); the turn commits. The
service then writes and installs the new scene through `advance`, as it does for a player's
pursuit, and narrates the arrival. If the write or the install fails, the committed turn stands,
the brief stays on the run, the page disables the composer and offers one button that retries the
write; nothing is replayed. If the write lands and the arrival's narration fails, the installed
scene commits unnarrated, as a pursuit's does today: no second write. The brief on the run is the
whole handoff state; a reload finds it in the save and offers the same retry. Room engines are
untouched: a map extension still moves nobody and opens no scene.

### Steps

1. **`engines/scenes/` — the ask.** `world.py`: `SceneRun.complication: str = ""` (comment: the
   game master's brief for the situation the worldsmith writes here once the turn ends).
   `settle(pursuit: str, complication: str)`: refuses both set; refuses either on an
   already-settled run; refuses a complication when one is pending ("a complication is already
   pending: {brief}"); a complication sets `run.complication` and returns `[Fact(kind=
   "complication_asked", told=False, trace="the worldsmith writes the complication once this
   turn ends: {brief}. Nothing more lands this turn; stop and exit")]`; a pursuit is as in
   Phase 1. `ready` (in `engine.py`) is `run.left is not None or bool(run.complication)`.
   `tools.py`: `NextScene.complication: str = Field(default="", description="Set to change the
   situation here without the player leaving: what arrives or turns, and why, for the worldsmith.
   Written now, the turn ends; the player answers it next turn. Empty otherwise.")`; `NEXT_SCENE`
   gains "or set `complication` to bring a new situation down on this place, only when
   `change_world` (an arrival, a reveal, a death) cannot make it from what is here". `engine.py`:
   `next_scene` passes both. `handoff(state) -> str | None` returns `run.complication or None`.
   `advance` skips `self.leaving(draft)` when `run.complication` is set: the scene turns, it
   does not end (Loner's `leaving` refills every luck pool). An installed complication leaves
   its brief on the run it replaced, as the record of why the scene turned; `handoff` and
   `ready` read the current run only, so an older run's brief is inert, not stale state.
   `write_next`: when `world.run.complication` is set, the intent given to `render_next` is
   `COMPLICATION.format(brief=world.run.complication)` (in `worldsmith.py`: "The game master
   brings a complication down on the scene the player is in: {brief}. Write the situation it
   makes as a new scene. The same `place` is allowed and usual; whoever is here stays unless the
   brief moves them. Change the situation, not the player's answer to it: they have not acted, so
   settle nothing for them."), else the intent as given. `crossing(state, pursuit)`: when
   `run.complication` is set, returns `TURNING` (in `worldsmith.py`: "The situation changes where
   the player stands, and they did nothing to bring it on. Write what arrives or turns, as they
   see it, from SCENE and WHAT HAPPENED, and end on what it asks of them. They have not answered
   it, so settle nothing."), else `CROSSING` as today. `install` is unchanged: the new run has an
   empty `complication`, so `ready` and `handoff` fall back on their own.

2. **`engines/seam.py` and `turn/run.py` — the platform half.** `Engine.handoff(self, state:
   G) -> str | None` returns `None` (docstring: the brief a tool handed the worldsmith this turn;
   the platform writes it once the turn ends). `turn/run.py`: `HANDOFF_WAIT = "the worldsmith
   writes what you asked for once this turn ends. Stop here and exit."`; `Turn.call`, after the
   pending-decision answer, returns `HANDOFF_WAIT` when `self.engine.handoff(self.draft)` is not
   `None`. Nothing is counted per turn.

3. **`app/runtime.py` — the write after the turn, and the retry.** `play` refuses at its top
   when `self.engine.handoff(self.state)` is not `None`: "the worldsmith owes the scene the game
   master asked for; write it first". Its tail becomes: after `self._present()`, when the game
   is not over, `await self._grow(turn.prompt, brief)` for a pursuit crossing as today, else
   `await self._resume()` when `self.engine.handoff(state)` is not `None`; then `_present`.
   `_resume()` (private, no guards: `play` calls it while its own phase is still set): `asked =
   self.engine.handoff(self.state)`, `brief = self.engine.crossing(self.state, asked)`, `await
   self._grow(asked, brief, marker=HELD, unwritten=COMPLICATION_UNWRITTEN)`. `resume()`
   (public, the page's retry): refuses when busy ("a turn is already in flight") or when nothing
   is owed, sets `self.phase` and clears it in a `finally`, never sets `self.intent` (the page
   shows `intent` as the player's bubble, and the brief is the game master's), and calls
   `_resume()` then `_present()`. `_grow` gains two keywords with today's values as defaults:
   `marker: str = CROSSED` (the prompt a failed or arrived write is filed under) and `unwritten:
   Fact = UNWRITTEN`; its body is otherwise unchanged. New constants beside `CROSSED`: `HELD =
   "(the situation holds)"` and `COMPLICATION_UNWRITTEN = Fact(kind="complication_unwritten",
   told=True, trace="the complication could not be written", card="The situation could not be
   written. Press Write it to try again, or restart.")`. `UNWRITTEN` keeps its text: a failed
   pursuit and a failed room extension have no Write it button. On failure the run keeps its
   brief; on an unnarrated arrival the installed scene commits with its cards, as today.

4. **`ui/game.py` — the retry button, the disabled composer.** `Observed` gains `owed: bool`
   (`session.engine.handoff(session.state) is not None`). `can_type(player, phase, *, owed:
   bool)` is false while owed; `_placeholder` reads "The worldsmith owes the scene. Press Write
   it." while owed. `way_on_panel`, while owed, shows the banner "the situation is changing"
   with the button "Write it", whose handler returns on `refuse_play()` and otherwise awaits
   `self._run(self.session.resume)`; the Move on button is hidden while owed. `chat` and
   `journal` render `HELD` beside `BEGUN` and `CROSSED` as a story marker, never as the player's
   words. Tests, one each (`tests/core/test_turn.py`, `test_game_service.py`,
   `tests/core/test_scenes.py`, `tests/ui/test_game.py`): a call after the ask answers
   `HANDOFF_WAIT` and lands no fact; a turn with an ask commits, then writes and installs the
   scene in the same place with the cast kept, with no second master spawn; a failed write keeps
   the turn, the brief and offers `resume`, and `resume` installs without re-running the turn's
   tools; a failed arrival narration commits the installed scene once; `can_type` is false while
   owed.

5. **`engines/twentyfourxx/` — the job is the engine's.** `world.py`: `class
   TwentyfourxxWorld(SceneWorld[Person, Operator])` with `job: str = ""` (the terms of the job
   the operator is on; empty between jobs); `TwentyfourxxGame`, `TwentyfourxxScenario`,
   `TwentyfourxxCharacter` as they are. `tools.py`: `TakeJob(terms: str = Field(min_length=1,
   description="Who wants what done, what done looks like, what it pays, as agreed."))`;
   `FinishJob(skill: str = Field(default="", description="The skill the job called on, named by
   the player, to raise. Empty opens the pick to the player."))`; delete `AfterJob`.
   `engine.py`: `take_job` refuses when a job is open ("a job is open: {terms}"), else sets
   `world.job` and returns `player.fact("job_taken", "the job is taken: {terms}", card="Job
   taken\n{terms}")`; `finish_job` refuses when no job is open ("no job is open to finish");
   with an empty `skill` it sets `draft.pending = PendingDecision(kind="job-done", prompt="The
   job is done. Which skill rises?", options=(...), allows_text=False)` and returns `[]`; the
   options are one `PendingOption(id=slug(label, ()), label=label, name="finish_job",
   args={"skill": label})` per skill of the game's packs (`self.packs[p].skills for p in
   draft.packs`, de-duplicated by label, in pack order) whose die on the sheet is not d12; with
   a skill it raises the skill, rolls the d6 of credits, clears `world.job` and returns the
   three facts `after_job` returned, the first carded "Job done: {label} d{die}".
   `master_tools`: `take_job` and `finish_job` replace `after_job`. 24XX then counts sixteen
   (`change_world` and its nine arms, `next_scene`, `attempt`, `test_luck`, `defend`,
   `take_job`, `finish_job`), one over fifteen and under the twenty the standing rule allows an
   engine whose SRD plays a crew; step 6 names that allowance in `docs/24XX.md`. No fold is made
   for the count's sake. `sheet_sections` adds `("THE JOB", world.job)` when set; `panels` adds
   `Panel(title="Job", rows=(PanelRow(label=world.job, detail=""),))` when set. `rules.md`:
   replace "## Job done" with "## Jobs": "`take_job` when the player agrees to work, with the
   terms as agreed; the job then stands under THE JOB. `finish_job` once, when the story and the
   player's own words close it: it raises the skill the player names, pays the d6 of credits and
   clears the job. Empty `skill` asks the player which skill rises. Neither tool is needed for
   work the player never takes on." Tests, one each, in `tests/twentyfourxx/test_tools.py`: a
   second `take_job` is refused; `finish_job` without a job is refused; `finish_job` pays once
   and a second call is refused; an empty `skill` opens the decision and its option finishes.

6. **`docs/24XX.md`.** Tool list: `take_job`, `finish_job` replace `after_job`. Add a
   deviation: the SRD's job-finding roll is not played; work arrives in the fiction and
   `take_job` records it. Count: sixteen, under the twenty allowed an engine whose SRD plays a
   crew (starships, help dice, "make a new character to introduce ASAP"); this file is where
   `CLAUDE.md` says that allowance is named.

7. **Documentation.** `README.md`: line 9 gains "and writes the complication the game master
   brings down on a scene"; after the scenario paragraph Phase 1 wrote, add the handoff
   paragraph above, shortened to four sentences. `CLAUDE.md` design decisions: add "Generation
   is an engine handoff: a tool hands the worldsmith a brief, the turn ends, the platform writes
   and installs after it, and a failed write is retried from the page. There is no commission
   queue and no same-turn respawn." and "24XX owns its job lifecycle in its world and tools; no
   other engine has a job."

8. **Fixtures.** Regenerate and read. Expected: `schemas/<id>/master_tools.json` for the three
   scene engines gain `complication` on `next_scene`; `twentyfourxx` also swaps `after_job` for
   `take_job` and `finish_job`; `prompts/twentyfourxx/master.txt` changes by the rules text;
   `turn/twentyfourxx.json` gains `"job": ""` and every scene engine's `turn/<id>.json` gains
   `"complication": ""` on each run. Nothing else.

### Done when

- A scene engine's master can call `next_scene` with `complication`, every later call answers
  `HANDOFF_WAIT`, and the player reads the arrival in the same place with the cast kept, with
  one master spawn for the turn. A worldsmith that fails leaves the turn committed and the
  "Write it" button working; a reload shows the same button.
- 24XX pays a job once; a second `take_job`, a `finish_job` without a job, and a second
  `finish_job` are refused.
- `grep -rn "commission" src/ docs/ README.md CLAUDE.md` finds nothing.
- `PROGRESS.md` holds the Phase 2 entry. Full check green; `uv run aidm` plays a complication
  end to end.
