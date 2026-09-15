# PLAN: the twenty-three QA findings, in three phases

Adversarial QA found 23 issues. Every fix the maintainer accepted is below; nothing else belongs
in this plan. Throughout, prefer removing or simplifying code over adding it.

The split is by blast radius, not by finding number:

- **Phase 1 — `engines`.** Findings 1–8. The only phase that moves a golden. One regeneration, at
  the end.
- **Phase 2 — `core` and `app`.** Findings 9–12. No golden moves.
- **Phase 3 — `ui`.** Findings 13–17, plus the one IDEAS.md line. No golden moves.

**Phase 1 runs first because it is the only phase that regenerates goldens.** Doing 2 or 3 first
would leave a stale tunnelgoons fixture for phase 1 to rewrite anyway.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Baseline before any change: `uv run pytest` **782 passed**; `ruff check`, `ruff format --check`
   and `basedpyright` all clean. Hold all four at that.
2. Do the phases in order, and the steps in a phase in order. Line numbers were read against the
   current tree; a step earlier in the same phase may have shifted them, so find the symbol the
   step names and treat the number as a pointer.
3. Where two steps touch the same file, the step says so. Do not fix the same line twice.
4. **Phase 1 goes red in the middle and stays red until step 8.** Step 1 reds
   `tests/core/test_golden_turn.py::test_a_worldsmith_request_renders_unchanged[tunnelgoons]` and
   step 3 reds `tests/core/test_golden_schemas.py::test_the_master_is_offered_the_same_tools[tunnelgoons]`.
   Both are the golden drift step 8 regenerates. Nothing else may be red between steps; a second
   failure is a step that went wrong.
5. Regenerating a golden:

   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest tests/core/test_golden_turn.py tests/core/test_golden_schemas.py
   uv run pytest
   ```

   `tests/conftest.py`'s `pytest_sessionfinish` fails any run with the flag set, so the second run
   is what proves the tree green. Phase 1 step 8 is the **one** step where a regeneration is
   allowed, and it names the two fixtures that may move.
6. `PROGRESS.md` gets one entry per phase, newest first, in the existing shape: line counts before
   and after, decisions made off-plan with the reason, and refuted review findings with the reason.
7. Two proposals are **refused**; record them in the phase-3 `PROGRESS.md` entry beside that
   phase's refusals:
   - **Pruning the save log.** Measured 5 KB → 88 KB over 100 turns with short narration, the whole
     file rewritten each turn. The log *is* the journal the player reads, so pruning removes a
     feature, and 88 KB is negligible in absolute terms.
   - **Paging the transcript in the UI** (the fix for the IDEAS.md line in phase 3 step 6). ~30–50
     lines of new UI for a cost invisible below ~150 turns; CLAUDE.md says "do not build for future
     needs."
8. The game stays playable at the end of every phase: `uv run aidm`, open a scenario, take a turn.

---

## Phase 1 — `engines`

### Steps

1. **A region is the rooms analogue of a scene.** `aidm.core.play.Chapter` means "a scene"
   everywhere except the rooms engine, where `open_chapter` sits inside `move()`
   (`src/aidm/engines/rooms/engine.py:212`) so a chapter means "one room arrival", and rooms never
   write a `recap`. Walking between two rooms 60 times on `buried-keep` makes 60 chapters with 0
   recaps; the master prompt goes 6,475 → 19,473 chars and keeps growing linearly against Linux's
   128 KiB argv cap. Worse: `told_history` (`src/aidm/core/prompt.py:37`) reads the last 2 chapters
   only, so a player who walks every turn gives the narrator 2 turns of memory out of 12.

   Mirror `NextDraft(SceneDraft)` (`src/aidm/engines/scenes/tools.py:72`) and `install`
   (`src/aidm/engines/scenes/engine.py:266-272`):

   - `src/aidm/engines/rooms/world.py`: add a `MapDraft` subclass directly after `MapDraft`
     (`:124`) carrying a required `recap: str = Field(min_length=1, description=…)`. Copy
     `NextDraft.recap`'s description style, worded for a region.
   - **Delete `map_model`, do not add a second attribute beside it.** Both room engines set it to
     exactly `MapDraft[self.member]`, so it is already redundant; the scenes family spells
     `NextDraft[self.member]` and `SceneDraft[self.member]` inline with no attribute
     (`src/aidm/engines/scenes/engine.py:256`, `:294`, `:297`). Delete the declaration
     (`rooms/engine.py:59`), `src/aidm/engines/tunnelgoons/engine.py:89` and
     `tests/support/sixth.py:49`. `author` (`rooms/engine.py:177`, `:179`) then spells
     `MapDraft[self.member]` inline and `write_next` (`:237`, `:240`) the new region type. Net
     removal instead of net addition.
   - Delete `self.open_chapter(draft)` from `move()` (`:212`). Add it to `install()` (`:243`) after
     `attach(...)`, with `draft.log[-1].recap = extension.recap` **before** it — the same order as
     `scenes/engine.py:269-272`. `write_next` and `install` retype to the region model.

   Three facts to state in `PROGRESS.md`, so nobody re-derives them:

   - **The anchor place's title is required, not a caveat.** `attach` does not move the player
     (`src/aidm/engines/rooms/world.py:405-415`), so `narrator_view()` titles the new chapter from
     the place the player still stands in. That is correct: `check_extension` forces the region's
     own `start` place to be hidden (`rooms/worldsmith.py:17` → `_map_unmet(start_known=False)`),
     so titling from the region would leak a hidden name into the narrator's
     "WHAT THE PLAYER HAS READ" header.
   - **The empty-trailing-chapter pop** (`src/aidm/engines/seam.py:277-278`) is right at the new
     call site: it is only reachable when MORE_MAP fires before any exchange, and the recap is then
     dropped with the empty chapter, which is what should happen.
   - **Nothing persisted is invalidated.** `TunnelGoonsScenario = Scenario[MapDraft[Npc]]`
     (`tunnelgoons/world.py:129`) is what lands on disk; the region draft is consumed by `attach`
     and never stored, and `Game.generation` is `exclude=True` (`src/aidm/core/model.py:105`).

   Known and accepted: a player who never triggers MORE_MAP has one chapter for the whole game,
   capped at `exchanges[-20:]` — scene engines have the same gap inside one long scene.

   Proof. Five tests break and must be fixed in this step:

   | test | why |
   | --- | --- |
   | `tests/tunnelgoons/test_worldsmith.py:72` `an_extension_of_one_hidden_place_with_no_ways_installs_hidden` | passes a bare `MapDraft` to `install` → `AttributeError: 'recap'` |
   | `tests/tunnelgoons/test_worldsmith.py:240` `install_on_a_game_from_the_engine` | same, through `_region()` (`:33`) |
   | `tests/tunnelgoons/test_worldsmith.py:264` `write_next_asks_for_the_map_draft` | replays module-level `THIN.model_dump()` (`:22`) through the region model → `ValidationError`; its `recorded == [MapDraft[Npc]]` assertion also moves |
   | `tests/tunnelgoons/test_worldsmith.py:280` `write_next_prompt_carries_scenes_so_far` | same `THIN.model_dump()` replay |
   | `tests/tunnelgoons/test_play.py:17` `REGION` | the module-level dict feeds the worldsmith in `the_shipped_map_plays_start_to_finish`; it needs a `"recap"` key |

   `tests/engines/test_rooms.py:404` reads `room_engine.map_model` and becomes
   `MapDraft[Dweller]`. `tests/tunnelgoons/test_tools.py:233`
   (`a_place_walked_through_without_a_word_is_no_chapter`) still passes but now pins nothing —
   delete it or rewrite it against `install`. Add one test: two `move` calls open no chapter, and
   `install` closes the old chapter with the region's recap and opens one new chapter.

   Also touches `src/aidm/engines/tunnelgoons/engine.py` (step 3) and
   `tests/tunnelgoons/test_worldsmith.py` (step 2).

2. **One cast bar for both engine families.** `scene_unmet`
   (`src/aidm/engines/scenes/worldsmith.py:71-76`) enforces `entry.required()`; `check_map` and
   `check_extension` (`src/aidm/engines/rooms/worldsmith.py:8`, `:13`) never call it.

   - Lift that one comprehension into a free helper beside `named_unmet`
     (`src/aidm/engines/base.py:371`), taking the entry pool and the ids already filed, and
     returning the `"{id}: {why}"` list. Call it from `scene_unmet` and from both room checks over
     `draft.npcs`. Each caller keeps its own sentence. **Both room calls pass `()` for the filed
     ids**: `check_map` has no world, and `_overlap_unmet` (`rooms/worldsmith.py:38-43`) already
     bars any id reuse in an extension, so the argument is vacuous there.
   - `src/aidm/engines/tunnelgoons/world.py`: add `required()` to `Npc` (`:75`) adding
     `"health above zero"`. Engine-local — it must not reach scene engines. Today an authored NPC
     at 0 HP is alive with Difficulty Score 0, so every roll against it auto-succeeds and kills it.
   - `src/aidm/engines/rooms/worldsmith.py`: in `check_extension`, refuse any extension item whose
     `on` is `PLAYER_ID`. `Dungeon._consistent` allows it (`rooms/world.py:58-64`), so today an
     extension can put items into the player's pack with no fact and no narration, silently
     counting against Inventory 8.

   Accepted feature cost: the worldsmith can no longer author an already-dead NPC entity; a corpse
   belongs in the place's `description`.

   Proof: the shipped `buried-keep` map has 3 npcs, all alive, all HP > 0, none sheeted, so nothing
   migrates — `tests/tunnelgoons/test_worldsmith.py:86`
   (`the_shipped_scenario_passes_the_map_bar`) must stay green. Add three refusal tests beside it:
   a map whose npc is dead, a map whose npc is at 0 HP, and an extension whose item is `on` the
   player.

   Also touches `tests/tunnelgoons/test_worldsmith.py` (step 1).

3. **Tunnel Goons level-up soft-lock.** `level_up`
   (`src/aidm/engines/tunnelgoons/engine.py:209`) resolves `args.actor_id`, which lets the master
   start the chain mid-party; `next_to_level` (`src/aidm/engines/tunnelgoons/world.py:120`) then
   re-queues someone already at level 2 and every option of the pending decision is refused — an
   unrecoverable soft-lock, escapable only by Restart, which discards the save.

   Both halves are needed; either alone leaves the lock reachable.

   - `src/aidm/engines/tunnelgoons/engine.py`: insert, **above** the existing
     `if args.ability is None or args.boost is None:`,

     ```python
     actor = world.player if args.ability is None else world.require_actor(args.actor_id)
     ```

     Keep the test inline and keep the existing `if` exactly as it is: hoisting the condition into
     a variable loses basedpyright's narrowing of `Ability | None` → `Ability` and costs two
     errors. The ask branch now ignores `args.actor_id` entirely and the chain walks the party by
     position.
   - `src/aidm/engines/tunnelgoons/world.py`: `next_to_level` returns the first member **at or
     after** the actor's position whose sheet is still at level 1, not `members[index]`. Without
     this, a master calling `level_up(actor_id=<a member>, ability=…, boost=…)` directly still
     hands the decision to someone already at level 2.
   - **Keep the `level > 1` guard** (`:212-213`) on the resolved actor — it is the backstop against
     a direct repeat call.
   - The refusal text says "has already levelled up this adventure" but the code has no notion of
     an adventure. Drop "this adventure" from the string.
   - `src/aidm/engines/tunnelgoons/tools.py:55`: change `LevelUp.actor_id`'s description from the
     shared `ACTOR` constant to `"Leave empty."`. Precedent: `src/aidm/engines/base.py:155`. This
     is the real fix — `LEVEL_UP` (`tools.py:14`) already says "Call this once… The engine opens
     the pick to the player, then to each living hired member in turn", `ACTOR`
     (`base.py:19`) says "Exact id of a hired party member here who acts", and the model believes
     the parameter.
   - `docs/TUNNEL-GOONS.md:57`: deviation 1 reads "once per adventure" → "once per game".
   - **Do not** add a levelling section to `src/aidm/engines/tunnelgoons/rules.md`.

   Proof: `tests/tunnelgoons/test_tools.py:204`
   (`level_up_with_no_args_does_not_offer_a_character_already_levelled`) and `:398`
   (`level_up_for_the_player_opens_the_members_decision`) both stay green. Add two tests: a no-args
   `level_up` carrying `actor_id=<a hired member>` opens the **player's** decision; and a direct
   `level_up` for the second of three members skips nobody back to a levelled one.

   Also touches `src/aidm/engines/tunnelgoons/engine.py` (step 1).

4. **Breathless loot ids can raise out of a tool call.** `loot_options`
   (`src/aidm/engines/breathless/world.py:80-104`) mints option ids by concatenation
   (`f"{SWAP}{key}"`, `:91`), and `PendingOption.id` is a `Slug` capped at 64 while `slug()`
   already emits up to 64 — so an item name over ~59 chars raises a raw `ValidationError` out of a
   tool call, escaping uncaught and violating CLAUDE.md's "any other exception is a bug". Reachable
   from player-typed text: Breathless character creation's `item` field accepts 100 chars.

   Fix the id, and only the id: `f"{SWAP}{key}"` → `f"swap-{index}"`, by enumeration order over
   `self.items`. `args` is `dict[str, JsonValue]` with no `Slug` constraint, so `args["choice"]`
   keeps the `SWAP`-prefixed key and `take_loot` (`:169-171`) is untouched.

   **Do not** make the id the bare item key, and **do not** reshape `TakeLoot.choice`
   (`src/aidm/engines/breathless/tools.py:95`) into a `Literal` with a separate target field. A
   bare key collides with the `take` and `med-kit` option ids, and that collision is worse than the
   overflow: `PendingDecision._options_are_unambiguous` (`src/aidm/core/play.py:88-91`) calls
   `check_unique`, which raises `Refusal`, and `Refusal` subclasses `ValueError`
   (`src/aidm/core/entities.py:38`), so inside a model validator Pydantic wraps it into a raw
   `pydantic_core.ValidationError` — verified. Code-controlled bounded ids remove both failures and
   leave `SWAP` and the two `removeprefix` calls in place.

   Proof: `tests/breathless/test_tools.py:173`
   (`loot_on_an_item_with_a_full_backpack_offers_swaps`) asserts the swap option ids and changes;
   `:197` (`loot_replay_applies_the_option_the_roll_wrote`) replays through `args` and stays green.
   Add one test: an item name of 100 characters produces options and replays without raising
   anything but `Refusal`, and an item keyed `take` does not collide. `take_loot` is not a
   registered master tool, so no schema golden moves.

5. **24XX: a defense is spent on a setback that costs nothing.** With no defense declared, a
   setback whose risk is not deadly lands **nothing** (`take_hit`,
   `src/aidm/engines/twentyfourxx/world.py:215-230`, final line). But the `item_id is not None`
   branch (`:225-227`) sits above the `disaster` check and never looks at it, so declaring
   `defend_with` costs the item **and** the hindrance to absorb a consequence that was never
   coming. `docs/24XX.md:50-54` says `risk` is what the actor suffers "in full on a disaster" and
   `defend_with` "breaks to spare them instead", and the Deviations section (`:64-70`) lists
   defense as the SRD's exact one.

   Fix: a guard at the top of `take_hit` — when it is neither a disaster nor deadly, return no
   facts. Everything else unchanged. Do **not** nest the branch inside `if disaster:` — that is
   more branches for the same result. The guard makes the final line's `else []` unreachable, so it
   becomes `return actor.hinder(MAIMED)`.

   Proof. Two tests pin the bug and must be rewritten here:

   | test | why |
   | --- | --- |
   | `tests/twentyfourxx/test_tools.py:277` `setback_with_defend_with_breaks_gear_instead_of_maiming` | its roll is a non-deadly setback; rewrite with `deadly=True` to pin the case that still matters — a deadly setback's defense breaks the gear and spares the maiming |
   | `tests/twentyfourxx/test_tools.py:295` `helper_defends_with_their_own_gear_while_actor_takes_their_own_consequence` | seed 15 is a non-deadly setback, so the helper's vest no longer breaks; rewrite with `deadly=True` on the `Helper` (`twentyfourxx/tools.py:107`) |

   Add one test that a non-deadly setback with `defend_with` leaves the gear intact and the sheet
   unchanged. `:121` (`deadly_setback_maims_not_doubled`) and `:137`
   (`non_deadly_setback_with_no_hindrance_named_lands_nothing`) must stay green.

   Also touches `src/aidm/engines/twentyfourxx/world.py` and `tests/twentyfourxx/test_tools.py`
   (step 6). Do step 5 first; step 6 then edits the same method.

6. **24XX: a hindrance named on a harmless item evaporates.** `take_hit` coerces
   `"" if item.harmless else hindrance` (`src/aidm/engines/twentyfourxx/world.py:227`), while the
   standalone `defend` tool refuses the same combination through `_break` (`:251-253`).

   - `src/aidm/engines/twentyfourxx/world.py:243-244`: `check_defenses` currently does
     `if item.harmless: continue`, skipping the check. Refuse there instead, with `_break`'s
     wording. It runs at `src/aidm/engines/twentyfourxx/engine.py:419`, **before** the roll at
     `:422`.
   - Then **delete** the `"" if item.harmless else` coercion in `take_hit`: the bad combination can
     no longer reach it.
   - Do **not** let `_break` refuse post-roll — `docs/24XX.md:53-54` promises "Gear is checked
     before the roll, so a defense the rules cannot honour never costs a die." `_break` keeps its
     own refusal for the standalone `defend` tool.

   Proof: add one test — a `roll` with `defend_with=<harmless gear>` and a `hindrance` is refused
   and the draft is unchanged, in the shape of `tests/twentyfourxx/test_tools.py:265`
   (`defend_with_non_harmless_gear_and_no_hindrance_is_refused_before_any_dice_roll`). `:184`
   (`defend_with_harmless_gear_spares_a_disaster_and_adds_no_hindrance`, no hindrance passed) and
   `:485` (`defend_hull_armor_breaks_harmlessly_and_refuses_a_hindrance`, the `defend` tool) must
   stay green.

   Also touches `src/aidm/engines/twentyfourxx/world.py` and `tests/twentyfourxx/test_tools.py`
   (step 5).

7. **Screen the master's free text onto the loner3e sheet — `drive` and `change_tags` both.**
   `drive` (`src/aidm/engines/loner3e/world.py:99-112`) writes master-authored
   `goal`/`motive`/`nemesis` onto the cast member, and `rows()` (`:58-74`) puts them into the sheet
   the narrator reads — permanently, on every later turn. `change_tags`
   (`src/aidm/engines/loner3e/engine.py:185-187`) is the identical path one tool over:
   `ChangeTags.gained` (`src/aidm/engines/loner3e/tools.py:26`) is master-written free text landing
   in the same `rows()` as Gear and Conditions (`world.py:65-66`). The leak is the **stored sheet
   row**, not the fact's `told` flag; dropping `told` does not fix it. `Roll.question` is already
   fenced for exactly this reason (`src/aidm/engines/loner3e/engine.py:234-235`).

   Fix both in this step — the screen is being added two lines away. `named_unmet(text, entities)`
   (`src/aidm/engines/base.py:371`) already returns the hidden names a piece of text leaks, and is
   used on worldsmith output at `src/aidm/engines/scenes/worldsmith.py:78`, `:83` and
   `src/aidm/engines/rooms/worldsmith.py:55`, `:59`. Add one check to `Loner3eWorld`
   (`src/aidm/engines/loner3e/world.py:139`) beside `check_conflict` (`:170`) that runs
   `named_unmet` over the strings it is handed against `self.hidden()`'s entities and refuses; call
   it from `Loner3eEngine.drive` (`:189-191`) over the three drive strings and from
   `Loner3eEngine.change_tags` (`:185-187`) over `args.gained`, each before the world method runs.
   `lost` needs no screen — those strings are already on the sheet.

   Proof: add two tests in `tests/loner3e/test_tools.py` — `drive` naming a hidden entity in
   `nemesis` is refused and the cast member's rows are unchanged; `change_tags` naming one in
   `gained` likewise. The same calls naming a revealed entity land.

8. **The master's `pursuit` reaches the narrator verbatim, and the phase's one golden
   regeneration.** `depart` (`src/aidm/engines/scenes/engine.py:307-312`) interpolates
   `request.detail` — master free text — into `CROSSING`
   (`src/aidm/engines/scenes/worldsmith.py:8-14`), which becomes the narrator's PLAYER ACTION.

   Remove the master from that path rather than screening it: the player's own words are already in
   the log. Use those for the narrator's half of `CROSSING`; keep `request.detail` for the
   worldsmith prompt, which is unchanged.

   Implementation notes:
   - Capture the words at the **top** of `depart`, beside `left`. `install` calls `open_chapter`,
     which appends a fresh empty chapter, so after it `draft.log[-1].exchanges` is empty.
   - Guard the empty case. `tests/core/test_golden_turn.py:56`
     (`a_worldsmith_request_renders_unchanged`) calls `advance` on a freshly begun game whose only
     chapter has no exchanges, so an unguarded `[-1]` raises `IndexError` there.
     `Game.exchanges()` (`src/aidm/core/model.py:113`) is the flat read.
   - `Generation` (`src/aidm/core/model.py:90-95`) carries only `operation`, `detail` and `target`
     — it does not carry the player's words, so they come from the log.

   Proof: add one test in `tests/engines/test_scene_bar.py` or beside
   `tests/breathless/test_tools.py:253` (`next_scene_with_pursuit_requests_the_crossing`) — a
   `pursuit` naming a hidden entity does not appear in the telling `depart` returns, while the
   player's own words do.

   **Then regenerate.** This is the one regeneration in the plan. Exactly two fixtures may move:

   | fixture | why |
   | --- | --- |
   | `tests/core/fixtures/schemas/tunnelgoons/worldsmith_answer.json` | step 1: `write_next` now asks for the region model, which carries `recap` |
   | `tests/core/fixtures/schemas/tunnelgoons/master_tools.json` | step 3: `LevelUp.actor_id`'s description |

   No prompt fixture may move, tunnelgoons included. `master.txt` is built once at turn start
   (`src/aidm/app/roles.py:60` calls `turn.picture()` before the master runs), so the scripted
   `move` cannot change the log it renders; and the fresh chapter `move` used to open carries no
   exchanges, which `told_history`'s `if chapter.exchanges` filter (`src/aidm/core/prompt.py:39`)
   already drops from `narrator.txt`. Nothing under `tests/core/fixtures/turn/` may move — no step
   changes a fact. No `worldsmith.txt` may move — the answer model appears only in the masked
   `ANSWER WITH` tail. If a fixture you did not expect drifts, read the diff before accepting it.

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

---

## Phase 2 — `core` and `app`

### Steps

1. **A source document can open its own prompt sections.** An uploaded document of up to
   `source_max_chars` (96,000) lands whole under `SOURCE MATERIAL`, and `sections()`
   (`src/aidm/core/prompt.py:13`) is plain concatenation with no fencing, so a document can open
   its own section header after the real ones.

   `src/aidm/core/source.py`: `_passages` (`:46-51`) drops any passage that is a bare all-caps
   heading, matching `^[A-Z][A-Z '\-]+:$`. Discarding running headers is already what `_passages`
   exists to do — this is one more line in the filter it already runs.

   What this actually adds: `MIN_PASSAGE = 24` (`:9`) already drops `YOUR ROLE:` (10 chars) and
   `ANSWER WITH:` (12) — they are too short to survive as passages. The new filter covers the
   all-caps headings of 24 characters or more that stand alone in a paragraph, such as
   `WHAT THE PLAYER HAS READ:`. Narrower than it looks, and still worth the one line.

   Proof: add one case to `tests/core/test_documents.py` beside
   `a_markdown_document_reads_to_text_without_its_furniture` (`:13`) — a document holding
   `WHAT THE PLAYER HAS READ:` on its own paragraph reads back without it, and a line of ordinary
   prose ending in a colon survives.

2. **An IDN base url escapes every `except HTTPError`.** `_valid_base_url`
   (`src/aidm/config.py:38-45`) validates with `AnyHttpUrl(base_url)` (`:44`), which punycodes an
   IDN hostname and accepts it. `httpx.URL` then rejects it with `httpx.InvalidURL`, which does
   **not** subclass `httpx.HTTPError` — so it escapes `src/aidm/app/builtin.py:60`,
   `src/aidm/app/media.py:85`, `src/aidm/app/speech.py:75` and `src/aidm/ui/game.py`'s `_run` as an
   uncaught 500.

   **Add the second check; keep the first.** They catch different things — verified:

   | url | `httpx.URL` | `AnyHttpUrl` |
   | --- | --- | --- |
   | `http://☃.example/v1` | `InvalidURL` | accepted (punycoded) |
   | `http://localhost:99999/v1` | accepted | rejected |
   | `not a url` | accepted | rejected |

   Keep `AnyHttpUrl(base_url)` and the `AnyHttpUrl` import (`:7`), and add below it the real
   request URL the providers build:

   ```python
   try:
       httpx.URL(f"{base_url}/chat/completions")
   except httpx.InvalidURL as bad:
       raise ValueError(...) from bad
   ```

   The `raise ... from` is required: `httpx.InvalidURL` is **not** a `ValueError` (verified), so
   raised bare inside a `field_validator` Pydantic will not wrap it and it escapes as the wrong
   type.

   Proof: add one case to `tests/test_config.py` beside
   `a_malformed_provider_base_url_is_refused` (`:42`) — `http://☃.example/v1` is refused. That
   test, `:51` (`a_valid_base_url_is_kept_exactly_as_given_not_normalized`) and `:56`
   (`a_padded_base_url_is_stored_stripped`) must all stay green; `http://localhost:11434/v1` and
   `https://openrouter.ai/api/v1` pass both checks.

3. **A disk failure is reported as a failed worldsmith.** `_grow`
   (`src/aidm/app/runtime.py:223-258`) wraps `engine.advance`, `_narrated`, two `self.save(...)`
   calls (`:236`, `:240`) and, in its `except`, a third (`:245`). `FileStore.write` raises
   `Refusal` on any `OSError` (`src/aidm/core/io.py:40` → `publish`, `:148-159`), so a disk failure
   is logged as "the world did not grow", the scene the worldsmith just wrote is discarded, and a
   second save is attempted which fails identically and propagates anyway.

   Narrow the `try` to `advance` and `_narrated`; hoist the three `save(...)` calls into exactly
   one after the `try/finally`, choosing `engine.land(draft)` when there is nothing to tell and
   `engine.close(...)` otherwise. The `except` branch replaces `draft` and supplies its own facts,
   so the hoist needs the lines, facts and telling held in locals initialised before the `try`:
   expect this to come out roughly line-neutral, not as a cut.

   Proof: add one test in `tests/app/test_game_service.py` — a `save` that raises `Refusal`
   propagates out of `_grow` instead of being logged as a failed write, and the fallback
   `unwritten` fact is not substituted for the scene the worldsmith returned.

   Also touches `src/aidm/app/runtime.py` (step 4).

4. **A scenario-drift refusal names a field it did not compare.** `_resumed`
   (`src/aidm/app/runtime.py:408-433`) compares the whole `ScenarioMeta` (`:425`) but reports only
   `.title` (`:427-428`), so drift in `premise`, `scope`, `art_style` or `voice` prints
   `save scenario is 'X', selected scenario is 'X'`.

   Keep the guard strict — `scope` is read by the master and the worldsmith every turn, so silently
   accepting drift would redirect a game in progress. Change the message to name the fields that
   differ. `ScenarioMeta`'s fields are `title`, `premise`, `scope`, `art_style`, `voice`
   (`src/aidm/core/model.py:26-31`).

   Proof: add one test in `tests/app/test_game_service.py` — a save whose scenario differs only in
   `scope` is refused with a message naming `scope` and not naming `title`.

   Also touches `src/aidm/app/runtime.py` (step 3).

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

---

## Phase 3 — `ui`

### Steps

1. **The app and `/mcp` listen on every interface.** `ui.run(...)`
   (`src/aidm/ui/app.py:111-116`) passes no `host`, and NiceGUI defaults to `0.0.0.0`. `/mcp`'s
   only guard is `allowed_hosts=["127.0.0.1:*", "localhost:*"]` (`src/aidm/app/mcp.py:59`), a
   Host-header check any non-browser client sets freely — verified from a network peer, which
   listed the master's tools and rolled dice into a live turn.

   - `src/aidm/config.py`: add `server_host: str` defaulting to `"127.0.0.1"` beside `server_port`
     (`:132`).
   - `src/aidm/ui/app.py`: pass it to `ui.run`.

   Setting it to `0.0.0.0` exposes `/mcp` too. The Settings page renders the new key automatically
   — `_shown` (`src/aidm/ui/settings.py:104-110`) skips only `Path` and `tuple`.

   Proof: add one case to `tests/test_config.py` — the default is `127.0.0.1`, and the env var
   overrides it. The var is **`SERVER_HOST`**, not `AIDM_SERVER_HOST`: `Settings` sets no
   `env_prefix` (`src/aidm/config.py:113-119`) and `env_key` is `"__".join(path).upper()` (`:161`),
   which is why the existing tests set `ROLES__MASTER__MODEL` and `MEDIA__ENABLED`.

   Also touches `src/aidm/ui/app.py` (step 4).

2. **A non-`Refusal` role failure loses the turn in silence.** `_run`
   (`src/aidm/ui/game.py:600-617`) catches only `Refusal`; NiceGUI swallows everything else, so the
   player gets no toast, no spinner and no transcript line — Send into the void.

   Add an `except Exception` after the `except Refusal`, notify the player, and **re-raise**.
   Re-raising keeps CLAUDE.md's rule intact: the bug is not handled, it still propagates and logs.

   Notify a **fixed string**, not `str(exception)`. A `Refusal` is the only exception written for
   the player to read; any other may carry hidden canon or a filesystem path, and putting it on
   screen is the leak the rule exists to stop. Something in the shape of "Something went wrong.
   The turn did not land — check the server log." The detail stays in the log, where the re-raise
   puts it.

   Proof: add one test in `tests/ui/test_game.py` beside
   `a_refusal_that_is_not_the_in_flight_guard_still_toasts` (`:419`) — a callable raising
   `RuntimeError("secret path")` notifies the fixed string, does **not** notify `"secret path"`,
   and the exception still leaves `_run`.

   Also touches `src/aidm/ui/game.py` (step 5).

3. **A second save on the settings page is silently dropped.** `SettingsForm.save`
   (`src/aidm/ui/settings.py:55-75`) compares every widget against `self.settings`, the snapshot
   taken at page build, and never refreshes it — so a second save on the same page reports "Nothing
   changed." while `.env` keeps the first value. Verified in a real browser.

   - Re-read the settings after `save_settings(changed)`: `self.settings = read_settings()`
     (`src/aidm/config.py:157`), imported alongside the existing `save_settings`.
   - `save_settings` (`src/aidm/config.py:165`) returns `None` and reports nothing, so
     `f"Wrote {len(changed)} keys."` (`:75`) is a claim about what was asked, not what landed.
     Replace it with a message carrying no count and no per-key outcome — e.g. "Saved to .env. The
     keys apply at the next start."

   Proof: extend `tests/ui/test_settings.py:54`
   (`a_saved_key_reads_back_and_the_rest_of_the_file_survives`), or add one beside it — two saves
   of two different values on the same form leave `.env` holding the second.

4. **A save that exists but will not restore reads as "no save".** The launcher
   (`src/aidm/ui/app.py:73`) computes `started` from `catalog.saves`, which `_save_option`
   (`src/aidm/app/launch.py:102-134`) has already filtered. So the button says "Start game", and
   `Runtime._open` then refuses on the same file; the refusal page's only control is Home
   (`src/aidm/ui/app.py:164-173`), so the pair is permanently unplayable.

   - `src/aidm/app/launch.py`: `LauncherCatalog.read` already holds `store`
     (`:66`, `:96`). Carry on the catalog, as a new field, the slugs that hit one of the **three
     warning paths** — `:117` (`Refusal` on read or restore), `:121` (scenario or character gone)
     and `:125` (filed under another name). **Exclude the fourth `return None`** (`:110-112`,
     `raw is None`): that means the file vanished between `slugs()` and `read`, and carrying it
     would hide the Start button on a target that would start fine.
   - `src/aidm/ui/app.py`: when the chosen target's slug is in that list, show a line saying a save
     file exists at that slug but cannot be resumed, and **no Start button**.

   Do not delete or migrate anything — `README.md:56` promises neither happens.

   Proof: `tests/app/test_launcher.py` already builds all three cases — `:139`
   (`a_save_filed_under_another_stem_is_not_listed`), `:154`
   (`a_save_whose_origin_is_gone_is_not_listed`), `:163`
   (`a_save_that_fails_to_restore_is_skipped_not_listed`) and `:200`
   (`a_save_that_is_not_utf8_is_skipped_not_raised`). Extend them to assert the slug lands in the
   new field.

   Also touches `src/aidm/ui/app.py` (step 1).

5. **The in-flight refusal leaks another game's save slug.** `IN_FLIGHT`
   (`src/aidm/app/runtime.py:34`) embeds the holder's slug, so a player blocked by a different game
   is shown that game's slug. But `src/aidm/ui/game.py:609` uses the slug to tell "my own turn is
   already running" (suppress the toast — it is the double-click guard) from "another game is busy"
   (show it), so simply dropping the slug silences both.

   `Runtime.admit` (`src/aidm/app/runtime.py:364-373`) has both the caller (`session`) and the
   holder (`self.admitted`). Raise two distinct messages from there — one when
   `self.admitted is session`, one otherwise — neither naming a slug.

   That deletes `_IN_FLIGHT_PREFIX` (`src/aidm/ui/game.py:67`), its `.partition()`, the
   `startswith` at `:592` and the `.format()` at `:609`. `:609` becomes a comparison against the
   own-turn constant; `:592` becomes a membership test against both constants, so `_opened` keeps
   retrying while the gate is held.

   Proof: `tests/ui/test_game.py:260`
   (`this_games_own_in_flight_guard_is_kept_from_the_player`), `:286`
   (`another_games_in_flight_guard_still_reaches_this_player`), `:320`
   (`opened_retries_silently_while_the_gate_is_held_by_another_game`) and `:381`
   (`a_restart_refused_by_this_games_own_gate_still_reaches_the_player`, asserting at `:413`) all
   spell `IN_FLIGHT.format(...)` themselves and change with the constants;
   `tests/app/test_game_service.py:36` and `:453` likewise. Note that `GamePage.restart`
   (`src/aidm/ui/game.py:501-509`) notifies every refusal directly, not through `_run`, so the
   own-turn message must keep reaching the player there while `_run` suppresses it. Add nothing —
   `:286` already pins that the other-game message reaches the player, and asserting it names no
   slug is one more line there.

   Also touches `src/aidm/ui/game.py` (step 2).

6. **Record the transcript rebuild in `IDEAS.md`.** One line, next free number (21), recording and
   not fixing: the game page rebuilds the whole transcript on every turn — `chat()`
   (`src/aidm/ui/game.py:271`) and `journal()` (`:380`) both render from turn 1 — measured at 1,603
   NiceGUI elements and ~172 ms per refresh at turn 160. The fix for it is refused; see "How to
   work" §7.

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```
