# Proposals: code quality and consistency before MVP0

Sources: a full read of `src/aidm` plus two independent reviews (structure, idiom); every ref was
checked against the source. Each entry is "Now / Change"; unsure ones carry "Decision" with
options. Size: S under 30 min, M one to two hours, L half a day. Ordered by how much a senior
Python reader would care, so groups of three close in order.

## A. Error contract

### 1. OSError and TimeoutError leak past the spawn and HTTP edges (M)

Now: `app/spawn.py:226-244` lets `FileNotFoundError` (no `claude`/`codex` binary) and
`TimeoutError` from `wait_for` escape; `app/builtin.py:56` `async with timeout(...)` raises
`TimeoutError` too. So seven sites spell `except (OSError, Refusal)`: `app/roles.py:64,70,102`,
`app/runtime.py:178,216`, `ui/create.py:266`, `ui/game.py:584`; `ui/game.py:585` prints
`type(error).__name__` because it does not know what it caught. CLAUDE.md: any exception but a
`Refusal` is a bug and is not caught.
Change: convert at the edge. `_spawn`: `except OSError as failed: raise Refusal(f"the {role}
could not be started: {failed}")`, `except TimeoutError: raise Refusal(f"the {role} answered
nothing in {timeout:.0f}s")`. Same in `run_builtin`. Every other site catches `Refusal` only.
Decided: yes.

### 2. An uploaded source document fails as a bug (S)

Now: `core/source.py:24` `read_text(encoding="utf-8")` raises `UnicodeDecodeError` on a Latin-1
`.txt`; `:36` `PdfReader(path).pages` raises `pypdf.errors.PdfReadError`. `ui/create.py:266`
catches neither, so the page shows nothing. `core/io.py:170-172` already converts the first.
Change: in `whole_text`: `except (UnicodeDecodeError, PyPdfError) as broken: raise
Refusal(f"{path.name} cannot be read: {broken}") from broken`.
Decided: yes.

### 3. `Refusal` is a `ValueError`, and refusal helpers run inside validators (S or M)

Now: `core/entities.py:37` `class Refusal(ValueError)`. `check_unique` raises `Refusal` and is
called from `@model_validator`s (`core/model.py:68,108`, `core/play.py:90`,
`rooms/world.py:44,56,124`, `scenes/world.py:64,258`) and from rules code (`rooms/world.py:184,221`,
`loner3e/world.py:59`, `twentyfourxx/world.py:104`, `core/io.py:186`). `check_filing`
(`base.py:279`) raises `ValueError` for the same job. CLAUDE.md's "inside a validator raise
`ValueError`" holds by inheritance, not by the code, and any `except ValueError` can swallow a
`Refusal` (see 4).
Decision:
- A (S): keep `Refusal(ValueError)`; its docstring says validators may raise it; `check_filing`
  raises `Refusal` for symmetry; one line in CLAUDE.md.
- B (M): `Refusal(Exception)`; `check_unique` raises `ValueError`; the five rules-code callers
  wrap it. The two error kinds become disjoint, as CLAUDE.md describes.
Decided: A.

### 4. Media and speech catch `ValueError`, which hides validation errors and refusals (S)

Now: `app/media.py:124` `except (HTTPError, ValueError)`; `app/speech.py:65`
`except (HTTPError, OSError, ValueError, wave.Error)`, both `LOGGER.exception`. `ValueError`
covers `_ImageReply.model_validate_json` (`:119`) and `b64decode` (`:207`); `app/spawn.py:85-88`
hand-converts the same `ValidationError` into a `Refusal`.
Change: `parse_json[T: BaseModel](model, raw: str | bytes) -> T` beside `parse` in
`core/entities.py`, used at `media.py:119` and `spawn.py:86`; `_decode` wraps `b64decode` with
`except binascii.Error: raise Refusal(...)`. Then media catches `(HTTPError, Refusal)` and speech
`(HTTPError, Refusal, wave.Error)`.
Decision: keep `OSError` on `speech.py:65` (a full disk is not a bug) or drop it.

### 5. Packaging errors raised as refusals (S)

Now: `scenes/engine.py:237-241` `srd_pack()` raises `Refusal("the SRD table set is not
installed")`; `loner3e/engine.py:146-152` `twist_table()` raises `Refusal("... has no twist
columns")`. Both mean a broken install, not a message a role or player reads.
Change: check once in `SceneEngine.__init__` (`ValueError` if `SRD_PACK` is missing); `srd_pack()`
becomes `self.packs[SRD_PACK]`. `Loner3eEngine.__init__` checks the twist columns the same way.

## B. Where rules live

### 6. State mutation is split between world methods and engine tool bodies (L)

Now: most rules mutate through entity or world methods (`TunnelGoonsWorld.rest`,
`TwentyfourxxWorld.defend/upgrade_ship/take_lead`, `Crewmate.gain_item/repair_item/spend`,
`Loner3eSheet.change_tags/drive/refill`, `Survivor.change_stress/use_med_kit/take_loot`, all of
`RoomWorld`/`SceneWorld`). But engine tool bodies also write fields directly:
`breathless/engine.py:236,246-254` (`sheet.worn[...]`, `del sheet.items[...]`, `item.die`,
`sheet.stunted`), `:281-283` (`catch_breath` resets three fields), `:312` (`sheet.loot`);
`tunnelgoons/engine.py:214-220` (`level_up` writes five fields, `hp.maximum += 1`,
`hp.current += 1` past `Counter.adjust`); `twentyfourxx/engine.py:389` (`MAIMED` appended),
`:432,479,485,494` (`world.job`, `sheet.skills[...]`, `sheet.credits`); `loner3e/engine.py:211-213`
(`world.twist.current`).
Change: one rule: an engine tool method resolves ids and rolls dice; a world or entity method
changes fields and writes the facts. Add `SurvivorSheet.wear(skill)`, `.spend_stunt()`,
`.rested()`, `Goon.level(ability, boost)`, `Crewmate.maimed()`, `Sheet.raise_skill(label)`,
`Sheet.earn(n)`, `TwentyfourxxWorld.take_job/finish_job`, `Loner3eWorld.tick_twist() -> bool`.
The four `roll` methods keep only dice and card lines.

### 7. Argument-shape rules sit in a validator for some tools and in the resolver for others (S)

Now: validators: `Check._one_thing` (`breathless/tools.py:46-52`), `ActionRoll._one_target`
(`tunnelgoons/tools.py:35-39`), `ChangeHindrances._some_change`, `Job._fields_for_verb`
(`twentyfourxx/tools.py:23-27,119-125`). The same kind of rule as a resolver `Refusal`:
`NextScene` "not both" (`scenes/engine.py:214-215`); `LevelUp` "both or neither"
(`tunnelgoons/engine.py:210-211`); `ChangeTags` "at least one" (`loner3e/world.py:57-58`); `Drive`
"needs a goal, a motive or a nemesis" (`:79-80`); `ChangeStress` "non-zero"
(`breathless/world.py:106-107`).
Change: `model_validator`s on `NextScene`, `LevelUp`, `ChangeTags`, `Drive`; `ChangeStress.amount:
int = Field(ne=0, ...)`. Resolvers and world methods then check state only.

### 8. `leaving(state)` mutates through a parameter named `state` (S)

Now: `SceneEngine.leaving(self, _state: G)` (`scenes/engine.py:312`) reads as read-only, but
`Loner3eEngine.leaving` (`loner3e/engine.py:154-161`) calls `member.refill(...)`, which writes
`luck.current`. Everywhere else `draft` names what a call changes and `state` what it reads.
Change: the hook takes `draft`; its docstring says it may change the draft.

## C. Layers

### 9. `app` knows the world's entity shape (M)

Now: `app/runtime.py:23` imports `Chattiness, Person` from `engines.base`; `GameService.interject`
(`:164-193`) walks `engine.world(state).members()` and reads `candidate.chattiness`;
`app/roles.py:18` imports `Person` and `Roles.interject` (`:110-123`) calls `member.subject()`,
`member.rows()`, `member.id`, `member.name`. CLAUDE.md: `app` knows no world shape. The leak point
is `Engine.world()` being called from `app` (`runtime.py:168`), the only call outside `engines`.
Change: `core/views.py` gets `class Companion(Frozen): id, label, detail, sheet: Pairs,
chattiness`; `Chattiness` moves to `core`; `Engine.companions(state) -> tuple[Companion, ...]` on
the seam; `Roles.interject` takes a `Companion`; `GameService` picks from
`engine.companions(state)`. `app` then imports nothing from `engines.base`.

### 10. The UI names engines (M)

Now: `ui/theme.py:47-107` keys `THEMES` by `EngineId("loner3e")`, `"tunnelgoons"`,
`"breathless"`, `"twentyfourxx"` ("the one place the UI names an engine"). Each engine already
carries presentation as `art_style` (`seam.py:46`), read by `app/runtime.py:414`. CLAUDE.md: the
registry is the one join point. A fifth engine touches `registry.py` and `theme.py`.
Decision:
- A: `Engine.look: Look` (palette overrides + `DiceLook`, both `Frozen` in `core`) next to
  `art_style`; `theme.set_engine(look)` and `dice_look(look)` take the look, not the id.
- B: move `art_style` out to `ui/theme.py` beside the palette, so engines carry no presentation.
A is smaller and matches the precedent.

## D. API shape

### 11. Results returned as positional tuples; `DiceEvent` hand-built five times (M)

Now: `type Written = tuple[tuple[Fact, ...], str | None]` (`seam.py:31`); `roll() ->
tuple[tuple[int, ...], Fact]` (`core/facts.py:47`); `roll_pool() -> tuple[int, DiceEvent, Fact]`
(`:56`); loner3e `_pair() -> ` a 5-tuple (`loner3e/engine.py:278`). Because `roll` returns no
`DiceEvent`, engines build one by hand at `tunnelgoons/engine.py:188`,
`twentyfourxx/engine.py:424,491`, `breathless/engine.py:324`, `loner3e/engine.py:230`, with the
label spelled five ways; both `roll_pool` callers re-derive `"+".join(f"d{f}" ...)` that
`core/facts._notation` already computes.
Change: `class Rolled(Frozen): faces, rolled, kept, event, fact` returned by one `roll(faces,
reason, rng, *, label: str = "")` (label defaults to the notation); `roll_pool` becomes the
keep-highest variant on top of it or is deleted. `Written` becomes a frozen dataclass
`Written(facts, telling)`. Delete the five hand-built events.

### 12. Boolean-flag methods and parameters (M)

- `SceneWorld.require_here(entity_id, *, alive=False)` (`scenes/world.py:112`); loner3e passes
  `alive=True` seven times. → `require_here` and `require_living_here`.
- `Roles.narrate(..., *, fatal: bool)` (`app/roles.py:74-108`): the flag selects error handling.
  → `narrate` always raises; the two tolerant callers (`runtime.py:100,214`) wrap it in
  `try/except Refusal: LOGGER.warning(...); lines = ()`.
- `GameService._generate(words: str = "")` (`runtime.py:195`): the emptiness of a string decides
  the mark, the prompt and what the return value means. → `_write_requested(words) -> bool` and
  `_write_after_turn() -> None` over one `_advance(draft, request)`.
- `GamePage.submit(acting: bool = False)` (`ui/game.py:484`). → `submit()` and `act()` sharing
  `_send(typed, playing)`.
- `mcp._content(body, error: bool = False)` (`app/mcp.py:95`). → keyword-only.

### 13. A part emits facts about its owner by being handed the owner (M)

Now: `Counter.change(self, owner: Thing, amount, label, why)` (`base.py:230`);
`ItemSheet.drop_item(item_id, owner: Thing)` (`base.py:138`); `Abilities.rows(hp: Counter)`
(`tunnelgoons/world.py:31`).
Decision:
- A: keep; smallest code, and the fact needs `owner.mention`.
- B: owner methods: `Thing.change(gauge, amount, label, why)`, `Person.drop_item(item_id)`; the
  gauge and the sheet stop knowing `Fact`.

### 14. `list[Fact]` and `tuple[Fact, ...]` mixed on fact-returning APIs (S)

Now: tool methods, `Thing.reveal`, `Counter.change`, `luck_test` return `list[Fact]`;
`SceneEngine.leaving` returns a tuple (`scenes/engine.py:312`) while its sibling `install` returns
a list (`:261`); `Engine.answer` returns a tuple (`seam.py:89`); `depart` splices
`(*self.leaving(draft), *self.install(...))` to reconcile (`:300`).
Change: rules code returns `list[Fact]`; tuples only in frozen models (`Exchange.facts`) and at
the `Play`/`Written` boundary, where `master_tool` and `advance` already convert. `leaving` and
`Engine.answer` return lists.

### 15. Property vs method has no rule (S)

Now: `Thing.mention/tag/headline/met_label` are properties; `Thing.subject()/rows()/line()`
methods; `Gear.broken` property but `Gear.detail()` method; `Person.hired()/hireable()` methods
next to `SurvivorSheet.vulnerable`, a property.
Change: property = no arguments, no side effect, derived from own fields. `hired`/`hireable` →
properties; `Gear.detail()` → `Gear.notes()` (a `detail` property would collide with the
`detail` naming rule).

### 16. Pack ids and widget values cross boundaries as unchecked `str` (S)

Now: `scenes/packs.py:17-21` keys packs by `path.stem`, `dict[str, P]`; `scenes/engine.py:94`
`packs: dict[str, K]`, while `Game.packs`/`Scenario.packs` are `tuple[Slug, ...]`. `ui/create.py:262`
passes `self.packs.value` as `Sequence[Slug]` and `:242` `self.character.value` as `Slug`;
`ui/app.py:38,42` already narrow with `content_id`. The upload's `mkdtemp()` (`ui/create.py:174`)
is never removed.
Change: `content_id(path.stem)` and `dict[Slug, ...]` in `read_packs`/`SceneEngine`;
`content_id(...)` on both widget values before calling the runtime; delete the temp dir in
`write`'s `finally`.
Decision on `Slug` itself: A) keep `Annotated[str, ...]` (checked at runtime only); B)
`Annotated[NewType("Slug", str), ...]` so the checker refuses a bare `str`, at the cost of wrapping
every literal (`id="take"`, `PLAYER_ID`). A unless the boundary keeps leaking.

### 17. The two worldsmith drafts differ in mutability (S or L)

Now: `MapDraft(Dungeon)` is `Mutable` (`rooms/world.py:33,109`) and installed by reference
(`RoomWorld.attach`, `:313-322`). `SceneDraft` is `Frozen` (`scenes/tools.py:44`) but holds
`cast: dict[Slug, C]` of `Mutable` persons, so `frozen` guarantees nothing: `settled()` writes
`cast[id].known = True` (`scenes/world.py:246`), which forced `model_copy(deep=True)` at
`scenes/engine.py:117,265` with comments explaining why.
Decision:
- A (S): both drafts `Mutable`, installed by reference after the check passes; one deep copy at
  the top of `new_game` only (a scenario file is reopened on restart).
- B (L): both `Frozen`, with entity classes split into a frozen authored shape and a mutable
  played shape. Honest, but doubles the entity classes.

## E. Naming

### 18. `Sheeted.dice()` returns the sheet (S)

Now: `base.py:109-113` `def dice(self) -> S` returns `self.sheet` or refuses; call sites read
`actor.dice().items`, `actor.dice().credits`, `sheet = actor.dice()`.
Change: `require_sheet()`, matching `require_actor`, `require_member_here`, `require_place`,
`require_gear`.

### 19. Four names for the `roll` tool's arguments (S)

Now: `Question` (`loner3e/tools.py:50`), `Check` (`breathless/tools.py:27`), `Roll`
(`twentyfourxx/tools.py:74`), `ActionRoll` (`tunnelgoons/tools.py:15`).
Change: `Roll` in all four.

### 20. Person and sheet class names follow no rule (S)

Now: breathless `Survivor` + `SurvivorSheet`; 24xx `Crewmate` + `Sheet`; tunnelgoons
`Goon`/`Npc` + `Abilities`; loner3e `Loner3eSheet` is the person (a `Person` subclass, no sheet).
Change: person is a noun, dice sheet is `<Noun>Sheet`: `Sheet` → `CrewSheet`, `Abilities` →
`GoonSheet`, `Loner3eSheet` → `Loner`.
Decision: `Loner` vs `Loner3eCast` for the loner3e person.

### 21. Three names for the npc type across one hierarchy (S)

Now: `SceneEngine.cast: type[C]` (`scenes/engine.py:91`), `RoomEngine.dweller: type[N]`
(`rooms/engine.py:63`), `Hiring.member: type[M]` (`hiring.py:47`); every hiring engine sets two of
them to the same class (`breathless/engine.py:63,66`, `twentyfourxx/engine.py:71,74`,
`tunnelgoons/engine.py:73,75`). `member` exists only for the `isinstance` at `hiring.py:86`.
Change: one `Engine.member: type[M]` on the seam, used by both families and `Hiring`; drop `cast`
and `dweller`.

### 22. `Library` calls an id `name`; two verbs for file IO (S)

Now: `core/io.py:56-58,105,112,139` `scenario_folder(self, name: Slug)`, `read_scenario(self,
name, ...)`, `write_scenario(self, name, ...)`, `character_folder(self, name)`; CLAUDE.md reserves
`name` for the display string on disk. `FileStore.load/save/discard` (`:33-44`) vs
`Library.read_*/write_*` (`:66-139`).
Change: `scenario_id`/`character_id`; `FileStore.read/write` (matches `read_prompt`, `write_text`).

### 23. One idea, five names: the callable that refuses a bad model answer (S)

Now: `Objection[T]` (`core/model.py:16`); parameter `refusal: Objection[M]` (`WorldsmithAnswer`,
`spawn.ask:191`); `playable: Callable[[AnyScenario], None]` (`seam.py:98,215`,
`runtime.py:372,380`); `hire_bar()` (`hiring.py:80`); "bar" in docstrings
(`scenes/worldsmith.py:40`, `seam.py:129`, `rooms/world.py:323`).
Change: `type Check[T] = Callable[[T], None]`; parameters named `check`; `hire_check()`; delete
"bar" from docstrings.

### 24. `prompt` names four things (M)

Now: `PlayerView.prompt: PendingDecision | None` (`core/views.py:117`); `Exchange.prompt` and
`Turn.prompt` (the player's words); `PendingDecision.prompt` (the question); `CreationStep.prompt`
(a field label); `Spawner.run(prompt)` (the model prompt). `ui/game.py:608` reads `prompt =
player.prompt` then `prompt.allows_text`.
Change: `PlayerView.prompt` → `decision`; `CreationStep.prompt` → `label` (CLAUDE.md: shown
names are `id`, `label`, `detail`); `Exchange.prompt`/`Turn.prompt` → `words`. Leave
`PendingDecision.prompt` and the model prompt. (`Exchange` is saved to disk: existing saves become
stale, which CLAUDE.md allows.)

### 25. `engines.base.Counter` collides with `collections.Counter` (S)

Now: `base.py:210` `class Counter(Mutable)` is a bounded gauge; `core/entities.py:2` imports the
stdlib one `as Tally` to dodge it; `twentyfourxx/engine.py:1` imports `collections.Counter` into a
module that also reads `hp`/`luck` gauges.
Change: `Counter` → `Gauge`; drop the `as Tally` alias.

### 26. Naming rule slips and small renames (S)

- `Generation.brief` (`core/model.py:90`) is never saved (`exclude=True`) and only the worldsmith
  reads it. → `detail`.
- `Outcome.name: Slug` (`loner3e/tools.py:79`) is a key. → `id`.
- `SaveOption.scenario_title`/`character_title` (`app/launch.py:35-36`) sit next to
  `CatalogEntry.label`. → `scenario_label`/`character_label`.
- `Thing.fact(narrate=...)` (`base.py:59-69`): no caller passes it. Delete; `told=self.known`.
- `ScenarioForm.took` (`ui/create.py:172`) is the upload handler. → `uploaded`.
- `RoomWorld.begin` vs `SceneWorld.opening` (`rooms/world.py:135`, `scenes/world.py:76`): same
  role, and `Engine.begin` already means "start a game". → `opening` in both.
- `GameService.engine_title`/`engine_id` (`runtime.py:82-88`) forward `engine.title`/`engine.id`.
  Delete; the UI reads `session.engine.title`.
- `TwentyfourxxEngine.kill(self, draft, args, _rng)` (`twentyfourxx/engine.py:285`) uses `_rng`.
  → `rng`.
- `Loner3eEngine.meanings()`/`twist_table()` return `tuple[tuple[str, str], ...]`. → `Pairs`.
- `complications()` (`breathless/engine.py:173`) and `meanings()` (`loner3e/engine.py:135`) are
  called only inside their class and by no test. → `_complications`, `_meanings`.

## F. Consistency across engines

### 27. Concrete engines reach `draft.payload`; family bases use `self.world(draft)` (S or M)

Now: 34 uses of `draft.payload`/`state.payload` in the four concrete `engine.py` files; 0 calls
to `self.world()` there; the families and `Hiring` use `world()` throughout. `world()` is abstract
on the seam so it owns that mapping. Cause: `SceneEngine.world()` returns `SceneWorld[C]`, so
`Loner3eWorld.twist` and `TwentyfourxxWorld.job` are unreachable through it.
Decision:
- A (M): a world type parameter, `SceneEngine[C, G, K, W: SceneWorld[C]]`, `world_type: type[W]`,
  `world() -> W`; every engine uses `self.world(draft)`; `payload` is read in the two family
  `world()` methods only.
- B (S): keep both and write the rule in CLAUDE.md: a family base uses `world()`, a concrete
  engine uses `payload`.
Also: `world_type` is the one type attribute not named as a bare noun (`game`, `scenario`,
`character`, `member`...). With A, rename the method `world_of(draft)` and the attribute `world`,
or accept the exception.

### 28. `Reveal`/`Kill` duplicated per family; four identical wrappers; `kill` takes an object in one family and an id in the other (M)

Now: `Reveal`/`Kill` declared in `rooms/tools.py:12-22` and `scenes/tools.py:17-30` with the same
single field; `twentyfourxx/engine.py:17` imports `Kill` from `scenes.tools`; `JoinParty`/`LeaveParty`
already live once in `base.py`. The wrappers `reveal`, `kill`, `join_party`, `leave_party` are the
same lines in `rooms/engine.py:206-220` and `scenes/engine.py:195-211`, except `RoomWorld.kill(actor:
P | N)` (`rooms/world.py:298`) vs `SceneWorld.kill(entity_id)` (`scenes/world.py:192`);
`tunnelgoons/engine.py:197,201` pass objects, `twentyfourxx/engine.py:387` passes an id.
Change: move `Reveal`, `Kill`, `REVEAL`, `KILL` to `base.py` beside `JoinParty`; declare
`reveal_hidden`, `kill`, `join_party`, `leave_party` (all by id) abstract on `World`; `RoomWorld.kill`
takes an id; the four wrappers and their `master_tool` entries move to `Engine.master_tools()`.
Families then add only their own tools.

### 29. Tool descriptions live in two places (S)

Now: 29 descriptions are constants in `tools.py` beside their args model; 11 are inline literals
in `master_tools()` (every `roll`, `test_luck`, `catch_breath`, `loot_check`, `level_up`, `job`,
`rest`); `hire`'s is `HIRE_TOOL` in `hiring.py`. `tunnelgoons/engine.py:81` passes the config base
class `Frozen` as the no-argument schema while breathless declares `Actor`.
Change: every description is a constant in the module of its args model, named after the tool
(`ROLL`, `TEST_LUCK`, `HIRE`); `class NoArgs(Frozen)` in `core/tools.py` for `rest`.

### 30. Four `roll` methods, four shapes, 42 to 65 lines each (M, with 6)

Now: `loner3e/engine.py:174-215` ends by patching a fact in place (`facts[answered_at] =
...model_copy(...)`); `breathless/engine.py:187-252` carries `helper: tuple[Survivor, Die] | None`
and re-branches on skill/item/stunt twice; `twentyfourxx/engine.py:340-394`;
`tunnelgoons/engine.py:167-212`. Each mixes: resolve actor and dice, roll, format the line, apply
the consequence.
Change: one shape in all four: `_pool(world, actor, args)` (die, label, extras), roll, `_line(...)`,
`_consequence(...)`. Breathless gets a frozen `_Pool(die, label, item, helper)` and
`_wear(sheet, pool)`; loner3e builds the oracle fact after the exchange so nothing is patched.

### 31. `loner3e/tools.py` holds rules and prompt text the other engines keep elsewhere (S)

Now: `loner3e/tools.py` carries `TOLD`, `AND_AT`, `BUT_AT`, `Outcome`, `outcome_for`,
`twist_pairing` (rules, `:11-20,78-102`), `twist_note`, `defeat_note` (master prompt text,
`:105-119`) and `pack_meanings`. The other engines keep rule helpers in `world.py`
(`breathless/world.py:167-173`, `twentyfourxx/world.py:233-238`) and prompt text as constants in
`engine.py`/`worldsmith.py` (`SIGNED_ON` in `hiring.py:16`).
Change: rules to `loner3e/world.py`; `twist_note`/`defeat_note` to `engine.py` as `TWIST_NOTE`/
`DEFEAT_NOTE` format strings. `tools.py` then holds args models and descriptions only.

### 32. The player's items are listed once in breathless and twice in 24XX; the sheet rows are owned by the World in rooms and by the Person in scenes (M)

Now: breathless keeps items out of `SurvivorSheet.rows()` and prints them as the BACKPACK section
and panel (`breathless/engine.py:159-171`), overriding `Survivor.line` for it
(`breathless/world.py:145-154`); 24XX puts a Gear row into `Crewmate.rows()`
(`twentyfourxx/world.py:145-152`) and also prints a GEAR section (`twentyfourxx/engine.py:218`), so
the master reads the gear twice. `preview_character` is overridden to append items in breathless
(`:146`) and tunnelgoons (`:131`), not in 24XX. Rooms reads the sheet via `RoomWorld.sheet_rows()`
(`rooms/world.py:366`, overridden by `TunnelGoonsWorld`); scenes reads `world.player.rows()`
(`scenes/engine.py:159,171`).
Change: `rows()` is the sheet without inventory; inventory is a `sheet_sections` section, a panel
and a `preview_character` row, in all three sheeted engines; drop the Gear row from
`Crewmate.rows()`; delete the `Survivor.line` override. `sheet_rows()` moves to `World` in
`base.py` (default `self.player.rows()`), read by both families' views.

### 33. `TwentyfourxxEngine._finish` and `scene_unmet` hide their structure (S)

Now: `twentyfourxx/engine.py:435-495` (60 lines) nests `def named` inside an `if` and builds three
sorted lists; `scenes/worldsmith.py:39-88` (50 lines, eight checks) reuses the walrus name `named`
for two different lists (`:50`, `:66`).
Change: `_operators_unmet(expected, got) -> str` (empty when fine) so `_finish` reads `if unmet
:= ...: raise Refusal(...)`; split `scene_unmet` into `_listing_unmet`, `_cast_unmet`,
`_hidden_unmet`, concatenated, as `rooms/worldsmith.py:30-36` already does.

### 34. Party-membership validation is written twice (S)

Now: `rooms/world.py:118-133` `_playable` and `scenes/world.py:64-73` `_consistent` both check
that party ids are unique, known, alive and with the player.
Decision:
- A: lift the shared part to a `World` validator with an abstract `member_of(id) -> M | None`; the
  "with the player" test stays per family.
- B: leave; the shared part is four lines and the families differ (place vs scene).

### 35. Small duplications with exactly two users (S)

- `drop_item` wrapper: `breathless/engine.py:177-179` and `twentyfourxx/engine.py:264-266` are
  identical; `DROP_ITEM`/`DropItem` already sit in `hiring.py:23,39`. → the tool and wrapper on
  `Hiring`, published when the member class carries an `ItemSheet`.
- Pack-content guidance `f"{AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"` at
  `breathless/engine.py:150-157` and `loner3e/engine.py:120-126`. → `SceneEngine.pack_content(picks,
  *, include=None, exclude_defaults=False)`.
- "The first pack" `self.packs[draft.packs[0]]` at `breathless/engine.py:188` and
  `twentyfourxx/engine.py:337`. → `SceneEngine.first_pack(draft)`.
- `{engine_id: engine.scenario for ...}` at `app/launch.py:67` and `app/runtime.py:398`. →
  `Runtime.scenario_models()`.
- `claim(generating, key)` in `app/providers.py:9-14` has nothing to do with providers; `media.py:41`
  and `speech.py:30` each hold `generating: set[str]` and pair `claim` with `discard` in a
  `finally` (three sites). → `class Claims` (`claim(key) -> bool`, `release(key)`) next to its first
  user; `providers.py` keeps `post_bearer` only.

### 36. Chapter handling differs between the families (S)

Now: `RoomEngine.move` pops `draft.log[-1]` when it has no exchanges before `open_chapter`
(`rooms/engine.py:227-229`); `SceneEngine.install` always appends (`scenes/engine.py:266`), so an
install that lands on an empty chapter (a failed opening narration, then a complication) keeps
the empty one in the save.
Change: the pop moves into `Engine.open_chapter` (`seam.py:165-168`); delete it from `move`.

### 37. Spelling drift (S)

- Type aliases: `type X = ...` in 24 places; bare `TagKind = Literal[...]` (`loner3e/world.py:18`),
  `Ability`, `AbilityScores`, `Boost` (`tunnelgoons/world.py:13-16`). → `type` for those four;
  `Slug` stays `Annotated` with a one-line comment (pydantic reads the metadata).
- Mutable defaults: `core/model.py:102` `notes: list[str] = []` beside `:103`
  `Field(default_factory=list)`; `core/play.py:75` `args: dict = {}`. → `default_factory`.
- `LOGGER` after constants in `core/io.py:20`, `app/spawn.py:25`, `ui/game.py:65`; before them in
  `app/runtime.py`, `app/media.py`, `app/speech.py`, `app/roles.py`. → first line after imports.
- Underscore constants: `_STEP_COPY`, `_DICTATION_FAILURES`, `_STATIC_CSS`, `_EVENT`, `_BLANK_LINE`,
  `_LINE_BREAK_HYPHEN`, `_SAVE_SLUG_PATTERN`; every other module-private constant is bare.
  Decision: no underscore on constants, or underscore on every constant unused outside.
- `→` in six trace/card strings, `->` in four (`base.py:237,293`, `twentyfourxx/engine.py:489-490`).
  → `→`.
- `Pairs` is defined in `core/views.py:16` but is a prompt type; `core/prompt.py` imports views
  only for it. → move to `core/prompt.py`.

### 38. `Hiring` is a four-parameter mixin whose tool order depends on the MRO (S or M)

Now: `hiring.py:46` `class Hiring[P, M, G, A](Engine[P, G])`; engines declare
`class BreathlessEngine(Hiring[...], SceneEngine[...])` and `super().master_tools()` walks
`Hiring → SceneEngine → Engine`. The docstring "family, then hire, then the engine" is true only
because of that order.
Decision:
- A (S): keep; one line on `Hiring`: "listed first so its tools follow the family's".
- B (M): fold hiring into `Engine` as an optional feature (`hire_answer: type[A] | None = None`);
  no mixin, no MRO.

## G. Ceremony, comments, tests

### 39. Free functions and parameters that use nothing (S)

- `Engine.compose` (`seam.py:97-105`) never touches `self`. → a free `compose(...)` in `seam.py`.
- `render_master(..., state, scenes, ...)` (`turn/run.py:145`): `scenes` is always `state.log`.
  → drop it.
- `app/builtin.py:58` `tools if role == "master" else None` re-decides what the caller decided. →
  drop the test.
- `Roles.master` (`app/roles.py:58-72`) writes the same `try/await/except` twice for one retry;
  `_landed` logs inside a predicate. → a `for attempt in (1, 2)` loop; log at the call site.
- `turn/run.py:63-64,80-81` repeat `'The rules paused play to ask the player: "{prompt}"'`. → one
  constant.
- `ui/theme.py:464` `@cache` on a zero-argument `None` procedure means "run once". → call
  `_install()` once from `start()`.
- `LauncherCatalog.read` (`app/launch.py:63-121`) is a 60-line classmethod with four `continue`s.
  → `_save_option(...) -> SaveOption | None` holds the loop body.
- `WORLDSMITH_PROMPT`/`RULES_PROMPT = Path(__file__).parent / ...` repeated at
  `rooms/engine.py:49-50` and `scenes/engine.py:58-59`. → `Engine.__init__` derives both from a
  `family_dir: Path` attribute.

### 40. Docstrings and comments (S)

- `twentyfourxx/world.py:209` `"""Decision 6: ids are kept. ..."""` cites the deleted PLAN.md. →
  `"""The new lead keeps their id; the dead lead is filed in the cast under theirs."""`.
- "Free:"/"free because" docstrings (`scenes/world.py:241`, `scenes/worldsmith.py:34`,
  `app/providers.py:20`, `app/media.py:169`) justify a CLAUDE.md rule, not the code.
  Decision: drop the clause or keep it.

### 41. Tests reach private state (S)

Now: `tests/support/table.py:262` `service._background`; `tests/app/test_game_service.py:395,404`
`service._speaking`, `:420` `_retain`; `tests/turn/test_turn.py:284`,
`tests/turn/test_decisions.py:175` `turn._apply(...)`; seven `reportPrivateUsage` ignores.
Change: `GameService.settled() -> Awaitable[None]` (await every background task) and
`GameService.speaking: bool`; `Turn.apply(play)` public (its docstring calls it "the one gate").
