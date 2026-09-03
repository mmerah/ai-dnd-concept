# PROPOSALS — conceptual simplification and consistency

Input: six independent full reads of `src/aidm` (9,205 lines) and `tests/` (8,236 lines) on
2026-09-03: five Fable subagents (A–E, E briefed as the contrarian) and the lead. Every reviewer
inventoried the concepts, judged each one, and critiqued the "pure functions" rule in CLAUDE.md.
This file merges them. Votes are out of 6. Line counts are estimates. Nothing here is decided.

**Decisions this file needs from the maintainer are in section 5. Read that first.**

Headline, agreed by all six: the architecture is right and the concepts are right-sized. Of
about 44 concepts, none should be removed outright and four merge. The weight is in *form*: the
engines were written as modules of free functions with a forwarding class on top, state is
threaded through 5–8 parameters that all belong to one object, and the purity rule produced a
dialect (tuple returns assigned back, rebuilt tuples, participle names, carrier dataclasses that
exist to give a function a `self`). Fixing form removes roughly 500–650 source lines and most of
the ceremony. Verified along the way: one real bug and one behavioural inconsistency (section 0).

---

## 0. Verified facts (checked by the lead, not opinions)

1. **`tests/core/test_package_boundary.py:7` lists three engines; `twentyfourxx` is missing.**
   A `loner3e -> twentyfourxx` import would pass today. Bug. (D)
2. **Tunnel Goons has two death paths.** `tools.py:328 _kill` drops the npc's items loose;
   `tools.py:209-214 action_roll` slays an npc with `alive = False` and drops nothing. A monster
   killed by the dice keeps its loot on the corpse. 24XX `attempt` likewise kills the player
   bypassing `SceneWorld.kill()`. (B)
3. **175 `raise ValueError`, 15 broad `except ValueError`/`except (OSError, ValueError)` sites.**
   `mcp.py:64` returns any `ValueError` to the model as a refusal to retry, so a resolver bug
   (a stray `int()` or `list.index`) reads as a rules refusal. (B, C, D, E, lead)
4. **`Game[LonerWorld]` is a real class at runtime** (`isinstance(Game[LonerWorld], type)` is
   True, `__name__ == "Game[LonerWorld]"`), so the twelve empty `XGame/XScenarioFile/
   XCharacterFile` subclasses can be aliases as far as `isinstance` goes. basedpyright's view of
   `game: type[G]` assigned from an alias is unverified. (A, B, D for; E against)
5. **`type X = Literal[...]` breaks `ui/settings.py:87`**: `get_origin` of a PEP 695 alias is
   `None`; `get_origin(X.__value__)` is `Literal`. Converting `config.py:9-13` needs that one-line
   change in the settings page, or those four stay as assignments. (E)
6. **`ConfigDict(revalidate_instances="always")` + `model_validate(instance)` raises on a
   mutated invalid instance**, so `Game.committed()` can drop its JSON round trip. (C)
7. **`ui/game.py:244-268`: four `bind_*_from(session, "phase", backward=...)` lambdas call
   `session.player_view()` on NiceGUI's 0.1 s binding loop**, rebuilding every panel ~30–40
   times per second per open tab while idle. (C, D)
8. Counts: `one` as an identifier 509 times; 16 `_ =` discards under
   `reportUnusedCallResult = false`; 17 relative imports against CLAUDE.md's own rule.

---

## 1. Inventory: every concept, one line, consensus verdict

Verdicts: **keep** (as is), **reshape** (same concept, different spelling), **merge** (into
another concept). No concept got **remove** from a majority.

| # | Concept | Lives in | Verdict | Notes |
|---|---------|----------|---------|-------|
| 1 | Three roles (master / narrator / worldsmith) | `config.py:11`, `app/spawn.py`, prompts | keep 6/6 | The product. NEXT-SPECS already refused a fourth. |
| 2 | Spawner / Driver (claude, codex) / `answered` one-retry | `app/spawn.py` | keep 6/6 | `ScriptedSpawner` is the whole offline test strategy. Only wart: `DRIVERS` after the classes. |
| 3 | `WorldsmithAnswer` Protocol, `_Worldsmith`, `authored` | `core/model.py:68`, `runtime.py:51`, `seam.py:115` | keep, trim | Protocol needed (engines cannot import `app`). `_Worldsmith` is a `partial`; `Ask` alias and `TurnStep` (= `Role`) go. (C, D) |
| 4 | Transactional draft (`draft()`/`committed()`, per-call candidate + rng fork) | `core/model.py:94`, `turn/run.py:196` | keep 6/6 | E: the per-call candidate is protected by three named tests; do not "validate once at the end". C: drop the JSON round trip via fact 0.6. |
| 5 | `Turn` (picture, call gate, finish) + `consume_answer`, `close_segment`, `_apply` | `turn/run.py` | reshape 6/6 | Methods spelled as functions. See P7. |
| 6 | Typed proposals: `Narration`; five scene drafts; `MapDraft`/`ReturnDraft` | `core/play.py:30`, `scenes/drafts.py`, `tunnelgoons/worldsmith.py:53` | keep 6/6 | Flat draft was refused in NEXT-SPECS; all six agree. |
| 7 | `MasterTool` / `master_tool()` / `schema_of` / `NoArgs` | `core/tools.py` | keep | The description check at `tools.py:34` is a real gate. Add `schema_text()` (5 copies of `json.dumps(schema_of(...))`). `tools` as a dict (two linear lookups). |
| 8 | `change_world` union + `apply_change` match + wrappers, per engine | each `engines/*/tools.py` | reshape 6/6 | Union and schema stay per engine; dispatch scaffolding is copy-paste ×4. See P2. |
| 9 | Facts (`Fact`, `DiceEvent`, `told`, `card`, `trace`, `cards()`, `traced()`) | `core/facts.py` | keep 6/6 | `kind: str` stays free. D: `card` could be a tuple of lines instead of `"\n"`-joined. |
| 10 | Told/hidden gate (`known`, `entity_fact`, `reveal`, `labeled`) | `engines/core.py:181-212` | keep the gate, drop `player_id` threading | Every player is `PLAYER_ID`; 8 call sites and 4 forwarders pass it anyway. Caveat Track G.2. (A, B, D) |
| 11 | `NarratorView` / `PlayerView` / `Panel` / `PanelRow` / `Subject` / `Speaker` / `Rows` | `core/views.py` | keep | E: `NarratorView`'s six fields are pinned by test; never merge it with `PlayerView`. Small: `Subject.speaker()` replaces `speaker_of`, `_subject_of`, `subject_of`. `Rows` does three jobs; name the prompt one `Sections`. |
| 12 | Pending decisions (`PendingDecision`, `PendingOption`, `Answer`, `Engine.answer`) | `core/play.py:39`, `seam.py:61` | keep 6/6 | B, D: drop the `str \| Answer` union; always pass `Answer`. |
| 13 | Notes from the rules (`Game.notes`) | `core/model.py:86`, `run.py:48` | reshape | A tuple rebuilt at 8–9 sites; a `list` with `Game.note()`. (A, B, C, D) |
| 14 | Exchange / Line / SpokenLine / Speaker / SceneRecord / `render_history` | `core/play.py`, `core/views.py:62` | keep 6/6 | `SceneRecord` is the one shape both worlds render through. |
| 15 | Engine seam (`Engine` ABC, 16–17 abstract methods) | `engines/seam.py` | keep, trim | `history()` derivable from `scenes()`; `preview_character` and `new_game`'s isinstance preludes default on the seam; `close` as a concrete method. |
| 16 | `SceneEngine[C, P, G, K]` | `engines/scenes/engine.py` | keep, give it more | Owns the lifecycle but not the three things its subclasses copy (P2, P3, worldsmith flow). Four type params stay (E, lead). |
| 17 | Scene world (`SceneRun`, `SceneCanon`, `SceneWorld`) | `engines/scenes/world.py:77-405` | keep 6/6 | The best-written code in the tree; the model for the rest. C, D: move the bar and prompt rendering out so `world.py` drops from 663 to ~450. |
| 18 | Scene bar (`scene_unmet`, `cast_unmet`, `hub_unmet`) | `scenes/world.py:517-616` | keep 6/6 | Accumulate-then-refuse is the documented design. Signatures with 5–6 params shrink once it is a method. |
| 19 | Scene worldsmith flow (`write_next`, `install_scene`, `render_opening`, `build_scenario`) | `scenes/worldsmith.py` | merge into `SceneEngine` 6/6 | Every keyword param (`cast_type`, `guidance`, `finished_note`, `hub_phrase`) is a `SceneEngine` attribute. `install_scene` mutates `world.board` from outside the world. |
| 20 | Hub / campaign (`Offer`, `Board`, `Job`, ledger, briefs, `check_*`, panels) | `engines/hub.py` (210) | reshape 6/6 | 16 free functions over `(hub, board, jobs)`; both worlds carry the three fields and re-wrap. See P4 and decision D1. |
| 21 | Party (`JoinParty`/`LeaveParty`, `join_party`, `check_party`, panels) | `engines/core.py:56-131` | keep, move onto the world | Helpers take a bare list because Tunnel Goons has no party yet; that is building for Track G. (A, C, D) E: leave, G is dated. |
| 22 | Cast: `Person`, `Entity` Protocol; TG `Goon/Npc/Item/Place` | `engines/core.py:21`, `tunnelgoons/world.py:32-95` | reshape 6/6 | `Entity` Protocol exists only because TG retypes `id/name/brief/known` four times. A `Thing(Mutable)` base. See P6. |
| 23 | `Counter` + `pool`/`adjust`/`counter_fact`/`_shortfall` | `engines/core.py:70-172` | reshape 6/6 | Three free functions over a two-field model, beside `Item.broken` as a property. The clearest purity artefact. |
| 24 | Packs (`Pack`, `load_packs`, `pack_options`, per-engine `Pack`, `packs_dir`) | `engines/core.py:50,226`, `engines/*/creation.py` | keep; stop threading | `packs` passed into ~20 signatures the engine already owns on `self`. A, C: drop the unused `packs_dir` setting (no `packs/` exists). `SRD_PACK` declared twice. |
| 25 | Scenarios (`Scenario[P]`, `ScenarioMeta`, per-engine `*ScenarioFile`) | `core/model.py:16-55` | keep | `art_style`/`voice` set via `model_copy(update=)` on a `Frozen` model skips validation; pass them into `build_scenario`. (C) |
| 26 | Characters: `Character[P]`, four file payloads, four `player_*` builders | `core/model.py:58`, `engines/*/world.py` | reshape | Four names for one hook (`player_of`); envelope built four times with `EngineId("...")` literals. Whether the payload becomes the sheet type is decision D3. |
| 27 | Creation flow (`CreationStep`, `Picks`, `check_picks`, per-engine steps) | `core/creation.py`, `engines/*/creation.py` | keep | Option lookup written three ways (`find_entry`, `_by_key`/`_require`, inline `next`); one `option_of` in core. |
| 28 | Source documents (premise + md/txt/pdf) | `core/source.py` | keep 6/6 | 49 lines, one purpose. |
| 29 | Saves (`FileStore`, atomic write, `decoded`, `SaveHeader`, `restored`) | `core/io.py`, `seam.py:53` | keep | C: `load_catalog` parses `SaveHeader` then `restored()` parses the whole save again; one parse. |
| 30 | Twelve empty `XGame`/`XScenarioFile`/`XCharacterFile` subclasses | `engines/*/world.py` | contested | A, B, D: aliases. E: keep. Fact 0.4 settles the runtime half; pyright unverified. Decision D5. |
| 31 | Registry (`build_engines`, `begin_game`) | `engines/registry.py` | keep 6/6 | Only file allowed to name concrete engines. Two constructor shapes (`packs_dir` vs none). |
| 32 | `GameService` / `Runtime` | `app/runtime.py` | keep 6/6 | E: `Runtime.playing()` and the three-object split are test-protected. Trim forwarders (`scene()`, `transition_available()`). `crossing: str \| None` doubling as a behaviour switch (C, D). |
| 33 | Launch catalog (`CatalogEntry`, `LaunchTarget`, `SaveOption`) | `app/launch.py` | keep | Pydantic for in-process view objects; dataclasses fit (C, D, E). `ui/create.py:208` rebuilds the whole catalog to make a two-field `LaunchTarget` (C). |
| 34 | Settings (pydantic-settings, `.env`, reflection page) | `config.py`, `ui/settings.py` | keep 6/6 | Reflection page means unused knobs are free. `for_name` `match` blocks stay (exhaustive under pyright). |
| 35 | Media / `Illustrator`, Speech / `Reader` | `app/media.py`, `app/speech.py` | keep | Both `frozen=True` dataclasses carrying a mutable `generating: set`. Un-freeze. (B, C, D, E) |
| 36 | MCP endpoint | `app/mcp.py` | keep 6/6 | 78 lines, one lock, one gate. |
| 37 | UI pages, `GameView`, refreshables, theme | `ui/*.py` | reshape | `GameView` dataclass + 14–20 module functions taking `view`; module-level refreshables share one target list across all clients; binding storm (fact 0.7). A `GamePage` class. (A, B, C, D) |
| 38 | Ids (`Slug`, `EntityId`, `CheckedEntityId`, `EngineId`) | `core/entities.py` | keep | The `NewType`-over-`Annotated` comment explains a real pydantic limit. Place is `Slug` in scenes and `EntityId` in TG (A). |
| 39 | `Frozen` / `Mutable` bases | `core/entities.py:18-27` | keep | E: add `Loose` (`extra="ignore"`) for the six foreign-shape models. Four character payloads are `Mutable` inside a `Frozen` envelope (D). `MapDraft` refreezes a `Mutable` by hand. |
| 40 | Tunnel Goons map (`Dungeon`, `MapCanon`, `TunnelWorld`, `frontier`/`walk`/`has_shortcut`, map bars) | `tunnelgoons/world.py`, `worldsmith.py` | keep | Under the cap at 1,429. World mutations live in `tools.py` free functions while `SceneWorld` owns its own; standardize on methods. Graph helpers are `Dungeon` methods. |
| 41 | Golden tests + `ScriptedSpawner` + `Table` | `tests/core/golden_*`, `core_test_support.py` | keep | The safety net every proposal depends on. D alone proposes trimming the `state/` and `save/` fixtures (~2,000 lines). Decision D4. |
| 42 | Boundary tests (`test_package_boundary`, `test_integrity_boundaries`, `test_crossing_integrity`, `test_context_boundary`) | `tests/core/` | keep, fix | Fact 0.1. D: replace the AST test with `import-linter`. Decision D7. |
| 43 | Test support modules (`*_test_support.py`, six `pythonpath` entries) | `tests/*/` | reshape | `changed/refused` defined three times; `hub_world/small_world` near-copies; two import roots. A `tests/support` package. (B, C, D, E) |
| 44 | Prompt text in `.md` files and ~25 string constants | `turn/prompts`, `engines/**/*.md`, `hub.py`, etc. | keep | Prompt files read at import time in three modules vs in `Engine.__init__` for `rules.md`. Pick init-time. (A, B, C, lead) |

---

## 2. Simplification proposals, ranked by value / risk

Each entry: what, where, votes, lines, risk, what is lost.

### P1. The engine class is the engine (6/6)

Move `creation_steps`, `create_character`, `preview_character`, `guidance`, `master_sections`
and the tool resolvers from `engines/*/{creation,tools,views}.py` onto the engine class. Delete
the 31 one-line forwarders in the four `engine.py` files, the `Oracle` / `Complications` /
`Skills` dataclasses (`loner3e/tools.py:118`, `breathless/tools.py:105`,
`twentyfourxx/tools.py:128`) whose only field is the `packs` the engine already holds, the
`packs: Mapping[str, Pack]` first parameter on ~20 signatures, and the `EngineId("loner3e")`
literals (`self.id`). Files may stay split if one gets long; the 2,000-line rule is per engine.

- Lines: ~150–250. Risk: low; mechanical; prompts and schemas do not change so goldens hold.
  Tests that build `Skills(PACKS)` or call `tools(packs)` build the engine instead.
- Lost: nothing. E: "what the purity rule protected survives: resolvers still mutate only the
  draft they are handed and roll only the `Random` they are handed."
- Start with Breathless (smallest).

### P2. Shared `change_world` arms, `next_scene` and the envelope written once (6/6)

`Reveal/Enter/Leave/Kill` are matched identically in three engines
(`loner3e/tools.py:175-194`, `breathless/tools.py:140-152`, `twentyfourxx/tools.py:239-259`);
`ChangeWorld`, `change_world` and `next_scene` wrappers are copied ×4/×3. Two shapes proposed:

- **(a) Double dispatch**: each arm gets `apply(self, world) -> list[Fact]`; `apply_change`
  becomes `change.apply(world)`; the match blocks vanish. (B, D)
- **(b) Base handles shared arms**: `SceneEngine.change_world` matches the four shared arms and
  calls an abstract `own_change(world, change)` for the rest. (A, C, E)

Either way the per-engine `WorldChange` union and schema stay (the tool count and
`master_tools.json` are per engine). Lines: ~70–80. Risk: low (pyright generics on the arm's
world type for (a)). Lost: nothing. Lead's preference: (b), because it keeps arg models as
plain schemas with no behaviour, which is how every other proposal model in the tree works.

### P3. `master_sections` once on `SceneEngine` with a `sheet_sections()` hook (5/6)

`loner3e/views.py`, `breathless/views.py`, `twentyfourxx/views.py` are the same eight-row
skeleton with one engine row spliced in (tag glossary / BACKPACK / GEAR) and the same
`master_tail(world.hub, world.at_hub, world.board, world.closed_jobs(), world.open_job())`
incantation. Lines: ~45–60; three modules gone. Risk: nil if row order is kept (golden
`master.txt` stays byte-identical). Lost: an engine can no longer reorder shared rows (none does).

### P4. One object for the campaign (6/6 on the problem; shape contested, decision D1)

`hub.py` is 16 free functions over `(hub, board, jobs)`; `hub_sections` takes seven arguments,
`master_tail` five; both worlds declare the three fields (`scenes/world.py:129-131`,
`tunnelgoons/world.py:193-195`), are policed by three external `check_*` functions, and re-wrap
`open_job/closed_jobs/since_start` as methods; 15–17 `hub is None` guards. Shapes proposed:

- **(a) Sub-model** `Campaign(Mutable)` / `Hub(Mutable)` with `place, board, jobs` and methods
  (`open_job`, `closed_jobs`, `ledger`, `sections`, `tail`, `panels`, `check(walked)`), held as
  `world.campaign: Campaign | None`. "A board with no hub" becomes unrepresentable. (A, B, C, E)
- **(b) `World` base class** in `engines/core.py` with `player, hub, board, jobs, source` and
  the methods; `SceneWorld(World)`, `TunnelWorld(World)`. Also absorbs the party helpers and
  makes `Engine.over/record/history/scenes` concrete. (D, lead)

Both change the save and scenario JSON shape (allowed by design; eight shipped `world.json`
files and all state/save goldens regenerate). Lines: ~60–90 source, ~60 test. Risk: medium.
Lost: existing saves. Do it in one commit, paired with P9's dict-shaped tags so saves go stale
once (E).

### P5. Un-thread the state: methods on the owner (6/6)

- `Counter.adjust()`, `Counter.shortfall`, `Counter.__str__`/`shown()` replace `pool`, `adjust`,
  `_shortfall` (`engines/core.py:152-161`, `loner3e/tools.py:358`).
- `labeled(entity)` / `reveal(entity)` compare to `PLAYER_ID`; drop the `player_id` parameter
  and the four `label/reveal` forwarders on both worlds. Revisit at Track G.2. (A, B, D)
- `Game.notes: list[str]` with `note()`; `Operator.hindrances` as a list; no `(*x, y)` rebuilds.
- `join/leave_party` onto `SceneWorld`.
- Tunnel Goons: `move`, `unlock_way`, `_reveal`, `_move_item`, `_kill`, `attach` become
  `TunnelWorld` methods, matching `SceneWorld.enter/leave/kill`; one `kill()` per world called
  by every death path (fixes fact 0.2). `frontier/walk/has_shortcut` onto `Dungeon`.

Lines: ~40–60. Risk: low. Lost: nothing.

### P6. `Thing` base class replaces the `Entity` Protocol (6/6)

`Thing(Mutable)` with `id, name, brief, known`; `Person(Thing)` adds `alive`; TG's `Goon`,
`Npc`, `Item`, `Place` subclass it (or `Goon(Person)`, `Npc(Person)` per B). Deletes the
Protocol, its property-vs-attribute dance, the `check_filing[E: Entity]` generic and 12–16 field
lines; `labeled/entity_fact/reveal/subject()` can become methods. Lines: ~15–25. Risk: nil.

### P7. `Turn` and `GameService` own their operations (6/6)

`consume_answer(turn, ...) -> tuple[str, str]` assigned back onto `turn` (`run.py:46`) and
`_apply(turn, play)` become `Turn.consume()` / `Turn._apply()` (a test imports `_apply` with a
pyright suppression). `close_segment(engine, view, draft, prompt, lines, facts)` — six params,
callers compute `view` first four times — becomes `Engine.close(draft, prompt, lines, facts)`
(A) or `GameService.file(...)` (C, D). `speakers_refusal`/`_spoken` onto `NarratorView`.
Lines: ~20–30. Risk: low.

### P8. Pipeline tidy-ups (C, plus overlaps)

- `Engine.tools` as `dict[str, MasterTool]`; drop the two linear lookups (`seam.py:62`,
  `run.py:65`). Default `history()` from `scenes()`.
- `committed()` without the JSON round trip (fact 0.6).
- Game creation builds the opening state twice and runs the bar twice (`authored` calls
  `build` twice; `playable` then `_begun`); `ui/create.py:208` rebuilds the catalog for a
  `LaunchTarget`; `load_catalog` parses each save twice (`SaveHeader` then `restored`).
- `_Worldsmith` → `partial`; drop `Ask` and `TurnStep`.
- `option_of` in `core/creation.py`; `schema_text()` beside `schema_of`; `SRD_PACK` once.

Lines: ~60. Risk: low. Lost: nothing.

### P9. Dict-shaped enumerated fields (B, C, D, E)

`tags_of`/`set_tags` (`loner3e/world.py:101-122`, two four-way matches), `Goon.ability`
(`tunnelgoons/world.py:48`), the `level_up` match (`tunnelgoons/tools.py:248`): a `Literal` that
selects a field is a dict field (`tags: dict[TagKind, list[str]]`, `abilities: dict[Ability,
int]`), as Breathless's `skills: dict[Skill, Die]` already does. Changes the Loner and TG
character/scenario shape. Pair with P4.

### P10. Character payload becomes the sheet type (contested, decision D3)

Every engine has a file payload (`Loner3eCharacter`, ...) and an in-world sheet
(`LonerCharacter`, ...) plus a `player_*` copier. D: make the payload the sheet for all four
(~85 lines, character-file format change). B: only Loner collapses cleanly, plus 24XX's `Kit`
→ `Item`. E: keep the split, it is honest for three of four. Lead: Loner and TG collapse; the
other two keep a small hook.

### Below the line (one or two votes each)

Drop `packs_dir` (A, C). `Generator` base for media/speech (A). `Library` class for content IO
(A). Trim goldens (D, decision D4). `import-linter` (D, decision D7). `Answer` only, no
`str | Answer` (B, D). `Fact.card` as a tuple of lines (D). `Engine.crossing` → a named method
(C, D).

### Not proposed, on purpose (E's list, endorsed)

`NarratorView` as its own type; the per-call candidate in `Turn._apply`; the five-class draft
hierarchy; `Driver`/`Spawner`; `Runtime`/`GameService`/`Turn` as three objects; the per-engine
`WorldChange` union; folding `_drop_item`/`test_luck`/`outcome` across Breathless and 24XX
("no fold for the count's sake").

---

## 3. Consistency proposals, ranked

### C1. One exception for what a model or player reads (5/6; A differs, decision D2)

`class Refusal(ValueError)` in `core`. Rules, bars, `Engine.validate`, `consume_answer` raise
it; `mcp.py:64`, `runtime.py:181/210/224`, `authored`, `ui.working` catch only it. A plain
`ValueError` then means a bug and surfaces as one. `_apply`'s `ValidationError` → first-message
translation becomes `Refusal`. This is the one item with a correctness edge (fact 0.3).

A goes the other way: drop the `-> str | None` refusal functions and raise everywhere, letting
`answered()` catch. E's counter: the `*_unmet` list-builders are the documented "one retry sees
every refusal" design and must keep returning lists. Both agree on one convention.

### C2. Methods on the owner (6/6)

The purity rule's fingerprint. Full list in section 4. Beyond P5/P7: `install_scene` writing
`world.board`/`state.notes` from outside while `apply_scene` writes inside; `move()` setting
`job.started` outside while `settle()` sets `job.finished` inside; `scene_unmet` fanning
`held/everyone/followers` into six-parameter helpers; `entity_line` existing twice with
different signatures (`scenes/world.py:644`, `tunnelgoons/views.py:116`).

### C3. Naming (A, C, D, lead)

- **Register**: `one` (509×), `held`, `said`, `told`, `landed`, `written`, `came` as variable
  names; docstrings written as aphorisms ("A value nothing owns"). Nouns for values (`entity`,
  `member`, `item`, `reply`), docstrings that state the contract. (A, lead)
- **Participles for actions**: `restored`, `committed`, `answered`, `authored`, `decoded`,
  `offered`, `_spawned`, and test helpers `opened/played`. `await answered(...)` spawns a
  process twice. Verbs for methods that act (`restore`, `commit`, `ask`, `decode`);
  adjectives for properties (`busy`, `broken`, which the repo already does right). (C, D)
- **One stem per engine**: `Loner3eEngine`/`Loner3eGame`/`Loner3eCharacter` vs
  `LonerCharacter`/`LonerWorld`; `TunnelGoonsEngine` vs `TunnelWorld`; `*File` suffix on
  scenario and character but not game. `<Stem>Engine/World/Game/Scenario/Character/Sheet`;
  a role noun only for the played entity. (A, C, D)
- **One name per act**: `ready`/`way_open`/`transition_available`; `new_game`/`new_state`/
  `new_world`/`begin_game`/`_begun`; `tools()`/`master_tools()`; `read_*`/`load_*`. (B, C)
- `player_character/player_survivor/player_operator/player_goon` → one hook `player_of`.
- `aidm.core` vs `aidm.engines.core`: rename the latter `engines/base.py`. (D)

### C4. Mechanical, one PR, zero risk (all)

- `type X = ...` for every alias; keep `config.py:9-13` as assignments or change
  `ui/settings.py:87` to read `__value__` (fact 0.5).
- Delete 16 `_ =` discards (`reportUnusedCallResult` is already off).
- 17 relative imports → absolute (CLAUDE.md already says so; ruff `TID252` enforces).
- `_arg` prefix for unused params, not `del ctx` (`mcp.py:51,55`).
- `JsonValue` instead of `dict[str, object]` (`media.py:104,169`, `speech.py:109`).
- `list[Fact]` inside resolvers, tuples only on the seam (mixed inside one module today).
- Keyword construction in-process; `model_validate(dict)` only at a boundary
  (`breathless/creation.py:75`, `twentyfourxx/creation.py:143`, `tunnelgoons/worldsmith.py:90`).

### C5. Pydantic vs dataclass vs plain class (all; rule is real but unwritten)

Pydantic for what crosses a boundary (files, settings, model answers, tool args, saves);
`@dataclass` for records; a plain class with `__init__` for a thing that owns behaviour or a
resource (`GameService` uses `field(init=False)` + `__post_init__` IO; `GameView` is a bag of
widget handles). `frozen=True` only when every field is immutable (`Illustrator`, `Reader`).
`launch.py`'s four models → dataclasses. `Outcome` → `Frozen`. A `Loose` base for the six
`extra="ignore"` foreign shapes (E). `Survivor._filled_out` is a validator that mutates;
defaults instead (C). Character payloads `Mutable` inside a `Frozen` envelope (D).

### C6. Protocol vs ABC (all agree; write it down)

ABC / base class when we own every implementation and share code (`Engine`, `Entity` → `Thing`);
Protocol where a test double or foreign object must fit (`Spawner`, `Driver`,
`WorldsmithAnswer`, `Box`).

### C7. Where things live

- Prompt `.md` files read at import time (`scenes/world.py:44`, `tunnelgoons/worldsmith.py:38`,
  `turn/context.py:20`) vs in `Engine.__init__` for `rules.md`. Init-time, by the class that
  uses them. (A, B, C, lead)
- Rendering and the bar out of `scenes/world.py` into `scenes/worldsmith.py`, as Tunnel Goons
  already does; tool arg models (`Reveal/Enter/Leave/Kill/NextScene`) into a `scenes/tools.py`.
  (C, D)
- `DRIVERS` after the classes is fine; say "a constant built from a class follows it" in the
  layout rule instead of apologising in a comment.

### C8. UI as small classes (A, B, C, D)

`GamePage` with method refreshables (per-instance targets, fixes the cross-client
`refresh_all`), `_can_type` computed once in `poll_turn` instead of four `bind_*_from` lambdas
(fact 0.7), `CharacterForm`/`SettingsForm` instead of `nonlocal` closures and a threaded
`boxes` dict. Zero behaviour change; the `nicegui-development` skill calls this a controller.

### C9. Tests (B, C, D, E)

`tests/support/` package (or `tests` as a package) instead of six `pythonpath`/`extraPaths`
entries; one engine-agnostic `apply(engine, draft, verb, **fields)` through `engine.tools`
replacing three copies of `changed/refused`; `core_test_support` is Loner-flavoured (`opened`,
`with_entity`, `loner_sheet`), name it so; pin seeds instead of five 200-seed hunts; file names
by subject (`test_pipeline`, `test_tool_surface`, `test_decisions`, `test_session`,
`test_crossing_integrity` are all "a scripted turn through `GameService`"). Fix fact 0.1.

---

## 4. CLAUDE.md `## Code` section: the purity rule and its replacement

### What the rule did

"Write pure functions. Put side effects at the edges" and "a method that writes nothing
outside its arguments is pure" contradict each other (the second permits mutating the
argument, so the first forbids nothing), and the code shows which won. Six reviewers found the
same residue independently:

| Pattern | Examples |
|---|---|
| Methods spelled as `f(obj, ...)` | `consume_answer(turn, ...)`, `_apply(turn, ...)`, `adjust(counter, n)`, `join_party(party, one)`, `attach(world, draft)`, `install_scene(state, ...)`, `_change_tags(world, one, change)`, 14–20 `f(view, ...)` in `ui/game.py` |
| Carrier classes that give a function a `self` | `Oracle`, `Complications`, `Skills` |
| State threaded as parameters the receiver already holds | `packs` (~20 signatures), `player_id` (8 sites + 4 forwarders), `hub_sections` (7 params), `close_segment` (6), `cast_type/guidance/finished_note/hub_phrase` in `scenes/worldsmith.py` |
| Tuple returns assigned back | `turn.prompt, turn.action = consume_answer(turn, ...)`; `_pair` (5-tuple); `keep_highest` (3); `_here_and_way` (3); `_absorbed` |
| Immutable collections used as mutable | `draft.notes = (*draft.notes, x)` ×8; `hindrances` ×3; `set_tags`; `_append_way` |
| Getter/setter pairs dispatching on a Literal | `tags_of`/`set_tags`, `Goon.ability` |
| Expression tricks to avoid a statement | `*((x,) if cond else ())` ×6; 0-or-1 tuple panels; nested conditional expression at `scenes/worldsmith.py:64-70` |
| Participle names for effectful calls | `restored`, `committed`, `answered`, `authored`, `decoded`, `offered` |
| Engines as function bags behind a forwarding class | every `engines/*/engine.py` |

Where argument passing is right and must stay (all six): `roll(faces, reason, rng)` and every
resolver taking `(draft, args, rng)`, so a trial run cannot consume the turn's dice; `Game.draft()`
/ `committed()`; prompt renderers taking a view, never the state; `scene_unmet(draft, world)`
as a predicate; `Fact` and every proposal staying `Frozen`; small pure helpers over scalars
(`stepped`, `raised`, `slug`, `outcome_for`).

### Proposed replacement (merged from the six drafts)

```markdown
## Code

- Ordinary object-oriented Python. A class owns its state and the methods that read, check and
  change it. A function whose first argument is one of our objects, and which reads or mutates
  it, is a method: write it as one. A module holds free functions only for what has no owner
  (a dice helper over ints, a slug over strings, a renderer over a view).
- An engine is one class. Its tools, creation steps, prompt sections and rules are methods on
  it; its packs, prompts and types are read from `self`, never passed in. Helpers two engines
  share live in `engines/core.py` or `engines/scenes/`.
- Pass the object, not its fields. Return one thing: two related results are a small frozen
  class, not a tuple; a tuple returned so the caller can write it onto an object is a method
  that should do the writing.
- Side effects have an address: files in `core/io.py`, processes in `app/spawn.py`, HTTP in
  `app/media.py` and `app/speech.py`, the browser in `ui/`. Rules code changes only the draft
  it is handed and rolls only the `Random` it is handed; nothing else changes state or rolls
  dice. A turn plays on a draft; the committed state is replaced only when the draft validates.
- Prompt renderers take a view, never the state. The narrator's view has no field that can
  hold a hidden fact.
- Pydantic for data that crosses a boundary (a file, a model answer, a tool call, a save,
  settings): `Frozen` for values and answers, `Mutable` for state a turn edits in place, `Loose`
  for a foreign shape whose extras are ignored. A `Mutable` model holds lists and dicts and
  mutates them in place; a `Frozen` model holds tuples. In-process records are dataclasses; a
  thing that owns behaviour or a resource is a plain class with `__init__`; `frozen` only when
  every field is immutable.
- Validate at each boundary with strict Pydantic V2 models and reject bad data at once. A
  model's invariants live in its own validator; a check that needs the engine's configuration
  lives in `Engine.validate`; a worldsmith bar collects every fault into one refusal so the one
  retry sees them all. Inside the process, construct models by keyword; `model_validate` is for
  the boundary.
- A message a role or the player is meant to read is a `Refusal`. Any other exception is a bug:
  raise it, do not catch it.
- A base class where we own every implementation; a `Protocol` only where a test double or a
  foreign object must fit without inheriting.
- Do not use `Any`. The one exception: a class or function generic on the game state, where
  `Game[P]`'s invariance makes `Any` the only spelling of the bound.
- Do not add an abstraction until two things need it. Do not build for future needs.
- Names are ordinary nouns and verbs: `entity`, `member`, `reply`, not `one`, `held`, `said`.
  A verb for a method that acts or computes (`restore`, `commit`, `ask`); a noun or adjective
  for a property (`busy`, `broken`). One stem per engine. A docstring says what the thing does
  and when it raises, in plain words. A comment only for a reason not visible in the code, one
  line.
- `type X = ...` for aliases. A `Literal` that selects a field is a dict field, not a `match`;
  `match` is for a closed union of classes.
- Keep `__init__.py` files empty. Imports are absolute, from the full module path, and flow
  one way: `core <- engines <- turn <- app <- ui`. Engines do not import each other. No IO at
  import time.
- Module layout: imports, `LOGGER`, constants, classes, public functions, private functions.
  A constant built from a class follows that class.
```

Dropped on purpose: "Write pure functions" (replaced by the side-effect bullet, which is what
it protected) and "a method that writes nothing outside its arguments is pure" (a definition
nobody used). Kept under Design decisions, unchanged: "Only resolver code changes state or rolls
dice" — it is about which role may act, not functions versus methods. Two sentences to add
there (D): "The page polls the service; the service never calls the page." and, if P4(b) lands,
"A World is `player`, `hub`, `board`, `jobs`, `source` and the methods over them."

---

## 5. Decisions for the brainstorming rounds

Ranked by how much downstream work each unlocks.

**D1. Campaign shape: sub-model or World base class?** (P4)
`world.campaign: Campaign | None` (A, B, C, E) keeps `SceneWorld` and `TunnelWorld` unrelated
and makes "board without hub" unrepresentable. A `World` base (D, lead) also unifies `player`,
`source`, party, `label/reveal`, `exchanges()/scenes()`, and lets four `Engine` methods go
concrete, but it is the bigger abstraction and Track G will want a party on both worlds anyway.
Either changes the save shape once. Lead recommends: `World` base holding a `campaign:
Campaign | None` sub-model, both at once, one stale-save commit.

**D2. Refusals: `Refusal(ValueError)` caught by name, or raise-everything?** (C1)
Five of six want `Refusal` and to keep the `*_unmet` list bars. A wants no string-returning
functions at all. Lead recommends `Refusal`; the bars keep returning lists (that is the "one
retry sees every refusal" decision) and raise `Refusal` at the end.

**D3. Character payload = sheet type?** (P10)
All four (D, ~85 lines, character-file format change), Loner + TG only (B, lead), or keep the
split (E). Lead recommends Loner + TG now, the others when Track G touches sheets.

**D4. Trim the golden fixtures?** (D alone)
Drop `state/*.json` (8 files, copies of shipped scenarios in an envelope) and `save/*.json`
(duplicating `turn/*.json`), keep prompts + schemas + turn facts. ~2,000 fixture lines. The
other five said keep the goldens whole. Lead: keep them through the refactor (they are the net),
revisit after.

**D5. Twelve empty subclasses → aliases?** (P8 / inventory 30)
Runtime is fine (fact 0.4); basedpyright's acceptance of an alias as `type[G]` is unverified.
Lead: try one engine on a branch; if pyright objects, keep the four `Game` subclasses and alias
the eight file classes.

**D6. How far does the rename go?** (C3)
Register (`one` → nouns, 509 sites), participles → verbs, one stem per engine, one hook name.
Pure churn with no behaviour change but it touches every file. Lead: do participles and engine
stems in one commit early (they set the tone), the `one` sweep last, file by file as each file
is touched anyway.

**D7. `import-linter` dependency or fix the AST test?** (C9)
D: ~25 lines of TOML replaces 98 lines of AST and closes fact 0.1. Others did not weigh in. Lead:
fix the tuple now (one line); decide the linter separately.

**D8. Drop `player_id` threading now, or wait for Track G.2 succession?** (P5)
A, B, D: drop it; every player is `PLAYER_ID` today and `Dungeon._consistent` already hard-codes
it. Lead agrees: drop now, reintroduce as a world method when G.2 needs it.

---

## 6. Suggested order and size

E's sequence, which the others' rankings fit:

1. Mechanical cleanups (C4): 30 minutes.
2. `Refusal` and the fact 0.1 one-liner (C1, D7): half a day.
3. Engine methods with P2, P3 and the worldsmith flow folded in, Breathless first (P1): one day.
4. Tunnel Goons world methods and one `kill()` (P5 second half, fact 0.2): half a day.
5. `Turn`/`GameService`/`Counter`/notes/`Thing` (P5, P6, P7): half a day.
6. Campaign object plus dict-shaped tags, one stale-save commit (P4, P9, D1): one day.
7. Renames last (C3, D6).

Total: two to three focused days with the goldens as the net. Roughly 500–650 source lines
removed (~6%), four concepts fewer (pack-closure dataclasses, `Entity` Protocol, `Kit`, the
empty file classes if D5 lands), and CLAUDE.md's Code section rewritten per section 4.

Raw reviews (not committed): `opinion-{A,B,C,D,E,lead}.md` in the session scratchpad.
