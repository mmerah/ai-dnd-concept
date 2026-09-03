# PROGRESS

One entry per phase of `PLAN.md`: the `src` line counts at start and end, decisions made off-plan,
refuted review findings and why, and what is known and accepted.

## Standing decisions

The two decisions that leave with `PROPOSALS.md`, quoted:

- "A base class where we own every implementation; a `Protocol` only where a test double or a
  foreign object must fit without inheriting."
- "The page polls the service; the service never calls the page."

## Phase 1 — the ground

`src` lines: 9,205 at start (`ae6be39`), 9,249 at end after the fold; the target was about 9,190. Tests: 472 to
475. Every golden under `tests/core/fixtures/` unchanged; `prompts/*`, `schemas/*`, `turn/*`,
`rules.md`, `worldsmith.md`, `master_tools.json`, `scenarios/`, `characters/` byte-identical.

What landed: §1.1 mechanical cleanups, §1.2 `Refusal` and `parse`, §1.3 the boundary test over
four engines and one `kill()` per world, §1.4 verbs, one reading verb, one stem per engine,
`engines/core.py` → `engines/base.py`.

### Decisions made off-plan

1. **`type` aliases, §1.1.1: only the four in `config.py`.** Measured on pydantic 2.13.4: a PEP
   695 `TypeAliasType` field is emitted in JSON schema as `$defs/<Alias>` plus a `$ref`, where an
   assigned alias is inlined. `Slug`, `CheckedEntityId`, `TagKind`, `Ability` and `Boost` sit in
   tool-argument models, so converting them changes `schemas/*/master_tools.json`. "How to work"
   rule 9 (`schemas/*` byte-identical throughout) wins; those five stay assigned aliases.
   `ui/settings.py` reads a `TypeAliasType` through as planned (`_unaliased`).
2. **`opening_canon(draft, source, cast_type)` and `build_scenario(..., cast_type)`.** With
   `revalidate_instances="always"` a bare `SceneCanon(...)` revalidates each `Loner3eSheet` cast
   entry as the unbound `C`'s bound, `Person` (`extra="forbid"` refuses `concept`). The canon is
   parametrized at runtime, `SceneCanon[cast_type]`, as `opening_draft` already parametrizes the
   drafts. PLAN §2.2.5 says `opening_canon(draft, source)` "stays a free function": Phase 2's
   engine method has `self.cast` at hand and should pass it.
3. **`parse` prefixes the error's `loc`** (`item: Field required`) when it is non-empty; PLAN
   §1.2.1 spelled `errors()[0]["msg"]` alone. A refusal that names no field is not actionable by
   the master, and the skip log for a stale save would name none.
4. **`core/io.py::_read_text` maps `UnicodeDecodeError` to `Refusal`**, as `decode` maps
   `JSONDecodeError`: a `ValueError` subclass the old `except ValueError` swallowed would
   otherwise escape the narrowed `except Refusal` and empty the home page for one bad file.
5. **Tunnel Goons `create_character` parses its payload** (`parse(TunnelGoonsPayload, {...})`)
   instead of keyword construction: the ability-sum rule lives in the sheet's validator, so a
   legal-per-pick split that does not sum to 3 raised `ValidationError` past the create page's
   narrowed `except Refusal`. Breathless and 24XX keep keyword construction (§1.1.7): their picks
   are fully checked before the payload is built. Breathless narrows `str` to `Skill` with a
   lookup over `SKILLS` (`_skill`) rather than a cast.
6. **Two extra renames by the same rule:** test support `_opened` → `_open_game`, and the
   test-local `FifthScenarioFile` → `FifthScenario` in `tests/core/test_seam.py`.
7. **`tests/core/test_tool_surface.py`: a second game in flight now crashes the call** rather than
   being routed as a refusal. PLAN §1.2.4 keeps `Runtime.playing` a `ValueError` (a bug, not a
   message), and the narrowed catches no longer turn it into a tool result.
8. Two tests that expected `ValidationError` from a boundary that now parses expect `Refusal`
   (`tests/core/test_integrity_boundaries.py::test_a_save_whose_payload_the_engine_rejects_is_refused`,
   `tests/core/test_decisions.py::test_an_option_whose_call_names_no_tool_or_carries_args_it_rejects_is_refused`).
   Every other `pytest.raises(ValueError)` stays (§1.2.6).

### Refuted findings and why

- `app/media.py::Illustrator` and `app/speech.py::Reader` dropped `frozen=True` (Opus review):
  PLAN §1.1.10 says so in those words. Refuted by the plan, not by taste.
- Breathless and 24XX should parse their payload like Tunnel Goons (Opus review): Breathless's
  skill steps exclude earlier picks (`tests/breathless/test_create.py::test_skill_steps_exclude_earlier_picks`),
  so `_three_skills` cannot fire on a checked pick; `TwentyfourxxPayload` has no validator.
  Keyword construction stays where no validator can refuse a checked pick.
- `breathless/creation.py::_skill`'s bare `next()` (Opus review): unreachable after
  `check_picks`, which holds the answer to the six skill ids. A message for an impossible state
  is a comment in code.
- `core/model.py`: drop `SerializeAsAny` from `payload` (Opus cut): payload shapes are Phase 3's
  (§3.4); not touched here.
- `deepcopy` in `tunnelgoons/engine.py::new_game` and `scenes/world.py::new_world` (Fable cut):
  left in place; the copy is cheap and the aliasing it prevents is not covered by a test.
- `app/launch.py::read_catalog`: `files.load(slug)` runs outside the skip `try`, so a non-UTF-8
  save file still takes the home page down. Not a regression of this phase (the old code had the
  same shape) and PLAN §2.7.4 restructures `read_catalog`; left for Phase 2.

### Known and accepted

- The line count is 59 over the plan's estimate: one `Refusal` import per raising module and the
  `parse`, `decode`, `_read_text` and `kill` bodies the estimate did not count. Nothing padded,
  nothing invented.
- A `Refusal` raised inside a pydantic validator is wrapped into a `ValidationError` (PLAN §1.2.4
  accepts this); `ask`'s `except ValidationError` still re-prompts a worldsmith whose draft
  builds an unvalidatable canon.
- Reviews: the implementing session had no `Agent` tool and no `codex`, so it ran the
  `/code-review` skill and `.claude/prompts/review.md` itself; the orchestrator then ran two
  independent `reviewer` agents (Fable and Opus) over the staged diff and folded both. Fixed
  from them: `Game.commit` goes through `parse`; `working()`'s docstring; `Ask` → `Spawn` in
  `app/spawn.py`; `ban-relative-imports = "all"` so `TID252` guards single-dot imports too;
  `build_scenario` called with keyword arguments; one test that a `type`-aliased `Literal`
  field is still a dropdown; the now-unreachable relative-import resolver in
  `tests/core/test_package_boundary.py` deleted.
- `uv run aidm` smoke: the home, settings and both game pages (`whispering-vault`, `amber-tap`)
  serve 200 on the staged tree. No tool call was played end to end (no CLI roles here); the
  refusal and crash paths are covered by `tests/core/test_tool_surface.py`.

## Phase 2 — the engine is the class

`src` lines: 9,249 at start (`4cafaae`), 8,690 at end of the implementation and 8,719 after the fold; the target was about 8,720. Tests: 476 to
476 (one user-packs test deleted with the feature, one non-UTF-8 save test added). Goldens:
`prompts/*`, `schemas/*`, `turn/*` byte-identical; `state/tunnelgoons*.json` and
`save/tunnelgoons.json` changed only in key order (`alive` follows `known` on every goon and
npc). `engines/<id>/` sizes: loner3e 676, tunnelgoons 1,327, breathless 635, twentyfourxx 709,
scenes 1,039. Tool counts unchanged (4, 6, 8, 6).

What landed: §2.1 `Thing`, `Person.line`, `Counter` methods, notes as a list, `Engine.tools` a
dict, `schema_text`, `option_of`/`chosen_option`, one `SRD_PACK`; §2.2 `engines/scenes/tools.py`,
`scenes/worldsmith.py` as the bar and the prompt, `SceneEngine` owning the shared arms,
`next_scene`, `master_sections` with `sheet_sections`/`glossary` hooks, the worldsmith flow and
both views, `SceneWorld.begin`/`join_party`/`leave_party`/`party_rows`/`party_panel`,
`Engine.compose`/`close`, the cached `_prompt`; §2.3–§2.5 every scene engine's resolvers and
creation as methods (`tools(packs)`, `Complications`, `Skills`, `Oracle` gone); §2.6 Tunnel
Goons' world methods and engine methods, `creation.py` gone; §2.7 `NarratorView.spoken` and its
two refusals, `Turn.consume`/`_apply`/`finish`, `str | Answer` gone end to end, `read_catalog`
restoring once inside the skip, `Engine.crossing(pursuit)`, `packs_dir` gone.

### Decisions made off-plan

1. **`opening_canon(draft, source, cast_type)` keeps its third parameter** (Phase 1 note 2): it
   stays a free function in `scenes/worldsmith.py`; `SceneEngine.build_scenario` passes
   `self.cast`. Nothing else knows the cast type at that point.
2. **`SceneEngine.write_next(draft, intent, worldsmith)` and `render_next(draft, intent,
   answer)` take the game, not the world.** PLAN §2.2.5 spells `world`, but `self.guidance(...)`
   reads `draft.packs`, which the world does not carry.
3. **`TunnelGoonsWorld.attach(region: Dungeon, start, *, known)`**, not `attach(draft: MapDraft,
   ...)` (§2.6.1): `MapDraft` lives in `worldsmith.py`, which imports `world.py`; naming it
   there would be a cycle. `attach` copies the region's `ways` lists: with `Dungeon.ways` a
   `list[Way]` (§2.1.3), sharing them let the anchor ways land in the draft too.
4. **A private name that gains a foreign caller loses its underscore.** The plan keeps
   `_AUTHORING`, `_take_loot`, `_roll_loot`, `_LEVEL_OPTIONS`, `_place_lines`, `_ways_lines`,
   `_lines` in their modules while the engine imports them; they are `AUTHORING`, `take_loot`,
   `roll_loot`, `LEVEL_OPTIONS`, `place_lines`, `ways_lines`, `lines_of`. `roll_loot` sits in
   `breathless/tools.py` beside `take_loot`, as §2.3.2 places it.
5. **`engines/tunnelgoons/creation.py` deleted**: §2.6.2 makes its three functions engine
   methods and §2.6.3 does not list it among the kept modules; `STARTING_ITEM_LIST` and
   `POINT_OPTIONS` moved to `engine.py`.
6. **`base.pack_options` inlined onto `SceneEngine.pack_options()`**: a one-line function whose
   one real caller was that method, and the only remaining hit of the `packs: Mapping` grep.
7. **`app/spawn.py`: the `Spawn` alias is the one deleted** (§2.7.3 names `Ask`, which Phase 1
   had already renamed to `Spawn`); `ask`'s spawn parameter is spelled inline.
8. **`FileStore.load` reads through `_read_text`**, so a save file that is not UTF-8 reaches
   `read_catalog` as a `Refusal` and is skipped with the log line (Phase 1's open note).
9. **`read_catalog` skips a save whose engine is gone with its own log line** rather than
   raising a `Refusal` to its own `except`.
10. **`Loner3eEngine` narrows through `draft.payload`** where it needs `Loner3eWorld.twist`;
    `SceneEngine.world(state)` returns the bound `SceneWorld[C, P]`.
11. **`Specialty` and `Origin` no longer redeclare `detail`**: as `DecisionOption` subclasses
    they inherit it with its `""` default (basedpyright refuses a required override); the packs
    supply it.
12. **`tests/core/test_tool_surface.py::_SilentEngine.crossing`** returns `None` under a pyright
    ignore: the double is a Loner engine that grows without a crossing, which is the test's point.
13. `NEXT-SPECS.md:133` says `Engine.over` where it said `player_over` (rule 10).

### Refuted findings and why

- `tunnelgoons/views.py::place_lines`/`ways_lines` should be `TunnelGoonsWorld` methods and the
  module deleted (Opus review): PLAN's Phase 2 done-when keeps `tunnelgoons/views.py` as the one
  remaining views module. Left for the plan's own sweep.
- `Loner3eEngine.change_world` should go through `self.world(draft)` (Opus review):
  `apply_change` is typed on `Loner3eWorld` (`loner3e/engine.py:193`), which `self.world`'s
  `SceneWorld[C, P]` is not; the comment on `SceneEngine.world` no longer claims to be the one
  narrowing.
- `attach`'s `start` parameter and moving `MapDraft` into `world.py` (Opus cut): a module move
  the plan does not ask for; left.
- `preview_character` narrowing (both reviews) was a real defect, not refuted: each scene
  engine's `_own(character)` narrows once and the payload is read off the narrowed file.

### Known and accepted

- The line count is 1 under the plan's estimate. Nothing padded, nothing invented.
- `Thing.label` and `Counter.change` compare against the `PLAYER_ID` constant, as §2.1.1 says;
  every engine files the player under it.
- `SceneEngine.__init__` reads `worldsmith.md` once per engine instance (three at start), where
  the module constant read it once at import.
- Reviews: the implementing session had no `Agent` tool and no `codex`; it ran
  `.claude/prompts/review.md` over the staged diff itself (`/tmp/phase-2/review-self.md`) and
  fixed three defects from it (`read_catalog`'s raise-to-catch, `attach`'s aliased lists,
  24XX `preview_character` reading the payload before the type check). The orchestrator then
  ran two independent `reviewer` agents (Fable and Opus) and folded both. Fixed from them:
  `_own` narrowing in the three scene engines' `preview_character`; 24XX `Pack` refuses a
  specialty or origin with no `detail` (a `model_validator`, since basedpyright refuses a
  required override of `DecisionOption.detail`); the 24XX weapon pick refuses instead of a bare
  `next()`; `SceneEngine.crossing` typed `str | None` like its base, so the test double needs
  no pyright ignore; `reload_settings` no longer rebuilds engines that read no setting;
  `FileStore.load` checks `is_file()` once; `roll_loot` reads the player off the draft;
  `NEXT-SPECS.md` says `AUTHORING`; one test that `compose` builds the accepted answer once.
- **Unmet done-when:** PLAN's Phase 2 asks `uv run aidm` to play a turn on every engine, write
  and install a Loner scene, and take and report a Tunnel Goons job. This machine has no CLI
  roles, so only the pages were smoked: `/`, `/settings`, `/create`, `/scenario` and the four
  game pages (`whispering-vault`, `amber-tap`, `buried-bell`, `salt-lantern`) serve 200. The
  turn, the option answer and the crossing are covered by `tests/core/test_pipeline.py`,
  `test_decisions.py` and `test_tool_surface.py`; the live play is still owed.
