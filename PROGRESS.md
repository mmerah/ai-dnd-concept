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
