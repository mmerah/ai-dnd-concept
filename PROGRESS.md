# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

Start: `src` 9,452 lines, `tests` 6,044 lines.

## Probes (done, before phase 1)

**The scene kit.** A throwaway kit driven by a real CLI: 5 turns and one scene write.
`change_world` came to 5,479 bytes across 11 arms, against the map version's 5,926 across 10.
Zero schema-invalid and zero rule-refused calls. The worldsmith wrote a strong scene — a
complication drawn straight from the source, two existing cast brought back, the secret kept —
in 335 seconds, with one id error. Two fixes came from it: the scene boundary is computed by
`scene_spent`, not judged by the game master, and the worldsmith never names the player.

**`SceneState[S]` round-trip.** A generic parameterised by a discriminated sheet union, inside a
payload discriminated on `engine`. Sixteen checks passed: byte-identical JSON round-trip, both
discriminators rejecting bad input, the kit's validator still firing through the generic,
`extra="forbid"` holding, two engines coexisting under one adapter, and schemas generating.
`basedpyright` keeps full type information throughout — nothing degrades to `Unknown`. The one
rule: sheet unions must be plain assignments, never `type X = ...`, or the discriminator breaks.

## Phase 0 — Keep the probe code — DONE

Counts unchanged: `src` 9,452, `tests` 6,044. Phase 0 adds no shipped code.

Both probe programs moved into `docs/probes/` (637 lines), excluded from ruff, and left out of
`basedpyright` by its existing `include` list. Each file gained a header saying what it proved
and what it lacks, and its `/tmp` imports were made relative.

- `scene_kit.py` — the eleven `change_world` arms, `apply_change`, `render_worldsmith`,
  `scene_unmet`. **No `apply_scene`, no `scene_spent`**; those are new work in phase 2.
- `scene_fixture.py` — the drowned-road fixture the probe played against.
- `state_spike.py` — the `SceneState[S]` round-trip, 16 checks.

Verification: 289 passed; ruff check, ruff format and basedpyright all clean.

## Phase 1 — Cut to one engine — DONE

`src` 9,452 -> **7,471** (target ≈ 7,530, met with 59 to spare). `tests` 6,044 -> **4,411**.
Verification: 203 passed; ruff check, ruff format and basedpyright clean. `uv run aidm` boots and
serves 200 on `http://localhost:8080`.

All nine steps done in order, with the full check green at every one.

1. `evals/` deleted. `evals` also came out of `include` in `[tool.basedpyright]`, which the step did
   not mention.
2. `engines/twentyfourxx/`, `engines/breathless/`, `tests/twentyfourxx/`, `tests/breathless/`
   deleted, and both out of `pythonpath`. They were also in `extraPaths` under
   `[tool.basedpyright]`, which the step did not mention; that list is now one line.
   Their golden fixtures went too — `instructions/`, `prompts/`, `schemas/`, and the `save/`,
   `state/` and `turn/` files — because `ENGINE_IDS` no longer parametrizes them.
3. `scenarios/drowned-road/`, `scenarios/saint-ivo/`, `characters/kael/twentyfourxx.json`,
   `characters/kael/breathless.json` deleted. `scenarios/whispering-vault/` kept.
4. `tests/hostile/` deleted.
5. `registry.py` imports `loner3e.engine.build` directly; `ENGINES` is gone and `build_engines`
   returns `{engine.id: engine}`, so a folder-name-versus-declared-id mismatch is now impossible
   rather than checked. `test_package_boundary` hardcodes the one engine name, and
   `test_no_module_names_a_concrete_engine` asserts `{"engines/registry.py"}` instead of nothing:
   the composition root is now the one place allowed to name the engine. `AnyEngine` untouched.
6. Succession deleted: `world/succession.py`, `tests/core/test_succession.py`, the choice `kill`
   opened, and `validate` from `actions.kill`, `apply_change` and `rooms_tools`. `player_over` is
   now a two-line local in `loner3e/engine.py`. `Exchange.speaker` removed, and with it
   `Turn.speaker`, the `speaker` parameter of `Game.record` and of `close_segment`; the chat page
   draws every past prompt with the current player's speaker.
7. `Engine.resolvers` deleted, along with `Engine.tool()` and `Engine._required_tool` — one caller
   was left, so the lookup is inlined into `Engine.answer`. The option-revalidation loop in
   `restored()` is gone.
8. Player actions deleted: `PlayerAction`, `player_action()`, `offered()`, `play_action()`, the
   `player_actions` field, `GameService.offers`/`act`, the UI panel and `_act`, the
   `player_action` MCP tool with `PlayerActionCall`, `_offers_listing` and the YOU CAN block of the
   code-mode picture, and `tests/core/test_player_actions.py`.
9. Full check green; golden files rebuilt once. The only drift was the three `speaker` blocks
   dropping out of `fixtures/save/loner3e.json`. Nothing else moved — in particular the
   `change_world` schema golden is byte-identical, which it would not be if the union had shifted.

### Decisions the plan did not cover

- **Cross-engine integrity tests needed a second engine.** Rather than lose them, three now use a
  literal foreign engine id, `"ruleless"`, on otherwise valid content:
  `test_a_game_is_refused_a_scenario_or_a_character_from_another_engine`,
  `test_a_character_file_belongs_to_its_folder_and_its_engine`, and the sibling-name check in
  `tests/loner3e/test_create.py`. The refusals they prove all read the id, never a built engine.
- **`test_a_later_call_is_judged_against_the_mechanics_the_earlier_one_moved`** was 24XX credits.
  Ported to Loner: `complete_chapter`, then `advance`, then `advance` again, refused with "has no
  advance owed". It is the only test of a call judged against what an earlier call in the same turn
  moved, so it was worth carrying over rather than deleting.
- **Two code-mode decision tests** were driven by 24XX's `stake_attempt`. Ported to Loner's
  `roll_question` against a resisting item, which leaves the open-ended conflict hand-back.
- **Three tests deleted outright**, all of them about mechanics that left with their engine:
  `test_twentyfourxx_opposition_needs_no_sheet`;
  `test_a_resume_that_re_suspended_may_still_develop_what_the_answer_caused`, which resumed through
  an option-carrying decision, and after succession went Loner's only decision carries no options;
  and the second half of `test_the_engine_plays_the_hand_back_and_refuses_every_other_decision`,
  which asserted the restore-time revalidation step 7 deletes. The two refusals it checked now fire
  at `engine.answer` time and are tested there, in `test_decisions.py`.

### Deleted beyond the plan, because the last reader went with the two engines

- `spend()` in `engines/core.py` and its test — Breathless and 24XX were the only callers.
- `stake_decision()` in `engines/core.py` — same.
- `ChangeWorldWithoutImprovisedItem`, `WorldChangeWithoutImprovisedItem` and the `improvised` flag
  on `rooms_tools` — Breathless alone turned improvised items off.

### Review, and the fixes it forced

An adversarial review of the staged diff confirmed all nine steps done, every "deleted beyond the
plan" item genuinely caller-free, and the three `"ruleless"` tests still hitting the same three
raises they did with a second real engine. Three leftovers it found, all fixed:

- `tests/core/test_code_mode.py` still called `take_over` with a `successor_id`. Both the tool and
  the concept died this phase; it passed only because any unknown name is refused. Renamed to
  `test_a_name_the_engine_does_not_publish_is_refused` and given a name that never existed.
- `turn/run.py` carried a comment about succession carrying a dead character on, and the
  `chosen is None` conjunct it guarded was dead with it. Both gone.
- `app/runtime.py`'s `legacy` docstring still claimed player actions lived on the rooms dataclass.

Left for later, by the review's own reckoning: the `WorldChange` flattening comment and
`_CHANGE_DESCRIPTION` (phase 2 deletes the file), and the restore-time option revalidation that
step 7 moved to `engine.answer` — moot while Loner's only decision carries no options, worth
revisiting when phase 6 brings an optioned one back.

One coverage note the review raised and this phase cannot close: answering an *optioned* decision
through the MCP surface lost its only harness test with 24XX. Loner has no optioned decision, so
it cannot be re-covered without a synthetic tool. Phase 3 rewrites that path into
`play(action: str | Answer)`.

### The turn checkpoint, actually taken

Not just "the app serves 200". A fresh `Runtime` opened a new `whispering-vault--kael` game,
`submit()` ran a full turn against scripted director and narrator models, and the result was
checked end to end: the director's `change_world` landed a `Watchful` trait, the narrator's prose
recorded, the turn committed at 1, the save was re-read by a second `Runtime` at turn 1, and both
views rendered. The game plays.


### Known and accepted

- `README.md`, `CLAUDE.md` and `AGENTS.md` still describe three engines and the weak-model tool
  bar; `IDEAS.md` L1 still names `evals/turn_eval.py`. Phase 5 rewrites the first three; the
  IDEAS entry is the maintainer's own backlog and was left alone.
- `tests/core/fixtures/source/drowned-road.{md,pdf}` kept: `test_documents` reads them to test PDF
  and markdown parsing, not 24XX.
- The local `saves/whispering-vault--kael.json` does not load, but it did not load before this
  phase either — it still has top-level `player_id` and `world`, and `speaker_id` on its lines. The
  home page logs it and skips it. `saves/` is untracked.
- `docs/24XX.md` and `docs/BREATHLESS.md` kept; phase 6 needs them.

## Phase 2 — The scene kit, and Loner ported onto it — DONE

`src` 7,471 -> **5,806** (target ≈ 6,300; under, because step 9 also deleted the harness's four
authoring tools and the growth tools, which was the bulk of what phase 3 still had to remove).
`tests` 4,411 -> **3,408**. Verification: 179 passed; ruff check, ruff format and basedpyright
clean.

**The turn checkpoint, actually taken.** A fresh `Runtime` opened `whispering-vault--kael` and
`submit()` ran a full turn against scripted director and narrator models: `reveal` found the vault
map, `roll_question` rolled Advantage on Quiet Hands and answered `yes`, `move_item` put the map
in Kael's hands, the narrator's prose recorded, three cards landed, and the turn committed at 1. A
second `Runtime` re-read the save at turn 1 with the map still carried and all five sheet rows
rendering. `scene_spent` then fired, and the note for the next turn reads *"This scene looks
finished — everything here has been found."* `uv run aidm` serves 200 on both pages.

### Steps 1–4 — the kit (done, checked one by one)

`src/aidm/kits/scenes/` is seven files:

- **`state.py`** — `Entity[S: BaseModel]`, `Scene`, `Thread`, `SceneCanon[S]`, `SceneState[S]`, plus
  `labeled`, `entity_fact` and `kind_word`, which moved off the deleted map entity. Shapes copied
  from `docs/probes/state_spike.py`; the sheet union is a plain assignment, as the probe demanded.
  Two additions the plan did not name:
  - `Scene.opened_at` — the turn the scene was installed on. `scene_spent` counts turns in a scene
    from it, and nothing else in state could say how long the player has been here.
  - `SceneState.spent` — why the scene already looks finished, written by the arm that settled it.
    A thread resolving is a scene-ending signal, and a resolved thread stays resolved forever, so
    it cannot be derived after the fact. `apply_scene` clears it.
- **`tools.py`** — the eleven `change_world` arms and `apply_change`, ported from the probe to
  return typed `Fact`s with the card wording the map arms used. `scene_tools()` publishes
  `change_world`; core owns it and the engine adds its own procedures after it.
- **`boundary.py`** — `scene_spent(state)`, new, plus the `SPENT_NOTE` it is read out as. Five
  signals: the scene's `spent` note, nothing left hidden, someone here dead, two quiet turns, and
  a 12-turn cap. `close_segment` appends the note, so the game master is asked every turn the
  scene looks finished.
- **`worldsmith.py`** — `render_worldsmith` and `scene_unmet` from the probe; `apply_scene` and
  `SceneDraft` are new. The player is added by code, unknown ids resolve case-insensitively
  against cast names before refusal, and what the player and companions carry follows them.
- **`views.py`** — `narrator_view`, `player_view` and `director_view`, filled from kit state with
  the engine's sheet rows arriving through one callback.
- **`source.py`** — `whole_text`, `_pdf_pages`, `_passages`, `given_text`, moved off
  `authoring/draft.py`. `given_text` takes `max_chars` rather than `Settings`, so the kit stays
  clear of `aidm.config`.

**The scene bar has three checks in code, not four.** "A detail traceable to the source" cannot be
verified by code; it stays in the worldsmith's prompt.

### Steps 5–10 — the switchover

- **The engine is typed.** `engines/loner3e/state.py` is new and holds `ActorSheet`, `ItemSheet`,
  the `LonerSheet` union, `Loner3eState`, `Loner3eScenario`, `Loner3eCharacter` and the SRD
  constants. It imports the kit and nothing above it, which is what lets `state/model.py` name it.
- **The payload is typed, not a union yet.** With one engine, `Annotated[X, Field(discriminator=…)]`
  is not a legal single-member union, so `Payload = Loner3eState` with the `engine` tag already on
  it. Phase 6 turns the three aliases in `state/model.py` into real unions and nothing else moves.
- **One inversion, recorded.** `state/model.py` imports `engines/loner3e/state.py`. That is what
  closes the engine set at type-check time, as `VISION.md` §6 asks.
  `tests/core/test_package_boundary.py` records it as one named exception, and `ROOTS` now holds
  two files instead of one.
- **`content/io.py` takes an `EngineIdentity`**, a one-member protocol in `kernel/protocol.py`.
  It only ever needed `engine.id`, and `AnyEngine` was the only reason it named an engine at all.
- Deleted whole: `src/aidm/world/`, `src/aidm/authoring/`, `src/aidm/state/scene.py`,
  `src/aidm/content/model.py`, and from `state/entities.py` the map's `Entity`, `Exit`, `Kind`
  and `kind_word`.
- `Game` lost `player`, `player_id`, `label`, `add`, `reveal`, `move` and every `_legacy` property;
  `committed()` is one `model_validate` of one dump.

### Two decisions the plan did not anticipate

**`beat_closed` was cut, and the rule that closes a beat writes the signal instead.** PLAN step 5
and `VISION.md` §6 ask the engine for `beat_closed(state)`. No such predicate can work for Loner,
and not because the obvious one is badly written: **`_strike` refills both pools the instant a
side reaches zero**, by the SRD. By the time any predicate could run, a scene that just ended a
conflict is indistinguishable from one where nothing happened. The rule that knows writes
`SceneState.spent` at the moment it knows. `beat_closed` is gone from the `Engine` dataclass, the
protocol and `scene_spent`; `VISION.md` §2 and §6 are updated to match. `scene_closed` stays: it
is a mutation, not a predicate.

**The engine's sheet rows reach the prompts through the same callback the views use.** The first
port rendered the sheet from `model_dump(exclude_defaults=True)` inside the kit, which printed
`skills: ['a', 'b']` and silently dropped luck at 6/6 — the whole conflict clock — because full
luck is the default. `entity_line`, `director_view` and `render_worldsmith` now take `SheetRows`,
which is what `VISION.md` §2 says the seam is. The engine's `TAGS IN PLAY` section shrank to a
glossary of what the tags mean, because the sheets are on the entity lines already, and
`describe_rows` went with the duplication.

### Known and accepted

- **A scene change cannot be driven from play yet.** `apply_scene` is written and tested, but the
  only role that can write a scene is the worldsmith, which is a phase-3 spawn. Phase 2 has no
  `next_scene` tool, and building one against the pydantic-ai path would be work phase 3 deletes.
  PLAN's "force a scene change" is covered by `tests/core/test_scene_kit.py` for now.
- `harness/driver.py` and `harness/claude.py` still name the `growing-aidm` and `authoring-aidm`
  skills. Phase 3 step 10 deletes both skills and both files.
- `AuthoringConfig` became `SourceConfig` with one knob, `source.max_chars`. `request_limit`,
  `starter_character` and `growth_frontier` had no reader left.
- Deleted tests, with what went with them: the whole authoring and growth suites; the map's
  placement, exit-locking and room-walking checks; the mechanics-blob parse and describer tests;
  the `SerializeAsAny` payload guard; `when_reached`. `tests/core/test_scene_kit.py` is new and
  covers the arms, the scene boundary, `apply_scene`, the scene bar and the typed round trip.
- `Entity.description` is authored and now renders on the entity line, for the game master and the
  worldsmith only. Before this phase nothing read it.

### The adversarial review, and what it caught

A review pass against the staged diff found **seven correctness bugs**, all reproduced and all
now fixed with a regression test each. They are worth recording because six of the seven share
one cause: **a consequence that the map version settled was dropped in the port to arms.**

| what broke | why | fix |
|---|---|---|
| a scene could be installed with **no player in it**, and `apply_scene` would file the player under `hidden` | the probe's measured id failure (`kael` for `player`) landing in the wrong list, and no validator said the player is in their own scene | `SceneState` now requires the player present and known; `apply_scene` strips followers from both lists before anything else |
| `kill` **lost what the dead carried** | the arm cleared `carried_by` but never put the item in `present`, while its own trace said "fell loose here" | dropped items join `present`, which is what "here" means |
| `add_trait`/`remove_trait` accepted **a corpse, or someone two scenes away** | the arms used `_here`, which checks presence; the map version went through `require_actor_here`, which checks life too | one `_acted_on` helper: an actor must be here and alive, a thing only here |
| `scene_closed` **raised on a scene that ended in a death** | it restored luck through the tool-facing helper, which refuses the dead | `close_conflicts` lives in `rules.py`, skips the dead, and refills directly |
| `apply_scene` **mutated before it validated**, and could install a duplicate id | `model_copy(update=...)` skips validation, so `Scene`'s own uniqueness check never ran on the resolved list | ids dedupe on resolve, the `Scene` is built and validated first, and the world is touched only after |
| a save's `engine` and its payload's **could disagree** | the tag became the payload's discriminator, and nothing tied the outer field to it | one check in `Game._playable_game` |
| the scene bar **deadlocked forever** once every thread resolved | it asked whether the world held a standing thread, which no scene can change; `SceneDraft` had no way to open one | `SceneDraft` carries `threads`, and the bar counts the ones this scene opens |

Four smaller ones went with them: the name fallback for a wrong id was **dead for any capitalised
name**, because the field pattern rejected it before the fallback ran; `apply_scene` silently
un-knew a character the player had met and force-revealed items a companion carried; `move_item`
printed a card for a move that changed nothing; `reveal` could raise `IndexError` instead of
refusing.

**The fix that mattered most is the smallest.** `SceneDraft` stopped wrapping a `Scene` and became
the model-facing shape in its own right: free-text ids, no `id`, no `opened_at`. Code owns what
code owns, the name fallback works for every name, and the strict `Scene` is what gets stored.

### What the review was right about beyond the bugs

- **The scene-spent nudge was available in phase 2, and I said it was not.** `VISION.md` §2 is
  explicit that the payoff of `scene_spent` is the directive text, not the write. `close_segment`
  now appends `SPENT_NOTE` to `Game.notes`, which the existing `NOTES FROM THE RULES` section
  already renders. Three lines, no worldsmith, and phase 3 deletes none of it. The golden save
  carries the note, so it is proven end to end.
- `kits/scenes/rows.py` was a module for one type alias, created to dodge a cycle that existed
  only because `entity_line` sat in `worldsmith.py`. `entity_line` moved to `views.py`, where its
  only caller was; the module and the cycle both went.
- `Scene.opened_at` moved to `SceneState.opened_at`: one field instead of one per archived scene,
  and off the schema the worldsmith fills.
- `_kill` no longer writes `spent`; `scene_spent` already derives "someone here is dead".
- `engines/core.py` gave up everything only Loner read: `ADVANCE_SPENT`, `owed_notes` (now
  `advances_owed`), `party_member`, `check_packs`, `find_entry`, `authoring_guidance`. The fields
  nothing read — `Engine.state`, `Engine.packs` — and the `new_game`/`open_game` double name went
  with them.
- **`Engine.guidance` was wired wrong and invisible.** It was built once at `build()` time with
  `chosen=()`, so the selected pack tables were always `{}` — the exact failure `VISION.md` §3
  warns about ("without them the worldsmith writes fantasy tags into a cyberpunk game"). It is now
  `Callable[[Game], str]`, computed per game from `state.packs`.
- `PlayerView` carries `traits`, so `ui/panels.py` stops reaching past the view into engine state.
- `PROGRESS.md` contradicted itself about `beat_closed` forty lines apart, and `VISION.md` still
  specified the hook. Both fixed.

**Where I disagreed with the review.** It called `render_worldsmith`, `given_text` and
`scene_closed` dead code. PLAN steps 4 and 5 ask phase 2 to build all three, and `CLAUDE.md` says
to build an agreed capability in its final planned form. They stay, uncalled, until phase 3.

## Phase 3 — The three roles and the tool surface — DONE

`src` 5,806 -> **5,422** (target ≈ 5,650; under it, because deleting `llm.py` and the whole
`harness/` package cost more than the spawner, the MCP surface and `play()` added back).
`tests` 3,408 -> **3,275**.

### The probe taken before step 6, which was the plan's hardest piece

An MCP streamable-HTTP endpoint **mounts on the server NiceGUI already runs**. A throwaway served
`StreamableHTTPASGIApp(StreamableHTTPSessionManager(...))` at `/mcp`, opened `manager.run()` from
`app.on_startup` and closed it on shutdown; a real `mcp` client initialised, listed the tool and
called it. **No fallback is needed**, so `harness/claude.py` is deleted as step 9 allows.

### The end-to-end check, actually taken

Not just "the app serves 200". A `Runtime` with a real `CliSpawner` was mounted on a bare ASGI
server and `play()` was run:

- the app **spawned a real process** with the master prompt as its last argument (6,319 bytes);
- that process **connected back over HTTP MCP to the live game**, called `start_turn`, read the
  picture, called `change_world(reveal vault-map)` and read back
  `- learned of the item the vault map[vault-map]`;
- it exited, and **its exit ended the turn**;
- a second spawn answered as the narrator, its JSON was parsed and validated, and the turn
  committed at 1 with the map found and the prose recorded.

Separately, `uv run aidm` serves the eight tools on `http://localhost:8080/mcp/` to a real MCP
client and refuses with *"no turn is open. The player starts one from the page"* until one is.

A **nested `claude -p` spawn could not be run from this session**, so the one thing left unproven
is the argv shape of the shipped default command. That is one `uv run aidm` and one typed turn.

### The design, where it settled

**`start_turn` is what opens the turn, not `play()`.** `play()` builds the `Turn` before it
spawns, but `Turn.started` stays false until the game master calls `start_turn`. That is what
makes `VISION.md` §4's "no turn open" row real: nothing may change the world before the master
has read the picture. `start_turn` takes no arguments — the player's action is in the prompt.

**The tool surface finds its game through `Runtime.playing()`**: the one session with a turn in
flight. One process owns the game and turns are sequential, so there is at most one, and
`open_game` and `list_games` have nothing left to do.

**The legality table is split in two, deliberately.** `app/mcp.refusal` owns the ordering rules
(`start_turn` first, once, and not after the game ends). The pending-decision row stays in
`Turn.call`, where it already was and is already tested: two gates that could disagree would be
worse than one that lives beside the tools it guards.

**The picture is built once.** `render_picture` (the old `render_director`) is what both
`start_turn` and `scene` return, and it now carries RECENT PLAY and WAITING ON THE PLAYER, which
the code-mode harness used to bolt on. `render_master` is the small spawn prompt: the brief, the
engine's rules, the action.

**Each role's brief is in its prompt.** A spawned CLI has no system-prompt channel, so
`render_master`, `render_narrator` and `render_worldsmith` each open with a YOUR ROLE section and
close, for the two that answer, with an ANSWER WITH section holding the generated JSON schema of
the type they must return. The schema is generated, so it cannot drift from the type.

### Decisions the plan did not cover, and the deviations

- **`schema_of` went to `state/tools.py`, not `app/mcp.py`.** `turn/context.py` needs it to write
  the ANSWER WITH sections, and `turn` may not import `app`. It sits beside `DirectorTool`, which
  owns the `args` type it reads.
- **It does not inline `$defs`, and it did not need to.** The only thing pydantic-ai's generator
  did was strip *property* titles. Ten lines of post-processing reproduce it **byte-identically**
  against all five tool schemas, `$defs` and all, and the schema golden is unchanged.
- **`Roles` and `RoleConfig` were repurposed rather than deleted and re-created.** The plan says
  delete them; what it means is delete the model-provider config. The classes keep their names and
  now hold `command`, `model` and `timeout`, which is what `VISION.md`'s `.env` example asks for.
  `Roles` became `extra="ignore"` so a `.env` still holding `ROLES__DIRECTOR__*` keeps loading, as
  the plan promises.
- **`Spawner.act` returns the game master's output** rather than the plan's `None`, which would
  leave phase 4's dev tab with no source. `CliSpawner` reads the whole output at once, so a return
  value is all it takes; the callback the first draft used bought nothing.
- **`RoleConfig` has no `model` field**, though the plan names one. Every shape it could take is
  wrong for some CLI: `-m` is what this repo's old driver used and `claude -p` rejects it. The
  command carries the model — `claude -p --model opus` — which is the only thing that works for
  every CLI at once.
- **`write` takes a `check`.** The narrator's speaker rule and the worldsmith's scene bar are both
  "the answer parsed but is not acceptable", and both want the same one re-prompt. One
  `Check[T] | None` parameter serves both, and the retry loop is one shared function, so
  `ScriptedSpawner` retries exactly as `CliSpawner` does — which is what keeps the
  "a line spoken by someone not here is re-prompted with the id" test alive.
- **`render_narrator` lost the scenario premise**, as the plan's "and nothing else" says. It gains
  WHAT THE PLAYER HAS READ: the last told passages, which the player has already seen, so they
  leak nothing.
- **`Runtime` takes its spawner from the composition root**, rather than building one. That is
  what lets a test inject `ScriptedSpawner` without touching a private field.
- **`GameService.reload`, `poll_save` and the save-stamp were deleted here, not in phase 4.**
  They existed only for a second writer in another process, and `Settings.code_mode` — their only
  guard — went this phase.
- `BUILTIN_ONLY`, `CODE_MODE_ONLY` and the settings page's `applies` rendering also went now
  rather than in phase 4 step 7: with `harness` gone they had no reader and no marked field left.
- **`Settings._keys_present` was kept**, though the plan says delete it. Its role half went with
  `Settings.role()`; its media half is the only thing that refuses illustration with no key.

### The worldsmith, wired

`next_scene(intent, include)` returns at once and starts a background write against a **deep copy
of the committed state**. After every commit, `_speculate` starts the same write from
`scene_spent`'s reason when no write is running and no scene is waiting; a real intent that
differs cancels the speculative one. The finished scene is installed by **`start_turn`**, so the
picture the master reads already holds it, and `Engine.scene_closed` runs in the same
trial-validated apply. A scene whose snapshot is more than one turn old is discarded.

### Tests

- `tests/core/test_code_mode.py` -> `test_tool_surface.py`, rewritten: the published set, the
  legality table's three refusals, a change landing on the draft then on disk, the decision gate,
  `next_scene` not ending the turn and installing at the next `start_turn`, the scene bar refusing
  a thin scene, a stale scene discarded, a failed worldsmith saying why, the speculative write
  firing off `scene_spent`, and `CliSpawner` killing an abandoned process group.
- `tests/core/core_test_support.py` lost every pydantic-ai helper and gained `Table`: a live
  `Runtime`, its `GameService` and a `ScriptedSpawner`, with `call` mirroring the server by
  turning a refusal into a result the scripted master reads and carries on from. `changed(...)`
  and `tool_call(...)` keep their names and now return tool calls instead of `ModelResponse`s, so
  most call sites did not move.
- **Two tests deleted.** `test_a_paused_exchange_replays_as_a_message_and_a_silent_one_refuses`
  went with `exchanges_to_messages`: a fresh CLI gets RECENT PLAY as text, not a replayed message
  history. `test_the_driver_serves_this_app_s_own_mcp_server_in_process` went with the SDK driver.
- **Two tests are new for the new rule**: a game master that crashes after applying still commits
  what it applied, and a turn that applied nothing and failed is refused.
- The `fixtures/instructions/` goldens folded into the prompt goldens, which now cover master,
  picture and narrator.

### The adversarial review, and what it caught

A review pass against the staged diff walked all eleven steps and found **four correctness bugs**,
all reproduced and all now fixed with a regression test each.

| what broke | why | fix |
|---|---|---|
| `next_scene` **ran while a decision was pending** | the pending row of the legality table lives in `Turn.call`, and `next_scene` is a server tool that never reaches it — the split had a hole at exactly the tool that skips the second gate | one row in `refusal()` |
| a written scene the turn had **outgrown killed the whole turn** | the worldsmith snapshots the committed state, so a later change in the same turn can invalidate the scene; `apply_scene` then raised **out of `start_turn`**, so `started` stayed false and every later call was refused | `_install_scene` catches the refusal, records it and drops the scene: a lost scene costs less than a lost turn |
| a **stale scene was discarded and never rewritten** | `VISION.md` §1.2 says discarded *and rewritten*; the code only logged. With a 335-second worldsmith and a one-turn staleness bound, any write slower than a player turn was silently lost forever | the same intent is written again from a fresh snapshot |
| `final_message` **preferred an earlier fenced block** to the trailing JSON | a CLI that fences a code sample before answering would have its sample parsed as the answer | the fence is used only if it decodes as JSON |

Three smaller things went with them: `GameService.scene_spent()` was a wrapper with one caller;
`LonerScene` was a subclass whose docstring claimed a generic alias would not typecheck, which is
false — it is a plain assignment now; and `render_worldsmith` took a `shape` parameter with exactly
one possible argument.

The review confirmed the parts most likely to be wrong are right: `except (OSError, ValueError)`
catches a timed-out master (`asyncio.TimeoutError` is `TimeoutError`, which is an `OSError`) while
letting `CancelledError` escape; `finally` clears the turn on every path; the two-writes-in-one-turn
race cancels cleanly with no unretrieved exception; and `schema_of` is byte-identical, which the
untouched schema golden proves.

### Known and accepted

- The one turn against a real coding CLI has not been taken. Everything under it has.
- **There is one final-message reader, not one per CLI.** `VISION.md` §1 asks for a JSON event
  stream reader for CLIs that emit one. The shipped default is `claude -p`, whose last message is
  the answer, so the fence-or-trailing-object reader is enough. `codex exec --json` would need
  its own reader, and would fail loudly rather than quietly if pointed at one today.
- **A finished speculative scene is thrown away when the game master's own intent differs.** That
  is what PLAN step 8 asks for, and it means the common path pays for a second full write. Worth
  revisiting against real latencies.
- `README.md`, `CLAUDE.md` and `AGENTS.md` still describe the old design; phase 5 rewrites them.
- `Settings.turn.recent_exchanges` is the one depth every role reads, as before.
