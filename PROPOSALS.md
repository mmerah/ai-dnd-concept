# PROPOSALS — conceptual simplification and consistency, round two

Input: six independent full reads of `src/aidm` (9,481 lines, 526 tests green, ruff and
basedpyright clean at `baa34f5`) on 2026-09-04: five Fable subagents (A generalist, B SOLID and
idiom, C the engines, D the platform, E the contrarian) and the lead. Each inventoried every
concept, judged it, and hunted for two spellings of one thing. This file merges them. Votes are
out of 6 where they matter. Line counts are estimates. Decisions (maintainer, 2026-09-04): D1 A,
D2 A, D3 C, D4 B, D5 A, D6 A, D7 A, D8 B, D9 B, D10 A, D11 A, D12 A, D13 A, D14 A, D15 B, D16 A,
D17 A, D18 A, D19 A; D20 was moot (`AGENTS.md` is already a symlink). Each heading in section 6
ends with the answer.

**Section 6 holds the decisions, now settled.** Section 7
lists what all six agree must not be simplified, with the test or rule that protects each.

Headline, agreed by all six: the architecture is right and there is no dead code. Every setting
is read, every public name has a caller, no concept gets a majority "remove". The 2026-09-03
form refactor did its job: the engines are classes, state is owned by the world. What is left is
smaller and of two kinds: **two spellings of one thing** (about thirty sites, most between the
scene family and the room family, or between the platform's gates), and **one verified bug plus
one edge crash** at the content directory. Total if everything lands: about −250 source lines,
−130 test lines, and one way to do each of the eight things now done two ways.

---

## 0. Verified facts (each checked by the lead or reproduced by a reviewer, not opinion)

1. **Bug.** `read_characters` calls `content_id(path.name)` before its `try` (`core/io.py:92`),
   so a non-slug entry under `characters/` (`.DS_Store`, `My Backup/`) raises out of
   `read_catalog` and the home page fails. `read_scenarios` filters on `world.json` first and
   is safe (`:77`). Reproduced by B and E.
2. **Edge crash.** Both content loops call `directory.iterdir()` on a directory that may not
   exist (`core/io.py:77,91`); `read_catalog` catches `Refusal` only (`app/launch.py:110`), so a
   fresh checkout pointing `SCENARIOS_DIR` elsewhere is a 500 on `/`. Reproduced by B.
3. **`Refusal` inside a pydantic validator is indistinguishable from `ValueError`.** Pydantic
   wraps both into `ValidationError`; `parse` (`core/entities.py:53-64`) rebuilds a `Refusal`
   from the first error. 18 validator sites raise `Refusal` (`engines/base.py:97,99`, `hub.py`,
   both worlds, every tool-args validator, three `Pack`s), 5 raise `ValueError`
   (`core/facts.py:21-27`, `core/play.py:83`, `config.py:126-128`). Direct constructions
   (`SceneWorld.begin`, `RoomWorld.begin`, `begin_game`, `opening_canon`) surface a
   `ValidationError`, and 32 tests already assert `pytest.raises(ValueError)` for messages
   written as `Refusal`. Reproduced by B (`Counter(current=5, maximum=3)` → `ValidationError`).
   All six found it.
4. **A generic `ChangeWorld[V]` with `Field(discriminator="verb")` does not work** in pydantic
   2.13.4: `TypeError: The core schema type 'any' is not a valid discriminated union variant`.
   Reproduced by B and the lead. The four identical `ChangeWorld` classes (`loner3e/tools.py:52`,
   `breathless/tools.py:25`, `twentyfourxx/tools.py:71`, `tunnelgoons/tools.py:22`) cannot fold
   that way.
5. **`AGENTS.md` reads identical to `CLAUDE.md`** because it is a git symlink to it (mode
   120000). Reviewer B reported a copy; the lead checked: no drift is possible. No action.
6. **`PendingOption.name` defaults to `""`** with the docstring "empty when its `answer` reads
   the id" (`core/play.py:45-49`), but nothing overrides `Engine.answer`, which refuses an
   unknown name (`engines/seam.py:88-94`); no production option omits it. A documented path
   nobody takes. (lead, A, E)
7. **`Fact.kind` is read back by value in exactly one place**, `loner3e/engine.py:225`
   (`conflict_lost`). Every other kind is a label in saves and goldens. (lead, A, E)
8. **The rooms bar runs twice on every advance.** `write_extension` passes
   `job_refusal`/`extension_refusal` as the worldsmith's retry check (`rooms/engine.py:386,390`),
   then `install_extension` raises on the same functions again (`:413,433`) on the same draft.
   `attach`'s docstring says "every caller refuses first" (`rooms/world.py:362`). Scenes' `install`
   trusts its bar (`scenes/engine.py:355`). Reachable only from eight direct calls in
   `tests/tunnelgoons/test_worldsmith.py`. (lead, A, C, E)
9. **`RETURN_BRIEF` names a field rooms do not have.** `hub.py:71` tells the worldsmith
   "`summary` and `recap` are written from it"; the rooms `ReturnDraft` field is `recaps`
   (`rooms/drafts.py:42`) and `rooms/engine.py:342` sends the same brief. The comment at
   `hub.py:64` ("`Campaign.sections` prepends the scene sentence") is half true: `sections` has
   one caller, in scenes. (A, C)
10. **Identical bodies in the two lifecycle bases:** `player_of` (`scenes/engine.py:118-120` =
    `rooms/engine.py:87-89`), `over` (`:122-123` = `:107-108`), `history`/`scenes` one-line
    forwarders (`:128-132` = `:113-117`), the `isinstance(scenario, self.scenario)` refusal
    (`:113-114` = `:97-98`), the `reopening = campaign.taken(intent) if at_hub …` line (`:441` =
    `:225-227`), `ask_worldsmith` (`:220-221` = `:257-258`), the `worldsmith.md` read in
    `__init__`, the `player_view` skeleton and the `master_sections` tail. In the worlds:
    `scenes()` (`scenes/world.py:165-167` = `rooms/world.py:423-425`), `exchanges()`, `at_hub`.
    Both worlds share `player`, `source`, `campaign`, `here()`, `records()`, `kill`,
    `reveal_hidden` with no common base. (all six)
11. **Two entity-line renderers.** `Person.line` (`engines/base.py:72-81`) and `RoomWorld.line`
    (`rooms/world.py:372-385`) print the same `- Name[id] — brief (dead)\n  sheet` shape; the
    rooms copy omits ` — ` on an empty brief (kit items have `brief=""`) and swaps in
    `sheet_rows()` for the player. `RoomWorld.reveal_hidden` (`:316-323`) re-implements
    `Thing.reveal` (`base.py:48-53`) by hand with the same trace. (all six)
12. **Per-engine copies.** `drop_item` is byte-identical modulo world type
    (`breathless/engine.py:287-294`, `twentyfourxx/engine.py:387-394`), as is `DropItem`
    (`breathless/tools.py:15`, `twentyfourxx/tools.py:43`). "not among the player's items" is
    written five times and "has only ₡" three times in 24XX. The pack creation step is built
    three times with two prompt texts. `source: str; license: str` sit on three engine `Pack`s
    and not on `base.Pack`. The shared-verb `case Reveal() | Enter() | Leave() | Kill()` branch
    is written three times; `JoinParty`/`LeaveParty` are dispatched only in Loner though they live
    in `scenes/tools.py`. `srd` pack lookup with its own refusal is written twice. (A, B, C)
13. **Concrete engines reach the world two ways:** `draft.payload` (Loner ×2, Tunnel Goons ×4)
    vs `self.world(draft)` (Breathless ×8, 24XX ×9), against the comment at
    `scenes/engine.py:96` prescribing `draft.payload`. Loner **must** use `draft.payload`
    because `self.world()` is typed `SceneWorld[C, P]` and hides `Loner3eWorld.twist`. (B, C)
14. **Rooms build the worldsmith prompt by hand three times** (`render_map`, `render_extension`,
    `render_return`, `rooms/engine.py:260-346`) repeating the YOUR ROLE / SOURCE MATERIAL / MAP SO
    FAR / ANSWER WITH lines, with two headings for the intent slot (`WHAT THE PLAYER WANTS TO
    PURSUE` vs `WHAT COMES NEXT`), and hand-roll the hub sections `Campaign.sections` already
    renders. Scenes has one `worldsmith_prompt` (`scenes/worldsmith.py:170`). (lead, A, C, E)
15. **The platform's gates are spelled twice.** Validate-then-commit at three sites
    (`turn/run.py:139-140`, `registry.py:40-41`, `runtime.py:226,237`); the tool lookup by name
    with two refusal sentences (`seam.py:88-94`, `run.py:95-97`); "route by engine header" at
    three sites (`io.py:110-115`, `seam.py:78-80`, `launch.py:104-109`); resume validates twice
    (`seam.py:82` then `runtime.py:306`); launch decodes each save twice (`launch.py:104,109`).
    (D, lead)
16. **`ask()` receives the role twice**: as `role` for the error text and baked into
    `spawn=partial(spawner.run, role)` (`runtime.py:191-201,416`). (lead)
17. **`speech.py` imports `claim` and `post_bearer` from `media.py`** (`speech.py:8`): the
    speech provider depends on the image module for an HTTP helper. `open_illustrator` and
    `open_reader` take the same inputs in different shapes; `illustrate()`+`speak()` are always
    called as a pair, three times. (lead, A, D)
18. **Small idiom drifts, each verified:** `ScenarioMeta.with_premise` hand-copies five fields
    where five other sites use `model_copy(update=)` (`core/model.py:33-41`); `_ImageUrl`/`_Image`
    are bare `BaseModel` beside `Loose` siblings (`media.py:129-146`); `SceneEngine.new_game ->
    BaseModel` vs `RoomEngine.new_game -> RoomWorld[N, P]`; `GameService` is the one dataclass of
    16 without `slots=True`; `SceneEngine.world` carries a comment inside a parenthesised return;
    `RoomEngine.narrator_view`'s `sorted(...)` is a no-op (`here()` already yields the player
    first); `BreathlessEngine.check`'s `and args.item_id is not None` is always true and
    `stepped(die) == 4` is computed twice; `change_hindrances` builds a dead set; the "last two
    scenes whole" `2` is a literal in three places; `twentyfourxx.tools.Attempt` (a roll)
    collides with `hub.Attempt` (a walk); `Campaign.taken` and `left_open` are one filter
    written twice; `Turn.consume` inlines the option lookup `core/creation.option_of` provides;
    `LaunchTarget.path` builds a UI route in the app layer. (A, B, D, lead)
19. **`read_packs` bypasses `decode` and `parse`** (`engines/base.py:165-170`): a broken pack
    raises `ValidationError`, a doubled key is silently last-wins. Every other JSON boundary
    runs both. (B, D, E)
20. **Hooks with one overrider:** `SceneEngine.leaving`, `glossary` (Loner), `RoomEngine.
    starting_items` (Tunnel Goons). `RoomEngine[N, P, G]` and `RoomWorld[N, P]` have one
    production subclass; the docstring says so (`rooms/engine.py:66-70`). (B, C, E, lead)
21. **Tool counts** (tools plus `change_world` arms, party arms and `commission` excluded):
    Loner 10, Tunnel Goons 9, Breathless 13, 24XX **15, at the cap**. NEXT-SPECS decision 4 says
    Breathless is 12; the code is 13. Stale number. Every `engines/<id>/` is under 2,000
    (shared `scenes/` 1,258, `rooms/` 1,252). (C)
22. **Tests.** `tests/support/{loner,breathless,twentyfourxx}.py` each hand-build the same
    `_hub_scene`/`_job_scene`/`hub_world` (~150 lines, three copies); Loner's test package is the
    odd one (`test_loner3e_engine.py` etc., no `test_tools`/`test_views`/`test_worldsmith`);
    narrowing is `raise AssertionError` ×23 vs `assert isinstance` ×47; `tests/core/test_seam.py:79`
    sets an attribute on the class where `seam.py:43` promises an instance; `tests/ui/test_game.py:4`
    imports a private name. (A, B, C, E)
23. **Not bugs, recorded so nobody "fixes" them ahead of Track G:** `after_job` has no
    once-per-job guard (prompt-enforced; G.2 plans `Job.raised`); `SceneWorld.party` has no writer
    in Breathless and 24XX (G.1 adds the arms); `SpeechConfig.voices` is unreachable from the
    settings page (tuples have no widget, by the page's own docstring); `Game.turn` equals
    `len(history)` on every path; `NarratorView.place` is read only by the illustrator's cache
    key; `SceneRecord.question` holds a place brief for room engines.

---

## 1. Inventory: every concept, one line, consensus verdict

Verdicts: **keep** (as is), **reshape** (same concept, different spelling), **merge**
(into another), **remove**. Nothing got remove from more than one reviewer.

| # | Concept | Lives in | Verdict | One line |
|---|---------|----------|---------|----------|
| 1 | Three roles, spawned cold, one retry | `config.py`, `app/spawn.py`, prompts | keep 6/6 | The product. |
| 2 | `Spawner`/`Driver` protocols, `CliSpawner`, `ask`, `final_message` | `app/spawn.py` | keep; trim | `ask` takes the role twice (P19); `final_message` runs in both driver and `ask` (P18). |
| 3 | `WorldsmithAnswer` Protocol + `_worldsmith` partial | `core/model.py:84`, `runtime.py:422` | keep 6/6 | The one seam engine→spawner; `Check[T]` alias should live beside it (C10). |
| 4 | Transactional draft: `draft()/commit()`, per-call candidate + rng fork | `core/model.py`, `turn/run.py:134` | keep 6/6 | Protected (7C). Validate-then-commit spelled thrice → one gate (P18). |
| 5 | `Turn` (begin/consume/picture/call/apply/_apply/finish) | `turn/run.py` | keep; trim | `consume` private, `option_of` reused (P23). |
| 6 | `Game.notes` read-once | `core/model.py:102` | keep 6/6 | Nine writers, one reader. |
| 7 | `Game.commissions` + `wanted/on_order/withdraw`, `Commission`, `later`, `Engine.fulfil` | `core/model.py`, `seam.py` | keep; `withdraw` returns None (P24) | Landed Phase 2; protected (7L). |
| 8 | Typed proposals: `Narration`, five scene drafts, `CastDraft`, `MapDraft`/`NpcDraft`/`ItemDraft`/`ReturnDraft` | `core/play.py`, `*/drafts.py` | keep 6/6 | Flat draft refused in NEXT-SPECS (7D). |
| 9 | `MasterTool`, `master_tool`, `schema_of/_text`, `NoArgs`, `Play` | `core/tools.py` | keep 6/6 | One schema function feeds MCP and prompts. |
| 10 | `ChangeWorld` ×4 + `apply_change` match per engine | each `*/tools.py`, `*/engine.py` | keep the four (fact 4); reshape the branch (P16) | Generic fold is impossible; the party arms and a `case _` fallthrough are not. |
| 11 | Facts: `Fact`, `DiceEvent`, `cards`, `traced`, `roll`, `keep_highest` | `core/facts.py`, `base.py` | keep 6/6 | `kind` stays a free string (D6). |
| 12 | Told/hidden gate: `Thing.known`, `fact(narrate=)`, `reveal` | `engines/base.py:21-53` | keep; rooms reuse `reveal` (P9) | The leak rule. |
| 13 | `NarratorView` (+ `spoken`, the two refusals) / `PlayerView` / `Panel` / `PanelRow` / `Subject` / `Speaker` | `core/views.py`, `core/play.py` | keep 6/6 | Never merge the two views (7E). `Speaker` vs `Subject` is D8; `PanelRow`'s three shapes stay (all lean keep). |
| 14 | Pending decisions: `PendingDecision`, `PendingOption`, `Answer`, `Engine.answer` | `core/play.py`, `seam.py` | keep; `name` required (P2); one tool lookup (P18) | |
| 15 | Exchange / Line / SpokenLine / `SceneRecord` / `ChapterRecord` / `render_history` at three depths | `core/play.py`, `core/views.py` | keep 6/6 | NEXT-SPECS decision 2; `question` → `focus` rename is D14. |
| 16 | Engine seam (`Engine` ABC, 17 abstract) | `engines/seam.py` | keep; hoist what both bases duplicate (D2) | Protected as an ABC (7G). |
| 17 | `SceneEngine[C, P, G, K]` | `scenes/engine.py` | keep 6/6 | Four params are the honest price of `Game[Any]`; pure prompt-line helpers move to the world (P10). |
| 18 | `RoomEngine[N, P, G]`, `RoomWorld[N, P]`, `Dungeon[N]` | `rooms/` | keep 5/6; E: fold | One production subclass → D3. |
| 19 | Scene world (`SceneRun`, `SceneCanon`, `SceneWorld`, party, `apply_scene`) | `scenes/world.py` | keep 6/6 | The best-written module; the model for rooms' `install_extension` (P11c). |
| 20 | Scene bar (`scene_unmet`, `cast_unmet`, `_hub_unmet`) run once | `scenes/worldsmith.py` | keep 6/6 | Rooms should run its bar once too (P3). |
| 21 | Room bars (seven `*_refusal` builders) | `rooms/worldsmith.py` | keep | Free functions by import order; say so once. |
| 22 | Hub / campaign (`Campaign`, `Job`, `Attempt`, `Offer`, `Board`, briefs, panels) | `engines/hub.py` | keep; rooms use `sections`/`board_panel` (P11) | Protected (7M). `taken` via `left_open` (P20); the prompt copy stays with the model (C15). |
| 23 | Party (`join_party`, `leave_party`, `party_rows`, `party_panel`) | `scenes/world.py`, `scenes/tools.py` | keep 6/6 | Track G; register the arms in the base now (P16). |
| 24 | Cast: `Thing`, `Person`, engine sheets (`Loner3eSheet`, `Survivor`, `Operator`, `Goon`, `Npc`, `Dweller`) | `base.py`, `*/world.py` | keep; one `line` (P8) | Sheet rules become sheet methods (P12). |
| 25 | `Counter` + `change` | `base.py:90-122` | keep 6/6 | Four engines. |
| 26 | Packs (`Pack`, `read_packs`, `pack_options`, per-engine `Pack`) | `base.py`, `*/worldsmith.py` | keep; `source`/`license` on base (P14); read through `parse` (D12) | |
| 27 | Scenarios, characters, envelopes, headers, `Named`, twelve empty `XGame/XScenario/XCharacter` | `core/model.py`, `*/world.py` | keep 6/6 | The envelopes are what `isinstance` narrows; all six lean keep the subclasses. |
| 28 | Creation flow (`CreationStep`, `Picks`, `check_picks`, `option_of`, `chosen_option`) | `core/creation.py` | keep 6/6 | One pack-step helper for the three scene engines (P15). |
| 29 | Source documents | `core/source.py` | keep 6/6 | |
| 30 | Saves (`FileStore`, atomic write, `decode`, `restore`) and content readers | `core/io.py`, `seam.py` | keep; fix fact 1–2 (P1); decode once (P18) | A content library object is D15. |
| 31 | Registry (`build_engines`, `begin_game`) | `engines/registry.py` | keep 6/6 | `begin_game` as `Engine.begin` is D16. |
| 32 | `GameService` / `Runtime` | `app/runtime.py` | keep 6/6 | Presentation tail folds to one `present()` (P17); `play` split is D17. |
| 33 | Launch catalog | `app/launch.py` | keep | `path` moves to `ui` (P25); `CatalogEntry.kind` on characters is noise (lean: `None` default). |
| 34 | Settings, `.env`, reflection page | `config.py`, `ui/settings.py` | keep 6/6 | Reflection has paid for itself; all lean keep. |
| 35 | Media / `Illustrator`, Speech / `Reader`, `post_bearer`, `claim` | `app/media.py`, `app/speech.py` | keep; shared helpers to their own module (P17) | |
| 36 | MCP endpoint | `app/mcp.py` | keep 6/6 | |
| 37 | UI pages (`GamePage`, `LaunchForm`, `CharacterForm`, `ScenarioForm`, `SettingsForm`), widgets, theme, `panels.py` | `ui/*.py` | keep; `_observed` → dataclass, `panels.py` folds into `game.py` (P5) | |
| 38 | Ids (`Slug`, `EntityId`, `CheckedEntityId`, `EngineId`), `Frozen`/`Mutable`/`Loose`, `Refusal`, `parse` | `core/entities.py` | keep 6/6 | The rule for which id where is written nowhere (C7). |
| 39 | Prompt text: five `.md` files + ~25 constants | `turn/prompts`, `engines/**/*.md`, `hub.py` etc. | keep 6/6 | Role text on disk, templated text in code: the visible rule holds (C15). |
| 40 | Golden tests (prompts, schemas, turn fact streams), `ScriptedSpawner`, `Table` | `tests/core/golden_*`, `tests/support/table.py` | keep 6/6 | Prompt goldens vs "not prose" is D10. |
| 41 | Boundary tests (package direction, context leak, integrity) | `tests/core/test_*_boundary*.py` | keep 6/6 | Protected (7P). |
| 42 | Per-engine test support (`small_world`, `hub_world`, `_hub_scene`…) | `tests/support/*.py` | reshape (P21) | Three copies of one builder. |

---

## 2. Simplification proposals, ranked by value / risk

Each: what, where, votes, lines, risk, what is lost. Grouped by the size of the step.

### Tier 1 — bugs and no-loss fixes (about an hour, no fixture moves)

**P1. Guard the content loops.** (B, E; 2 bugs, fact 1–2) `read_characters` iterates
`sorted(p for p in directory.iterdir() if p.is_dir())` and moves `content_id` inside the `try`;
both loops return nothing when `not directory.is_dir()`. `core/io.py:77,91`. +4/−1. Risk none.
Lost nothing. Add one launcher test for a non-slug folder beside `tests/ui/test_launcher.py:80`.

**P2. `PendingOption.name` required.** (lead, A, E; fact 6) `name: str = Field(min_length=1)`;
delete the docstring clause. Two view-only tests name a tool. `core/play.py:45-49`. −2. Risk none.
Lost: a path nobody built on.

**P3. Run the rooms bar once.** (lead, A, C, E; fact 8) Delete the re-runs at
`rooms/engine.py:411-414,433-434`; the eight direct `install_extension` tests call the refusal
first or go through `advance`. −8 source. Risk: low; the tests that assert a refusal *through*
install retarget to `job_refusal`/`extension_refusal`. Lost: a belt under braces that only tests
exercised; scenes already lives without it.

**P4. Fix the prompt facts.** (A, C; fact 9) `hub.py:71` → "`summary` and the recap fields";
`hub.py:64,102` comments stop naming Tunnel Goons ("a room engine"); `rooms/` prose stops
saying "tavern"/"dungeon" where it means the hub and a region, or `RoomEngine` gains a
`hub_phrase` like scenes (one user; lean: reword only). ±3. Risk none.

**P5. The small idioms bundle.** (A, B, D, E, lead; fact 18) One commit: `with_premise` via
`model_copy(update=)`; `_ImageUrl`/`_Image` → `Loose`; `GameService` `slots=True`;
`SceneEngine.new_game -> SceneWorld[C, P]`; the comment above `SceneEngine.world`; drop the
rooms `sorted` no-op and Breathless's redundant `item_id` test and second `stepped`; one pass in
`change_hindrances`; `WHOLE_SCENES = 2` beside `SCENE_EXCHANGES` used at the three sites;
`twentyfourxx.tools.Attempt` → `Roll`; "resumed" logged from `session`, not argv; `decision_widget`'s
callback typed `Awaitable[None]`; `GamePage._observed` → a frozen `Observed` dataclass; `ui/panels.py`
folds into `ui/game.py` (one caller each; skip if a ~470-line page bothers); `ANSWERED_BY_OPTION` moves
beside `RULES_WAIT` (used only in `run.py`); `_can_type` public for its test. About −30. Risk none.

### Tier 2 — one spelling per thing (half a day; one golden regeneration run)

**P6. Validators raise `ValueError`; constructions go through `parse`.** (6/6 on the fact;
lean on the direction in D1) The 18 sites become `ValueError`; `SceneWorld.begin`,
`RoomWorld.begin`, `begin_game` and the two `opening_canon`s build through `parse(cls, {...})`
so the first-error `Refusal` reaches `Engine.compose`/`Runtime.new_scenario.playable` instead of
a pydantic dump. ±0 lines. Risk: none (`Refusal` ⊂ `ValueError`, every existing
`pytest.raises(ValueError)` holds). Lost: nothing; gained: CLAUDE.md's rule becomes true at
`new_game` and `begin_game`.

**P7. One way to reach the world in a concrete engine.** (B, C; fact 13) `draft.payload` in
Breathless (8) and 24XX (9), as the comment at `scenes/engine.py:96` prescribes; `self.world()`
stays the generic bases' spelling. ±0. Risk none.

**P8. One entity line.** (A, C, E, B; fact 11) `Thing.line(*, rows=None, detail="")` prints
`- name[id]` + ` — brief` only when non-empty; `Person.line` adds `(dead)` and defaults
`rows` to `self.rows()`; `RoomWorld.line` becomes
`entity.line(rows=self.sheet_rows()) if entity.id == self.player.id else entity.line()` and
`Item` gets the `Thing` line. `base.py`, `rooms/world.py`. −12. Risk: the scene goldens print
` — ` on an empty brief today; no shipped scenario or character has one (grep: 0), so the
fixtures should not move; run them. Timing is D7 (now, or after Track G rewrites these lines).

**P9. `Thing.reveal(card="")`; rooms use it.** (A, C) `scenes/world.py:215-221` builds the
fact then patches its card by `model_copy`; `rooms/world.py:303-323` re-derives the same fact.
Both arms become `entity.reveal(card=...)`. −10/+3. Risk none; kinds and traces unchanged.

**P10. Prompt-line helpers move onto the world they read.** (A, B, C) `SceneEngine.here_lines/
hidden_lines/cast_lines` (`scenes/engine.py:223-243`) → `SceneWorld`; `RoomEngine.map_so_far`
(`rooms/engine.py:348-363`) → `RoomWorld`. CLAUDE.md's method rule; matches
`RoomWorld.place_lines/ways_lines`. 0 net. Risk none; goldens unchanged.

**P11. Rooms get one prompt assembler and use `Campaign` for the hub block.** (lead, A, C, E;
fact 14) (a) A `worldsmith_prompt(role, *, source, map_so_far, history, hub, player, asked,
intent, guidance, answer)` in `rooms/worldsmith.py` mirroring scenes; `render_map/
render_extension/render_return` become section tuples; one heading (`WHAT COMES NEXT`), one
`SOURCE MATERIAL` fallback constant. (b) `Campaign.sections(hub_title, brief, *, returning)`
takes the brief so rooms pass `JOB_BRIEF` and scenes prepend `WRITE_HUB_SCENE`; a
`Campaign.job_before(job, records)` replaces the `THE JOB BEFORE` tuple written in both bases;
rooms' Board panel uses `board_panel(at_hub, reporting=REPORT_ROW)`. (c) `install_extension`'s
map-side mutation (`attach`, `job.close`, recaps, `board`) moves to `RoomWorld.apply_extension/
apply_return` so the engine only builds facts, as scenes does. −60/+30. Risk: medium; the return
prompt gains `ENGINE GUIDANCE` and its heading changes (D13); `tests/tunnelgoons/test_worldsmith.py`
prompt assertions are the guard. Lost: nothing measurable.

**P12. Rules whose first argument is the sheet become sheet methods.** (A, B, C) 24XX:
`Operator.require_item(id)`, `Operator.pay(cost)`, `change_hindrances/gain_item/drop_item/
repair_item/spend` as methods (the resolvers delegate); Breathless: `Survivor.require_item`,
`drop_item`, `take_loot`, `loot_options`; Loner: `Loner3eSheet.change_tags/drive/refill`,
`Loner3eWorld.conflict_prompt`; `gear_detail` → `Item.detail`. `apply_change` bodies become
one-liners. About −25 net. Risk: low; no test calls these by name, messages unchanged. Lost
nothing. Justified exceptions stay functions with a docstring saying why: `*_refusal` (import
order), `run_of`, `here_panel`, `render_narrator`, `scene_key`, `post_bearer`.

**P13. Shared refusal strings and one `require_here`.** (B, C) `UNKNOWN_ID`, `IS_DEAD` constants
in `base.py` for the three and two copies; `SceneWorld.require_here(entity_id, *, alive=False)`
replaces `require_alive_here`. −12. Risk low (four tests match substrings; keep the wording).

**P14. `source` and `license` on `base.Pack`.** (C, B) Delete the six duplicated lines; the
test pack at `tests/core/test_seam.py:78` gains two keys. Required or defaulted is D11.

**P15. `SceneEngine.pack_step()` and `srd_pack()`.** (C) One pack step with one prompt text
replaces the three `first`/`pack is None` blocks; one `srd_pack()` refusal replaces
`twist_table`'s and `complications`'s. −13. Risk none. Lost: Loner's "character table set" wording.

**P16. Register the party arms once; a `case _` fallthrough.** (C, B) `SharedChange` gains
`JoinParty | LeaveParty`, `SceneEngine.shared_change` gains the two cases, Loner's `apply_change`
loses them; each engine's `apply_change` ends `case _: return self.shared_change(...)` (pyright
narrows the remainder to `SharedChange`). Breathless/24XX unions unchanged, so their schemas
and goldens do not move. −8/+4. Risk none; this is G.1's registration step done early.

**P17. `app/providers.py`; one opener shape; one `present()`.** (lead, A, D) `post_bearer`
and `claim` move out of `media.py`; `open_reader(settings, target, store, *, voice)` mirrors
`open_illustrator`; `GameService._present(state)` holds the `illustrate()+speak()` pair now
written three times; the page reaches clips only through `newest_clip()`. −6. Risk none.

**P18. One gate for each platform check.** (D, E, lead; fact 15) `Engine.commit(draft)` =
validate then `draft.commit()`, used by `Turn._apply`, `begin_game`, `close`, `_grow`;
`Engine.tool(name)` is the one lookup (`Turn.call` and `Engine.answer` call it; `answer`'s
"to play option" wording wrapped for `test_decisions.py:206`); `_resumable` stops validating a
state `restore` just validated; `restore` takes the decoded value so `read_catalog` decodes
once, and `read_scenario` routes through the same header helper; `final_message` runs once
(drivers extract, `ask` validates). −20/+12. Risk low.

**P19. `ask(spawner, role, prompt, model, refusal)`.** (lead; fact 16) The role is passed once;
`_worldsmith = partial(ask, spawner, "worldsmith")`. −4. Risk none.

**P20. `Campaign.taken` via `left_open`.** (lead, B) Undo `TAKE_JOB.format` and call
`left_open(title)`. −6. Risk low (five tests cover `taken`).

**P21. Test hygiene.** (A, B, C, E; fact 22) One `scene_hub_world(...)` builder in
`tests/support/scenes.py` with a six-line wrapper per engine (−90); Loner's test files take the
four-file names; `assert isinstance` replaces `raise AssertionError` narrowing; `test_seam.py:79`
sets the attribute on the instance. −130 test lines. Risk none.

**P22. `read_packs` through `decode` + `parse`.** (B, D, E; fact 19) ±2. Whether to do it is D12.

**P23. `Turn.consume` uses `option_of` and becomes `_consume`.** (D) The three tests that build
`Turn` directly go through `Turn.begin`, the only production path. ±0.

**P24. `Game.withdraw` returns `None`.** (D, E, lead) The withdraw-as-`Play` lambda lives in
`runtime.py` where it is used; the engines already discard the return. +3/−1.

**P25. The game route lives in `ui`.** (D) `LaunchTarget.path` → `game_path(target)` beside the
`@ui.page` that declares it. ±0.

### Tier 3 — structural; each is a decision (a day each)

**P26. `Engine` owns what both bases duplicate.** (lead, B, C; E against) → **D2.** A `World`
base or Protocol in `engines/base.py` (`player: Person`, `source`, `campaign`, `exchanges()`,
`records()`, `scenes()`, `record(exchange)`), an abstract `Engine.world(state) -> W`, and
concrete `over`, `history`, `scenes`, `record`, `player_of`, `check_scenario`, the `reopening`
line, the trail/jobs panels. Four abstract methods leave the seam; −40 across the bases.

**P27. One `CommissionArgs` base and a concrete `commission_tool`.** (B, C; A leans leave) →
**D4.** Note the Phase 2 review already refuted a shared base because pydantic prints parent
fields first, so `kind` would print last in the schema the master reads; the schema goldens
would drift.

**P28. Fold `engines/rooms/` into `engines/tunnelgoons/`.** (E) → **D3.**

**P29. `begin_game` → `Engine.begin`; `launch_target` → `LauncherCatalog.target`.** (B) →
**D16.** CLAUDE.md's method rule applied to the last two free functions over our objects.

**P30. `GameService.play` split; presentation ownership.** (A, D, B) → **D17.**

**P31. A content library object for the three directories.** (D) → **D15.**

Not proposed by anyone, with the count that killed it: a shared `drop_item` over a `Protocol`
(two `Item` types share only `name`; the protocol is longer than the two copies); sharing
`outcome()`/`test_luck` between Breathless and 24XX (different words the docs commit to);
splitting `Engine` into role-sized protocols (one implementer per slice); a `Presentation`
object (one caller); removing the single-overrider hooks (Track G uses them).

---

## 3. Consistency findings (the same thing written two ways; the standard a senior would pick)

- **C1. Exceptions inside validators.** `Refusal` ×18 vs `ValueError` ×5 (fact 3). Standard:
  `ValueError` inside a validator, `Refusal` only where a caller reads it unwrapped, written
  into CLAUDE.md in one sentence. → P6, D1.
- **C2. Constructing a model from untrusted data.** `parse(model, value)` vs bare
  `model_validate*` (`spawn.py:86,202`, `base.py:168`, `media.py:119`) vs bare `Model(...)` on
  worldsmith-derived data (`begin` ×2, `begin_game`, `opening_canon` ×2). Standard: `parse` at
  every boundary CLAUDE.md names; bare construction only for code-built values. → P6, D12.
- **C3. What an edge catches.** `(OSError, Refusal)` ×6 vs `Refusal` ×4 (`ui/create.py:93`
  around a file write; `io.py:80,100`; `launch.py:110`) vs `Exception` ×2 (documented, media).
  Standard: `(OSError, Refusal)` wherever a file or process is touched; `working()` for every
  player-facing failure in `ui`. → P1, P5.
- **C4. Copy-with-change.** `model_copy(update=)` ×5 vs a hand-written constructor ×1;
  `deepcopy` ×5 vs `model_copy(deep=True)` ×1. Standard: `model_copy` for models, `deepcopy`
  for the rng. → P5.
- **C5. Who renders a prompt line.** Rooms: on the world. Scenes: split between world and
  engine. Hub: on `Campaign`. Standard: on the state object. → P10.
- **C6. Prompt assembly.** One builder (scenes) vs three hand-built (rooms); hub sections
  through `Campaign` (scenes) vs inline (rooms); one heading vs two for the intent slot;
  `"(none — write from the cast)"` vs `"(none — write from the setting)"` ×3. → P11.
- **C7. Which id type where.** `Slug` for content ids and places, `CheckedEntityId` for ids the
  model writes, `EntityId` for ids the world checked; rooms then cast `EntityId(campaign.place)`
  twice. Standard: write the rule down in `entities.py`, and make `Campaign.place`/`Job.place`
  `CheckedEntityId` (same grammar). Low value; note.
- **C8. `name[id]` rendering.** `Thing.label` (prefixes "the player ") vs six hand f-strings.
  Standard: a `Thing.tag` (`name[id]`, no prefix) for the six. → with P8.
- **C9. `kill` and `reveal` shapes.** `SceneWorld.kill(entity_id)` vs `RoomWorld.kill(actor)`;
  rooms re-implements `reveal`. Standard: `Thing.reveal()` everywhere (P9); leave `kill` (each
  matches its callers) with one docstring line, or align after Track G (D7).
- **C10. The refusal-callback type.** `Check[T]` (`spawn.py:21`) vs inline
  `Callable[[M], str | None]` ×3. Standard: one alias in `core/model.py` beside `WorldsmithAnswer`.
- **C11. World access in engines.** `draft.payload` vs `self.world()` (fact 13). → P7.
- **C12. Property vs method for derived state.** `Campaign.finished` (property) and
  `Campaign.terms()` (method) are the same scan. Standard: property for O(1) reads (`run`,
  `at_hub`, `open`), method for anything that scans; make `finished` a method.
- **C13. Where creation and guidance constants live.** `BOARD_GUIDANCE` in
  `twentyfourxx/engine.py` while every other engine keeps worldsmith text in `worldsmith.py`;
  SRD numbers (`STARTING_DICE`, `STARTING_ITEMS`) split between `engine.py` and `world.py`.
  Standard: worldsmith text in `worldsmith.py`, SRD numbers in `world.py`, page options with
  `creation_steps`.
- **C14. Naming.** Sheets thematic (`Survivor`, `Operator`, `Goon`) except `Loner3eSheet`; three
  `Pack`s imported as `ScenePack` — `<Engine>Pack` would free the base name; `worldsmith` the
  `str` vs `worldsmith` the callable inside one method (`worldsmith_role`); `Attempt` ×2. → P5,
  and rename `Loner3eSheet` only if a fifth engine makes the pattern matter.
- **C15. Prompt text on disk vs in code.** Role text → `.md`; templated or engine guidance →
  code. Exceptions: `OPENING` (`runtime.py`) and `ONE_SHOT_OPENING` (`hub.py`) are untemplated
  role text in code. Acceptable; recorded. Three loading styles (init-time attribute, `@cache`
  function, constant) are all once-per-process; the two lifecycle `__init__`s repeating the
  `worldsmith.md` read is the only nit (a module constant each).
- **C16. Test conventions.** Four-file test packages except Loner; `raise AssertionError` vs
  `assert isinstance`; `small_world()` in code vs Loner reading the shipped scenario. → P21.
- **C17. Foreign-shape models.** `Loose` everywhere except two nodes in one reply tree. → P5.
- **C18. `config.py` models on `BaseModel + ConfigDict(frozen=True)` ×4** rather than `Frozen`.
  `Frozen`'s `extra="forbid"` would turn a `.env` typo like `ROLES__NARATOR__MODEL` into a
  start-up error (today it vanishes). → D18.

---

## 4. SOLID and idiom findings

- **S1 (SRP).** `RoomEngine.install_extension` lands four different drafts in one 46-line
  method chosen by `isinstance` and `at_hub`; scenes splits the same into `apply_scene` (world)
  and `install` (engine). → P11c. `GameService` carries the turn lifecycle plus ~35 lines of
  presentation pass-through with its own state (`_background`); `play` runs gate, master,
  commission loop, narration, commit, media, growth in one method. → P17, D17. `Campaign` has
  25 methods over four families (rules, prompt text, panels, history folding); CLAUDE.md
  sanctions it and two families share it, so group them with a comment, do not split.
- **S2 (OCP).** Adding a shared arm today touches the union, `shared_change`, every engine's
  union and every engine's first `case`. With the generic `ChangeWorld` ruled out (fact 4), the
  cheapest gain is P16's fallthrough: a new shared arm then touches `scenes/tools.py`,
  `shared_change`, and one union line per engine. Adding a scene engine copies a `ChangeWorld`
  class, the `change_world`/`next_scene` registrations and the pack step; P15 and B's
  `SceneEngine.master_tools` = shared two + `rules_tools()` (D2's companion) make an engine add
  only its own.
- **S3 (LSP).** `Engine.new_game -> BaseModel` while `RoomEngine` narrows and scenes does not
  (P5). `Engine.crossing()` returning `None` is a control-flow flag: `GameService.play` routes a
  Move-on to `extend()` on it (`runtime.py:101-104`); a subclass changes which method the app
  calls by returning `None`. Low priority; one docstring line on `play` naming the contract, or
  an explicit `Engine.crosses: bool` — D19.
- **S4 (ISP).** `Engine` has 17 abstract members and consumers use disjoint slices (`Turn`,
  `Runtime.new_scenario`, the UI, `read_catalog`). Splitting is three names for one object with
  one implementer per family; keep it fat, keep it under ~20. What shrinks it honestly is
  hoisting the duplicated bodies (D2): −4 abstract methods.
- **S5 (DIP).** Clean: `Spawner`, `WorldsmithAnswer` and `Driver` are protocols injected at
  the root; `core` imports nothing above it; `ui` names no engine, enforced by test. The one
  accidental dependency is `speech → media` (P17).
- **S6 (generics).** `SceneEngine[C, P, G, K]` vs `RoomEngine[N, P, G]`: `G` cannot be derived
  from the world params because Loner's world subclasses `SceneWorld`, so `world_type` beside
  `game` is the honest price of `Game[Any]`; `K` exists so `self.packs` is typed. Keep.
- **S7 (idiom).** Unnamed tuples where a record is meant (`GamePage.seen` 5-tuple, `_STEP_COPY`
  values, `_shown` triples) → P5. `Roles.for_name`/`Providers.for_name` `match` over a `Literal`
  is the typed spelling; keep. `Engine.compose`'s `nonlocal built` is tested and no clearer as
  a cell; keep. `Turn.call` returning a string for "the rules wait" but raising for "game over"
  is intentional and commented; keep. `RoomEngine.fulfil`'s `case _: raise ValueError` exists
  because `Commission.kind` is `str` in core; keep. `_skill` is a `cast` spelled as a search;
  `theme._inject_css` uses `@cache` as run-once; `render_next` uses `issubclass(answer, ...)` as
  two booleans where `write_next` already knows `returning`; `render_extension` has a
  positional `hub` between positional and keyword-only params. Each one line.
- **S8 (over-engineering against "two things need it").** Nothing in the platform fails the
  rule. In the engines: `RoomEngine` with one subclass (D3); `leaving`, `glossary`,
  `starting_items` with one overrider each (seam points Track G will use; list them so the next
  engine either uses them or they go); the reflective settings page (all six lean keep).
- **S9 (under-engineering, recorded so nobody "optimises" it).** `Turn._apply` deep-copies the
  whole game per tool call and `commit` revalidates it whole. Correct, cheap at 3 KB saves, and
  protected by three named tests (7C).

---

## 5. Order of work, if everything is taken

1. Tier 1 (P1–P5): one commit, no fixture moves, about an hour.
2. P6 and P7 (mechanical, pytest stays green), then P8–P10, P13, P15–P17, P19, P20: one golden
   run, half a day.
3. P11, P12, P18, P21–P25: prompt tests to retarget, a day.
4. Tier 3 only where section 6 says yes.

---

## 6. Decisions for the maintainer

Each with options and the reviewers' lean, and the maintainer's answer (2026-09-04) on the
heading.

**D1 — `Refusal` or `ValueError` inside validators? — settled: A** (fact 3; 6/6 on the fact, 5/6 lean A)
- A. `ValueError` in every validator; one CLAUDE.md sentence: "inside a validator raise
  `ValueError`; `parse` turns it into the refusal". 18 sites, mechanical, zero behaviour change.
- B. Keep `Refusal` everywhere and add the CLAUDE.md sentence "inside a validator, `Refusal` is
  only the message; pydantic wraps it". Zero edits; the class name keeps lying.
- C. A `refuse(msg)` helper raising `PydanticCustomError` so the message is verbatim (drops
  pydantic's "Value error, " prefix in re-prompts). Cleaner text, one more helper.
- Lean: **A**, C if the prefix in re-prompts bothers anyone.

**D2 — Hoist what both lifecycle bases duplicate into `Engine`? — settled: A** (fact 10; lead, B, C for; E
against)
- A. A `World` base class in `engines/base.py` (two things need it: `SceneWorld`, `RoomWorld`)
  with `player`, `source`, `campaign`, `exchanges()`, `records()`, `scenes()`, `record()`; the
  seam gains abstract `world(state) -> W` (a second type parameter, `Engine[W, G]`) and concrete
  `over`, `history`, `scenes`, `record`, `player_of`, `check_scenario`, the shared panels and
  the `reopening` line. −40, four abstract methods fewer. Risk: basedpyright strict on the
  covariant world type; `hub.py` imports `base.py` so `campaign` on the base needs care (put the
  base in `hub.py`, or keep `campaign` off it).
- B. A `Protocol` instead of a base (no inheritance, same methods). Same saving, no shared
  validators.
- C. Leave: six one-liners duplicated; E's "not until a third family".
- Lean: **A**; the duplication is the seam's own shape, and "two things need it" is met.

**D3 — `engines/rooms/` with one production subclass. — settled: C (keep the split as is)** (fact 20; E for folding, five keep)
- A. Fold into `engines/tunnelgoons/`: `RoomEngine[N,P,G]` → `TunnelGoonsEngine`, `Dungeon[N]`
  over `Npc`, the `dweller`/`world_type`/`starting_items`/`guidance` hooks go. −90 to −120 lines
  of generic plumbing; 1,676 lines folded, under the cap; `test_rooms.py`'s `SixthEngine`
  rewritten; CLAUDE.md and `docs/TUNNEL-GOONS.md` edited. IDEAS 18 (Maze Rats) says it returns
  "on its own strict model", so no second crawler is planned.
- B. Keep the split, rewrite `rooms/engine.py:66-70` so it stops promising a second crawler
  ("building for future needs" in the docstring's own words).
- C. Keep as is.
- Lean: **B now**; A is the honest reading of CLAUDE.md's rule against a line in CLAUDE.md, so it
  is the maintainer's call, not a reviewer's.

**D4 — One `CommissionArgs` base and a concrete `commission_tool` on the seam? — settled: B** (fact 12; B, C
for; A leans leave; refuted once in the Phase 2 review)
- A. Do it: `kind: str` on the base, each family overrides `kind` with its `Literal`; `Engine`
  gains `commission_args` and `commission_hint` class attributes. −22. Cost: pydantic puts
  parent fields first, so `kind` prints last in the schema the master reads (the Phase 2
  objection), and the two `later` descriptions ("next scene" / "next region") either unify or
  stay as field overrides. Schema goldens regenerate.
- B. Hoist only `ask_worldsmith` and the tool construction, keep the two args classes whole.
  −10, schema unchanged.
- C. Leave (−14 lines is not worth two more class attributes).
- Lean: **B**.

**D5 — The four `ChangeWorld` classes. — settled: A** (fact 4)
- A. Keep the four (twelve lines, no risk).
- B. A `change_world_tool(union, resolve)` helper using `create_model` so the class is built per
  engine; hides the schema the master reads behind a call.
- Lean: **A**; recorded so nobody tries the generic again.

**D6 — `Fact.kind`. — settled: A** (fact 7)
- A. Keep as a free-string label (D's view: a `Literal` would leak engine kinds into core).
- B. Drop it; `conflict_lost` becomes a typed flag on the fact or a return value of `_strike`.
  Saves and turn goldens change.
- Lean: **A**; it is the journal's and the goldens' vocabulary and costs nothing.

**D7 — Align the entity line, `kill` signatures and `reveal` now, or after Track G? — settled: A** (P8, P9,
C9; B leans wait, A/C/E lean now)
- A. Now: P8 and P9 land in Tier 2.
- B. Wait: G.3 rewrites `Npc` (a sheet), `take_lead` and every one of these lines; aligning
  twice is waste.
- Lean: **A for `reveal` (P9, no G overlap), B for `line`/`kill` if Track G starts within the
  month, else A.**

**D8 — `Speaker` vs `Subject`. — settled: B (now, not with G.1)** (D, A) `Speaker` is `Subject` minus `brief`; its only
constructor is `Subject.speaker()`.
- A. Keep both: a stored line never carries authoring text that may later be rewritten.
- B. Drop `Speaker`; `NarratorView.speakers: tuple[CheckedEntityId, ...]` with a validator
  `speakers ⊆ subjects` — the same shape NEXT-SPECS G.1 plans for `party`. Saves go stale.
- Lean: **A now, B when G.1 lands** (one migration instead of two).

**D9 — Derive `Game.turn` from history? — settled: B** (D) `turn == len(history)` on every path.
- A. Keep the field (one int, the launcher's cheapest read).
- B. Delete it (stale saves, 12 test edits).
- Lean: **A**, revisit in the G.1 stale-save pass.

**D10 — Golden prompt fixtures vs "test behaviour, not prose". — settled: A** (E) Eight prose snapshots (883
lines) plus five wording-asserting tests.
- A. Keep both kinds, and say why in CLAUDE.md: "a golden is a drift detector, not a prose
  test".
- B. Keep the schema goldens (the MCP boundary), replace prompt goldens with structural asserts
  (section headings in order).
- C. Drop both.
- Lean: **A**; B is what `test_context_boundary` does for one engine and would need four copies.

**D11 — `source`/`license` on `base.Pack`: required or defaulted? — settled: A** (P14)
- A. Required; the test pack gains two keys; a pack naming no licence does not load.
- B. `""` defaults; nothing breaks, the guarantee goes.
- Lean: **A**; the docs already say every pack carries them.

**D12 — `read_packs` through `decode`+`parse`? — settled: A** (fact 19; B, D, E for; A leans keep raw)
- A. Yes: a doubled key is refused at boot like every other JSON, the failure reads as a
  `Refusal`.
- B. Keep raw and say so in the docstring ("shipped, not user data; crash with the full
  pydantic error").
- Lean: **A**; consistency over one nicer traceback.

**D13 — The Tunnel Goons return prompt gains `ENGINE GUIDANCE` and the `WHAT COMES NEXT`
heading when P11 lands. — settled: A**
- A. Accept (the return is the one rooms write with no guidance today, which reads as an
  omission).
- B. Add a flag that skips guidance and keeps the old heading (saving drops from −12 to −8).
- C. Leave the duplicate.
- Lean: **A**.

**D14 — Rename `SceneRecord.question` → `focus`. — settled: A** (E) Rooms store a place brief there;
`NarratorView.focus` already exists for the same slot.
- A. Rename (touches `play.py`, `views.py`, both worlds, tests; saves stale).
- B. Leave, one docstring line.
- Lean: **B now, A in the next stale-save pass.**

**D15 — A content library object. — settled: B** (D) Nine sites thread `settings.scenarios_dir/
characters_dir/saves_dir` by hand.
- A. Keep the free functions on `Path` (the rule allows them; a `Path` is not ours).
- B. A frozen `Library(scenarios, characters)` beside `FileStore` with the readers and writers
  as methods, built once in `Runtime.__post_init__`. −12 argument threads, +20/−25 lines, six
  files and `test_store.py`'s eight calls.
- Lean: **B**; `FileStore` already set the precedent for the saves directory.

**D16 — `begin_game` → `Engine.begin`, `launch_target` → `LauncherCatalog.target`. — settled: A** (B)
- A. Do it (CLAUDE.md's method rule; `registry.py` becomes 13 lines).
- B. Leave (`begin_game` is the composition root's one verb).
- Lean: **A**, folded into D2 if D2 is A.

**D17 — `GameService.play` and presentation. — settled: A** (A, D, B)
- A. Extract `_run_master(turn)` (the master + commission loop) and `_present(state)`; keep
  media in the service. +3 lines, `play` reads as six steps.
- B. Move illustration and speech scheduling to the page's `poll_turn` on history growth; the
  service loses seven methods and `_background`; art starts up to a second later.
- C. Leave.
- Lean: **A**.

**D18 — `config.py` models on `Frozen`. — settled: A** (B)
- A. Switch the four sub-models to `Frozen` (`extra="forbid"`): a `.env` typo in a nested key
  fails at start instead of vanishing; `Settings` itself stays `extra="ignore"` for the shell's
  unrelated keys. Needs `aidm.config` to import `aidm.core.entities` (allowed: the boundary test
  restricts who imports config, not what it imports) and one manual run with a deliberate typo.
- B. Leave.
- Lean: **A after the manual check.**

**D19 — `Engine.crossing()` as a behaviour switch. — settled: A** (lead, B)
- A. One docstring line on `GameService.play` naming the contract ("None means the world grows
  without a turn").
- B. An explicit `Engine.crosses: bool` beside `crossing()` returning `str`.
- Lean: **A**; two users, one None.

**D20 — `AGENTS.md`. — settled: moot, already a symlink** (fact 5)
- A. A symlink to `CLAUDE.md` (git stores symlinks; Codex reads it).
- B. Delete it (Codex loses the rules).
- C. Keep two copies and accept drift.
- Lean: **A**.

Leans everyone shares, listed so they need no round: keep the twelve empty envelope subclasses;
keep the reflective settings page; keep `PanelRow`'s three shapes with one comment on the branch
order; keep `NarratorView.place` with its existing comment; keep the single-overrider hooks;
keep the wording-asserting tests (the strings are load-bearing prompts); `CatalogEntry.kind`
defaults to `None` for characters; write the three id types' rule into `entities.py`; fix the
Breathless count in NEXT-SPECS decision 4 (13, not 12).

---

## 7. What must not be simplified, and what protects it (agreed by all six)

- **A. Folding engines together or the three scene engines into one with a mode.** Each SRD's
  own ladder, tools and documented deviations; NEXT-SPECS decision 4 "no fold is made for the
  count's sake"; `tests/core/fixtures/schemas/*/master_tools.json` pins each surface.
- **B. Merging the scene and room families.** A room is a place with directed ways, locks, a
  frontier and holders; a scene is a titled question with a cast list; the map bar
  (`_map_unmet`: shortcut, locked way, reachability) has no scene analogue. `test_rooms.py`,
  `tests/tunnelgoons/test_worldsmith.py`.
- **C. The transactional draft** (`draft/commit`, `Turn._apply`'s candidate and dice copy). A
  refused call leaves state and dice alone (`test_turn.py:298,143`), a crashed master keeps
  only what landed (`:186,205`), mutation lands only at commit (`test_integrity_boundaries.py:122`).
- **D. Typed proposals over free text.** The bars, the leak checks on `debrief`/`situation`/
  `question`, pydantic's minimum lengths, the one re-prompt with the error; NEXT-SPECS refuses
  the flat draft.
- **E. `NarratorView` and `PlayerView` as two types.** `test_context_boundary.py:43-59` pins the
  narrator's closed field set; `PlayerView` carries `prompt`, `over` and panels the narrator
  must never be handed. CLAUDE.md: "Hidden facts have no path into it."
- **F. `Refusal` as the one message-bearing exception.** `working()`, `on_call_tool` and
  `read_catalog` each show, return or skip `Refusal` only; a bug propagates
  (`test_master_tools.py:114`).
- **G. `Engine` as an ABC.** It carries concrete shared behaviour a Protocol cannot hold, and
  `abstractmethod` makes a fifth engine fail at construction (`test_seam.py:102`).
- **H. The generics.** Pydantic's runtime parametrisation is what puts the engine's cast type
  into the worldsmith's schema (`HubDraft[self.cast]`, `MapDraft[self.dweller]`) and revalidates
  a save as the engine's own people; NEXT-SPECS decision 1.
- **I. The golden schema tests.** The only test of what MCP publishes per engine.
- **J. Prompt text in `.md` files.** `rules.md` carries the licence attribution the docs cite;
  ruff formats fenced code in `.md`.
- **K. MCP as the master's tool surface.** The design is spawned CLIs reaching the live game
  over HTTP; in-process calls were refused.
- **L. The commission** (`Commission`, `later`, `fulfil`, one per turn). Landed Phase 2;
  `test_turn.py:268,282,366`, `test_game_service.py:118,160`.
- **M. `Job.attempts` (reopening) and the three-depth history.** NEXT-SPECS decisions 2 and 5;
  `test_hub.py:303-420`, `test_views.py:67-127`.
- **N. `Counter`, `DiceEvent`, `Fact.dice`.** Bounds at commit, one card format for every pool
  move, the UI's dice row and kept-die highlight.
- **O. The package-boundary test.** The only mechanical enforcement of `core <- engines <- turn
  <- app <- ui` and "ui names no engine".
- **P. `SCENE_EXCHANGES` as a constant, `NarratorView`'s field set, the `.mcp.json` port
  coupling** — each recorded in NEXT-SPECS or a comment; not knobs.
