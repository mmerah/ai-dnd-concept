# Proposals: code pattern quality before MVP0

Scope: `src/aidm` only. Baseline: `ruff`, `ruff format --check` and `basedpyright --strict` all pass.
Four reviewers read every file (one lead, three independent lenses: duplication, consistency,
architecture). The five below are the ones every lens agreed a senior Python reviewer would notice
first, ranked by lines removed and consistency gained per unit of risk. None changes what the player
sees. Together they remove about 100 lines.

Each proposal ends with **Decisions**. Accepting a proposal means picking one option per decision.
The recommended option is listed first.

---

## 1. Type the engine by its world and delete `world_of`

**Plain English.** Every engine method that touches the world calls `self.world_of(state)`, which
is always `return state.payload`. The method exists only because the engine does not know its own
world type. Give it that type and the indirection disappears at 75 call sites.

**Today.**
- `Engine[P: Person, M: Person, G: Game[Any]]` (`engines/seam.py:61`) with `world_of` abstract at
  `:336`.
- Five identical overrides of `return state.payload`: `scenes/engine.py:95`,
  `rooms/engine.py:64`, `loner3e/engine.py:76`, `tunnelgoons/engine.py:75`,
  `twentyfourxx/engine.py:111`. Breathless has none, proving the three concrete ones exist only to
  narrow the return type.
- Both families already declare the world class: `world: type[SceneWorld[C]]`
  (`scenes/engine.py:82`) and `world: type[RoomWorld[P, N]]` (`rooms/engine.py:56`).
- `Game[Any]` is spelled as a bound in three places (`seam.py:56,61`, `scenes/engine.py:80`,
  `rooms/engine.py:55`, `core/tools.py:23,30`). CLAUDE.md allows it only where invariance forces it;
  after this change it is forced nowhere in `engines`.

**Change.**
```python
# engines/seam.py
class Engine[P: Person, M: Person, W: World[P, M]](ABC):
    world: type[W]
    game: type[Game[W]]          # unchanged declaration, narrower type
    ...
    def kill(self, draft: Game[W], args: Kill, _rng: Random) -> list[Fact]:
        return draft.payload.kill(args.entity_id)

# engines/scenes/engine.py
class SceneEngine[C: Person, K: ScenePack, W: SceneWorld[C]](Engine[C, C, W]): ...

# engines/rooms/engine.py
class RoomEngine[P: Person, N: Dweller, W: RoomWorld[P, N]](Engine[P, N, W]): ...

# engines/loner3e/engine.py
class Loner3eEngine(SceneEngine[Loner3eCast, Pack, Loner3eWorld]): ...
```
Then: delete the abstract `world_of` and its five overrides; replace every `self.world_of(x)` with
`x.payload` (75 sites, mechanical); `MasterTool[G]` and `Request[G]` keep their game parameter and
are spelled `MasterTool[Game[W]]` inside the engine. `AnyEngine = Engine[Any, Any, Any]` is
unchanged.

**LOC.** About −25 (six methods), plus 75 lines that get shorter.

**Feature impact.** None. Type-level only. `basedpyright` is the proof: the narrowed
`draft.payload` must type-check everywhere `world_of` did.

**Tests.** Three sites call `world_of`: `tests/engines/test_hiring.py:118`,
`tests/support/fifth.py:65`, `tests/core/test_golden_turn.py:48`. Each becomes `.payload`.
`tests/support/sixth.py:36` and `fifth.py` update their class headers.

**Decisions.**
- D1.1 How far to go.
  - (a) Remove `world_of` entirely, as above. One spelling, `state.payload`, everywhere.
  - (b) Keep `world_of` but type it once in each family via the new `W`, deleting only the three
    concrete overrides (−9). Smaller diff, keeps the indirection.
- D1.2 The `game` class attribute (`game = Loner3eGame`, four sites). It stays declared, because
  pydantic needs the concrete `Game[World]` class at runtime for `parse`. Deriving it as
  `Game[self.world]` in `__init__` is possible but reads as magic. Recommend: keep it declared.

---

## 2. One spelling for a pass-through tool, and hiring as a mixin

**Plain English.** A master tool that only unpacks its arguments and hands them to the world is
written two ways: as a lambda in the `master_tools` tuple, or as a two-line method. Both forms sit
side by side in the same files. On top of that, three engines carry the same hiring code twice
over (a `hire_prompt` wrapper with one caller each, a byte-identical `drop_item`), and every engine
carries a hiring stub that can never run.

**Today.**
- Lambda form, 8 sites: `seam.py:99-101` (reveal), `rooms/engine.py:199-205` (unlock_way,
  move, meanwhile), `scenes/engine.py:198-199` (enter, leave), `tunnelgoons/engine.py:92` (rest),
  `twentyfourxx/engine.py:138-140` (take_lead).
- Method form doing the same job, 7 sites: `seam.py:116-120` (join_party, leave_party),
  `rooms/engine.py:208-209` (move_item), `breathless/engine.py:165-166` (use_med_kit),
  `:269-270` (ask_world), `twentyfourxx/engine.py:327-328` (ship_upgrade), `:478-479` (ask_world).
  `kill` (`seam.py:113`) must stay a method: `twentyfourxx/engine.py:335` overrides it.
- 20 tool methods take `_rng: Random` and ignore it.
- `drop_item` is byte-identical in `breathless/engine.py:183-185` and
  `twentyfourxx/engine.py:313-315`.
- `hire_prompt` has exactly one caller in each of `tunnelgoons/engine.py:139`,
  `breathless/engine.py:168`, `twentyfourxx/engine.py:372`.
- `hires: bool` (`seam.py:67`) gates a branch in `master_tools` (`:105`) and one in
  `worldsmith_requests` (`:109`), and puts `hire`, `write_hire` and a `write_sheet` stub that
  raises `ValueError("hires nobody")` (`:122-125`) on every engine. The stub is unreachable: with
  `hires = False` nothing registers the tool or the request. Three of four engines hire.

**Change.**
1. Rule: a binding whose body only forwards is a lambda in `master_tools`; a method as soon as it
   resolves an id, rolls, calls `check_unnamed`, or is overridden. Delete the seven forwarding
   methods and bind them like their neighbours:
   ```python
   master_tool("join_party", JOIN_PARTY, JoinParty, lambda d, a, _: d.payload.join_party(a.entity_id)),
   ```
2. Move the hiring slice out of `Engine` into `engines/hiring.py`:
   ```python
   class Hiring[P: Person, M: Person, W: World[P, M]](Engine[P, M, W]):
       def master_tools(self): return (*super().master_tools(), master_tool("hire", HIRE_TOOL, Hire, self.hire))
       def worldsmith_requests(self): return {**super().worldsmith_requests(), HIRE: Request(HIRE_UNWRITTEN, self.write_hire)}
       def hire(...): ...          # moved from seam.py:127-134
       async def write_hire(...): ...   # moved from seam.py:136-147
       @abstractmethod
       async def write_sheet(...) -> str: ...
   ```
   `BreathlessEngine`, `TwentyfourxxEngine`, `TunnelGoonsEngine` inherit `Hiring`; the `hires`
   flag, both `if self.hires` branches and the dead stub go.
3. Inline `hire_prompt` into each `write_sheet` (pure inlining; three defs and three calls
   vanish).
4. `drop_item`: put the two-line bridge on the entity that owns the sheet, once:
   ```python
   # engines/base.py, beside ItemSheet
   class Carrier[I: Item](Sheeted[ItemSheet[I]]):
       def drop(self, item_id: Slug) -> list[Fact]:
           return self.require_sheet().drop_item(item_id, self)
   ```
   `Survivor(Carrier[Supply])`, `Crewmate(Carrier[Gear])`; both engines bind `drop_item` as a
   lambda.

**LOC.** About −36 (−12 forwarders, −6 hiring, −12 hire_prompt, −6 drop_item).

**Feature impact.** None. `master_tool` already accepts any `Callable[[G, A, Random], Sequence[Fact]]`
(`core/tools.py:30-42`). The MCP tool list, names and descriptions are unchanged, so the prompt
goldens under `tests/core/fixtures` do not move.

**Tests.** `tests/engines/test_hiring.py` constructs engines; check it does not set `hires` on a
test engine (grep finds none in `tests/support`).

**Decisions.**
- D2.1 Direction of the rule.
  - (a) Lambda for a pure forward, method otherwise (as above).
  - (b) Method everywhere: converts eight lambdas into about 24 lines. Consistent, but a LOC loss.
- D2.2 Hiring.
  - (a) Mixin class as above; `hires` flag deleted.
  - (b) Keep the flag; only delete the unreachable `write_sheet` stub body by making
    `write_sheet` abstract on `Engine` and raising in Loner3e. Smaller, but Loner3e then carries a
    method it must never be asked for.
- D2.3 `drop_item`.
  - (a) Add `Carrier` (two classes need it, which meets the CLAUDE.md bar).
  - (b) Keep the two copies and only apply D2.1 to them.
- D2.4 Also fold the `author` duplicate? Both families write the same 18-line `author` body
  (`rooms/engine.py:161-178`, `scenes/engine.py:268-286`; last line byte-identical), differing in
  four values. Making `Engine.author` concrete costs four hooks (`opening_ask`, `opening_model`,
  `premise_of`, `authored_packs`) and a fourth type parameter for the draft, for −22 lines.
  - (a) Leave it: two explicit bodies read better than four hooks.
  - (b) Do it, accepting the extra parameter on the two family headers.

---

## 3. One rule for failure signalling and for lookups that fail

**Plain English.** Three small drifts in how the code says "no". A refusal's prose is compared as a
string across the app/ui boundary to drive control flow. Validator helpers raise two different
exception types for the same job, eight lines apart. And one raising lookup is named as if it did
not raise.

**Today.**
- `runtime.py:31-32` defines `IN_FLIGHT_HERE` and `IN_FLIGHT_ELSEWHERE`; `Runtime.admit`
  (`:345`) raises one as a plain `Refusal`. `ui/game.py:13` imports both back and branches on the
  message text: `str(error) in (IN_FLIGHT_HERE, IN_FLIGHT_ELSEWHERE)` (`:596`) and
  `message != IN_FLIGHT_HERE` (`:616`). Editing the wording silently breaks the retry loop.
- Validator-only `check_*` helpers: `check_named` (`scenes/world.py:258`), `check_spread`
  (`breathless/world.py:212`) and `check_risk` (`twentyfourxx/tools.py:177`) raise `ValueError`;
  `check_filing` (`engines/base.py:361`) raises `Refusal`. `scenes/world.py:52-62` is one
  `@model_validator` that calls both kinds. `check_unique` and `check_picks` correctly raise
  `Refusal` because rules code also calls them; `check_filing` has no such caller.
- Sixteen raising accessors are named `require_*` (`base.py:154,193,236,259,267`,
  `rooms/world.py:82,88,194,204`, `scenes/world.py:98,106,117,128`, `twentyfourxx/world.py:227`,
  `scenes/packs.py:36`, `runtime.py:335`). The one exception is `chosen_option`
  (`core/creation.py:62`), which raises, beside `option_of` (`:58`), which returns `None`.

**Change.**
1. In `core/entities.py`:
   ```python
   class Busy(Refusal):
       """The single-writer gate is held; the caller may retry."""
   ```
   `Runtime.admit` raises `Busy(...)`. In `ui/game.py`, `_run` becomes
   `except Busy: return False` then `except Refusal as e: alert(str(e)); return False`, and
   `_opened` (`:587-605`) loses the `nonlocal blocked` closure: `try: await self._run(self.session.open)
   except Busy: return` then `opener.cancel()`. The two constants stay in `runtime.py` as the
   message text only; `ui` stops importing them.
2. `engines/base.py:364`: `raise Refusal(...)` becomes `raise ValueError(...)`. Rule to write into
   CLAUDE.md: a helper called only from validators raises `ValueError`; a helper rules code also
   calls raises `Refusal`.
3. Rename `chosen_option` to `require_option` (one def, five call sites: `loner3e/engine.py:125`,
   `twentyfourxx/engine.py:200,201,205,227`).

**LOC.** About −14 (all in `ui/game.py`).

**Feature impact.** None for 1 and 3. For 2, the message the worldsmith reads on a mis-filed cast
gains pydantic's field prefix, e.g. `cast: entity 'x' is filed under 'y'`; the player never sees it.

**Tests.** `tests/ui/test_game.py:273,299` raise `Refusal(IN_FLIGHT_*)` from a stub; they raise
`Busy` instead. `tests/app/test_game_service.py:535` matches on the message and keeps passing.
`tests/engines/test_scene_bar.py:505` matches `ValueError`, which pydantic's error still is.

**Decisions.**
- D3.1 `Busy` placement.
  - (a) `core/entities.py`, beside `Refusal`: the one home for exception types.
  - (b) `app/runtime.py`: it is an app concept. Then `ui` imports it from `app`, which the layering
    allows.
- D3.2 `PackSet.chosen()` (`scenes/packs.py:41`) raises via `require`, while
  `SceneEngine.chosen_packs()` (`scenes/engine.py:110`) deliberately does not.
  - (a) Rename `PackSet.chosen` to `PackSet.selected` so `chosen` means one thing.
  - (b) Leave it.

---

## 4. Readers are properties; abstract signatures carry no stray markers

**Plain English.** CLAUDE.md says a zero-argument, side-effect-free reader of its own fields is a
property. About half of them are; the rest are methods, sometimes next to a property of the same
shape in the same class. Separately, five of thirteen abstract methods carry a positional-only
`/` that no implementation mirrors. Neither costs lines to fix, and both are the first things a
reviewer sees when opening `base.py` and `seam.py`.

**Today.**
- Properties: `Gauge.shortfall`, `Thing.mention/tag/headline/met_label`, `Person.hired/hireable`,
  `Gear.broken`, `SurvivorSheet.vulnerable`, `CreationStep.constrains`, `Rolled.kept/total/face`,
  `RoomWorld.current/holders_here`, `SceneWorld.run`.
- Methods of the same shape: `Person.required()` (`base.py:122`, overridden at `:170`,
  `loner3e/world.py:75`, `tunnelgoons/world.py:90`), `Item.notes()` (`base.py:186`,
  `twentyfourxx/world.py:62`, `breathless/world.py:34`), `Sheeted.carried()` (`base.py:162`,
  `twentyfourxx/world.py:197`, `breathless/world.py:187`), plus `rows()` (7 defs) and
  `subject()`/`row()`.
- Worst adjacent pairs: `Gear.broken` (property, `twentyfourxx/world.py:50`) beside `Gear.notes()`
  (method, `:62`); `Subject.headline` (property, `core/views.py:29`) beside `Subject.row()`
  (method, `:32`); `Person.hired` (property, `base.py:137`) beside `Person.required()` (`:122`).
- Positional-only `/` on `creation_steps`, `build_character`, `family_sections`, `act`,
  `guidance` (`seam.py:332,334,342,357,361`) and `write_sheet` (`:122`), plus
  `FileStore.write` (`core/io.py:40`). Not on `world_of`, `new_game`, `master_sections`,
  `narrator_view`, `player_view`, `author` in the same block. Zero implementations mirror it
  except `write_sheet`'s three. Nothing calls any of them by keyword.

**Change.**
1. Make `required`, `notes`, `carried` properties: 9 definitions, about 10 call sites drop `()`.
2. Delete the `/` markers (seven sites).

**LOC.** 0. About 30 one-token edits.

**Feature impact.** None. `super().required` works on a property. The master prompt text is built
from the same values.

**Tests.** Any test calling `.required()`, `.notes()` or `.carried()` drops the parentheses
(grep before editing).

**Decisions.**
- D4.1 `rows()`, `subject()`, `row()`.
  - (a) Leave them as methods and add one line to CLAUDE.md: "a reader that builds a new value
    stays a method". `rows()` builds a tuple, `subject()`/`row()` construct objects; the rule as
    written does not reach them.
  - (b) Convert them too, about 25 more edits, for a rule with no exception.
- D4.2 `write_sheet`'s `/`.
  - (a) Drop it with the rest, including its three overrides. One rule.
  - (b) Keep it as the one place base and overrides already agree.

---

## 5. Things live where their kind lives

**Plain English.** Four placement drifts. UI page classes declare attributes with no value inside
`__init__`, which tells the type checker they exist and the runtime that they do not. The seam's
tool descriptions and argument models live in `base.py` and a one-tool module named `hiring.py`,
while every family and engine keeps the same material in a `tools.py`. Two sibling modules with
identical structure make opposite visibility choices. One module puts a private function ahead of
nine public ones.

**Today.**
- 25 bare `self.x: T` lines with no assignment: `ui/game.py:107-126` (16),
  `ui/create.py:38-39,180-187` (9). `Engine` spells the same intent in the class body
  (`seam.py:63-78`) with a one-line reason. Two spellings for "set later by `build()`".
- Seam tool material outside a `tools.py`: constants `base.py:15-22` (`REVEAL`, `KILL`,
  `JOIN_PARTY`, `LEAVE_PARTY`, `ACTOR`, `DROP_ITEM`) and models `base.py:291-322` (`Attempt`,
  `Reveal`, `Kill`, `JoinParty`, `LeaveParty`, `DropItem`, `AskWorld`); the whole of
  `engines/hiring.py` (`HIRE`, `HIRE_TOOL`, `HIRE_UNWRITTEN`, `SIGNED_ON`, `HIRED`,
  `UNWRITTEN_CAST`, `Hire`). Six of eight layers already use `<layer>/tools.py`.
- `scenes/worldsmith.py:35` `scene_unmet` is public with one caller (`:31`); its sibling
  `rooms/worldsmith.py:25,32,50,58` keeps the same four fragments private.
- `ui/widgets.py:54` `_notify` precedes nine public functions. The only module-order violation in
  `src` (verified by an AST walk over all 69 files).

**Change.**
1. Move the 25 bare annotations to the class body, as `Engine` does. `__init__` keeps only
   assigned state.
2. Create `engines/tools.py`; move the constants and models from `base.py` and fold `hiring.py`
   into it (or, if proposal 2's `Hiring` mixin lands, `hiring.py` keeps the class and
   `engines/tools.py` takes the constants and `Hire`). Update about eight import lists.
3. Rename `scene_unmet` to `_scene_unmet`.
4. Move `_notify` below `decision_widget`.

**LOC.** About −6 (one module header) for 2; 0 for the rest, 30 lines relocate.

**Feature impact.** None. Pure relocation; prompt text and schemas are byte-identical, so the
prompt and schema goldens do not move.

**Tests.** Imports of `HIRE`, `Hire`, `Attempt`, `DropItem` from `engines.base` or
`engines.hiring` in `tests/` repoint to `engines.tools`.

**Decisions.**
- D5.1 Bare annotations.
  - (a) Class-body declarations, matching `Engine`. Zero behaviour change.
  - (b) A `Widgets` dataclass built by `build()` and held as `Widgets | None`, so the "before
    build" state is typed. Honest, but every access pays a `None` check.
- D5.2 `Attempt` (`base.py:291`), a shared base for engine argument models.
  - (a) Move it with the rest; every importer is already a `tools.py`.
  - (b) Leave it in `base.py`; the split is then 90% done.
- D5.3 `scene_unmet`.
  - (a) Make it private.
  - (b) If you intend to unit-test fragment lists directly, make `rooms`' four helpers public
    instead so the families match.

---

## Not in the five

One line each, with the reviewer's estimate, so any can be pulled up.

- `GameService.phase` is set at seven sites under three `try/finally` blocks
  (`runtime.py:120-244`); a `_phase(role)` context manager removes the blocks (−8) and the
  "composer wedged disabled" failure mode.
- `Game.generation` is `exclude=True` (`core/model.py:108`) with no comment, so the
  `restore` guard at `seam.py:181` is dead for saves this app writes, and a server restart between
  `act`'s save (`runtime.py:148`) and `_grow` drops the request silently. Pick: keep exclusion and
  delete the guard (−2), or drop exclusion and refuse the save. Behaviour, not pattern.
- A failed narrator on a landed turn closes the exchange with no lines
  (`runtime.py:249-259`); every other failure path lands a told "unwritten" fact. A
  `UNNARRATED` fact would match (+6). Behaviour, not pattern.
- `ui` writes a character to disk itself (`create.py:135-138`) while scenario creation goes
  through `Runtime.new_scenario`; a `Runtime.new_character` and `Runtime.catalog()` keep `Library`
  and `FileStore` out of `ui` (+2).
- `CatalogEntry.rules/look` and `SaveOption.rules` are functions of `engine`; deriving them on the
  catalog removes both constructions' repeats (−10).
- "Drop the empty pairs and join" is open-coded six times across `rows()` and `required()`; two
  free helpers remove it (−13).
- `SkillPool.helper` is a `tuple[Survivor, Die]` read by index (`breathless/engine.py:195-214`)
  while its twin is a `NamedTuple` (`twentyfourxx/engine.py:90`); two named fields fix the only
  index-through-a-tuple in `src`.
- `render_worldsmith` (`seam.py:203`) reads only `family_dir` and renders at an edge; CLAUDE.md
  says such a function stays free.
