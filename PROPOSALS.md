# PROPOSALS — code quality and pattern consistency in `src/`

Audit before MVP0. Four readers: one lead pass plus three independent Opus passes over
`core`+`turn`+`app`, `engines`, and `ui`+cross-cutting. Claims below were checked against the
files, not assumed.

## Baseline

`ruff check`, `ruff format --check` and `basedpyright` (strict) all pass. 806 tests pass in 7.8s.
No dead code. No `cast`, no `type: ignore`. `Any` appears only as the `Game[Any]` bound CLAUDE.md
allows. The import graph `core <- engines <- turn <- app <- ui` holds and is enforced by a test.
A 4-line clone scan across all of `src/` found nothing but import blocks.

There is no fat to cut. What is left is: data written as code, a few one-off spellings of a job
done elsewhere, and about nine places where the code breaks a rule CLAUDE.md states.

**Every proposal is accepted and every decision is closed. Total: about −139 lines.**

| # | Proposal | LOC | Feature impact | Status |
|---|---|---|---|---|
| 1 | Engine palettes become data | −55 | none | auto-accepted |
| 2 | One home for `w-full`; `page_header` returns the header | −18 | none | auto-accepted |
| 3 | `RoomWorld.meanwhile` takes its args model | −16 | none | auto-accepted |
| 4 | `UnresumableSave` becomes a `Refusal` | −12 | none | auto-accepted |
| 5 | 24XX: one staked shape, one hit loop | −28 | none | **accepted: B** |
| 6 | Six small subtractions | −15 | none | auto-accepted |
| 7 | Nine places `src/` breaks its own rules | +5 | none | auto-accepted |
| 8 | The hidden-canon check runs in one scene engine of three | +4 | **yes** | **accepted: a** |
| 9 | Player-facing messages: three fixes | −2 | **yes** | **accepted: all three** |
| 10 | The two engine families disagree on shape | −2 | none | **accepted: 10a + 10b** |

## Order of work

Four commits. Each one leaves `uv run pytest`, `ruff check`, `ruff format --check` and
`basedpyright` green.

1. **Pure subtraction, no behaviour** — 1, 3, 4, 6, 2. About −116 lines. Half a day.
2. **Rule compliance** — 7 (nine sites, +5). No behaviour change, but it touches `engines`, `app`
   and `config`, so it wants its own commit. Two to three hours.
3. **Schema-affecting** — 5B. Regenerate `master_tools.json` with `AIDM_GOLDEN_REGEN=1` and commit
   the fixture diff alongside the code. One hour, plus one live 24XX turn to sanity-check the
   reordered prompt.
4. **Behaviour** — 8, 9, 10a/10b. New refusals, new toast shape, one bug fix. Each needs a test
   touched. Half a day. Re-run `qa/s_create.py` and `qa/s_settings.py`.

Do not batch 3 and 4 into 1 and 2: the first two commits should be reviewable as "nothing can have
changed", and the last two as "here is exactly what changed".

---

## 1. Engine palettes become data — −55 lines, no feature impact

**Auto-accepted** (no feature impact, removes code).

**What is there now.** Each engine writes its colour scheme as a Python literal inside its engine
class: `loner3e/engine.py:64-77` (14 lines), `tunnelgoons/engine.py:67-80` (14),
`breathless/engine.py:69-83` (15), `twentyfourxx/engine.py:101-115` (15). 58 lines in total, all
the same shape — a `Look(palette={...nine or ten hex strings...}, dice=DiceLook(...))`. Nothing in
those hex strings is code. `Look.palette` is `Mapping[str, str]` (`core/views.py:135-137`), so the
keys are not type-checked today either.

**What it becomes.** A `look.json` beside each engine's `rules.md`, read once in
`Engine.__init__` (`seam.py:81-93`), which already reads two markdown files and, for scene
engines, a directory of pack JSON:

```python
self.look = read_model(self.directory / "look.json", Look)
```

`read_model` already exists (`core/io.py:185-188`) and is the same mechanism
`scenes/packs.py:read_packs` uses. `look` moves from the "Declared" block (`seam.py:66`) to the
"Derived by `__init__`" block (`seam.py:76-79`).

**Why it is right.** Every other per-engine asset already lives as a file next to `engine.py`:
`rules.md`, `worldsmith.md`, `packs/*.json`. The palette is the odd one out. It is also the thing
a new engine author most wants to edit without opening Python.

**LOC.** −58 across four `engine.py` files, +1 in `seam.py`, +2 in test support = **−55**.
`read_model` folds into an existing import line. About 56 lines of new JSON.

**Risk.** Low, with one bonus. `tests/support/fifth.py` and `tests/support/sixth.py` define test
engines that never set `look` at all — verified — so `Engine.look` is today a declared-but-unset
attribute that would raise `AttributeError` if anything touched it. Reading it in `__init__` turns
that silent hole into a load-time failure. Each test helper needs one line writing `look.json`.

**Alternative, if you would rather keep the values in Python:** a shared
`def palette(bg, surface, raised, text, muted, border, accent, wash, radius, ...) -> Look`
constructor in `engines/base.py`, giving about −30 instead of −55. Say the word and I will switch
this proposal to that.

---

## 2. One home for `w-full`; `page_header` returns the header — −18 lines, no feature impact

**Auto-accepted.**

### 2a. `.classes("w-full")` — 26 repeats — −14

**What is there now.** `ui/theme.py:42-50` already states the intent: *"One look for every call
site: the defaults live here so no widget repeats a prop."* It sets `default_props` for five
element types. But 26 call sites still write `.classes("w-full")` by hand:
`create.py` ×16, `settings.py` ×6, `app.py` ×4.

**What it becomes.** Three lines in `theme.install()`:

```python
for field in (ui.input, ui.textarea, ui.select, ui.number, ui.switch, ui.upload):
    field.default_classes("w-full")
ui.textarea.default_props("autogrow")
```

Then every `.classes("w-full")` on those elements goes. `default_classes` exists on all six types
in the pinned nicegui 3.16.0 — verified by running it.

Most sites just get shorter, but five multi-line builders collapse to one line each:
`create.py:45-47` (brief), `234-238` (premise), `239-246` (scope), `247-249` (style),
`254-258` (upload).

**LOC.** −15 in `create.py`, +1 in `theme.py` = **−14**.

**One carve-out.** `game.py:402-406` builds the composer box as `ui.input().classes("flex-grow")`
inside a `no-wrap` row; a default `w-full` there would squeeze the send button. Fix with
`.classes(remove="w-full")` on that one box (+1 line). Playwright selectors in `qa/` do not key on
`w-full`, so the e2e suite is unaffected.

### 2b. `page_header` is a context manager three callers do not want — −4

**What is there now.** `widgets.py:33-45` is a `@contextmanager`, so three of its six callers are
forced to write a `pass`-bodied `with`: `app.py:171-173`, `create.py:34-35`, `create.py:183-184`.

**What it becomes.** It returns the header instead. NiceGUI's `Element` is itself re-enterable,
so the three callers that *do* add buttons (`app.py:89`, `game.py:135`, `settings.py:26`) keep
`with page_header(...):` unchanged and their children still land in the header slot.

```python
def page_header(title, badge=None, *, home=True, look=None) -> ui.header:
    ui.dark_mode(value=True)
    theme.set_look(look)
    with ui.header().classes("items-center no-wrap") as header:
        ...
    return header
```

**LOC.** −1 in `widgets.py`, −3 at call sites = **−4**.

---

## 3. `RoomWorld.meanwhile` takes its args model — −16 lines, no feature impact

**Auto-accepted.**

**What is there now.** `rooms/world.py:332-341` is a ten-line keyword-only signature taking six
optional slugs in three pairs. `rooms/engine.py:213-221` is a nine-line adapter that does nothing
but re-type those same six names from the `Meanwhile` tool model into keywords.

**What it becomes.**

```python
# rooms/world.py
def meanwhile(self, args: Meanwhile) -> list[Fact]:

# rooms/engine.py
def meanwhile(self, draft: G, args: Meanwhile, _rng: Random) -> list[Fact]:
    return self.world_of(draft).meanwhile(args)
```

The body's six names become `args.dweller_id` and so on. The longest resulting line is 62
characters, well under the 100 limit.

**Why it is safe.** The precedent exists: `scenes/world.py:17` already imports `SceneDraft` from
`scenes/tools.py`. `rooms/tools.py` imports only from `core`, so there is no cycle. CLAUDE.md's
"an engine tool method resolves ids" is not in tension here — `RoomWorld.meanwhile` already
resolves its own ids and raises `UNKNOWN_ID` itself (`rooms/world.py:348, 363`); the engine
adapter contributes only the splat.

**LOC.** 10 → 1 in `world.py`, 9 → 2 in `engine.py` = **−16**.

**Alternative if you dislike a world importing a tool model:** declare a frozen `Offscreen` value
in `rooms/world.py` and have `Meanwhile` convert to it — same saving in `engine.py`, +5 in
`world.py`.

---

## 4. `UnresumableSave` becomes a `Refusal` — −12 lines, no feature impact

**Auto-accepted.**

**What is there now.** `app/launch.py:45-49` defines a frozen dataclass whose only field is
`slug: str`. `_save_option` (`launch.py:121-160`) returns `SaveOption | UnresumableSave | None`,
writes `LOGGER.warning("skipping save %r: ...")` in four separate places, returns the sentinel
from four branches, and `LauncherCatalog.read` (`launch.py:106-118`) splits the result apart again
with two `isinstance` filters.

This is a hand-rolled error channel sitting beside the one the project already has. Each of those
four branches is exactly CLAUDE.md's definition of a `Refusal`: "a message a role or the player is
meant to read". The `except` at `launch.py:129-139` already converts real `Refusal`s from
`store.read` and `engine.restore` into the same sentinel.

**What it becomes.** `_save_option` raises `Refusal` for a stale save and returns `None` only for
the vanished-between-listing-and-read case. `read` catches once:

```python
saves: list[SaveOption] = []
unresumable: list[str] = []
for slug in store.slugs():
    try:
        option = _save_option(slug, store, engines, titles, played_by, metas)
    except Refusal as unreadable:
        LOGGER.warning("skipping save %r: %s", slug, unreadable)
        unresumable.append(slug)
    else:
        if option is not None:
            saves.append(option)
```

**LOC.** Class block −7; `read` 13 → 18 (+5); `_save_option` 40 → 30 (−10) = **−12**.

**Feature impact: none.** `catalog.unresumable` keeps type `tuple[str, ...]` and the same
contents, so `ui/app.py:73` is untouched. Log lines keep their shape.

**Risk.** Low. `tests/app/test_launcher.py` asserts on `catalog.unresumable` contents, never on
the class, and nothing outside `launch.py` imports it.

---

## 5. 24XX: one staked shape, one hit loop — −28 lines — **DECIDED: option B (full)**

**What is there now.** Two things in the 24XX engine are written twice.

**(a) The four "what is at stake" fields, plus their validator, appear in both `Helper` and
`Roll`** (`twentyfourxx/tools.py:102-109` and `128-135`, validators at `111-116` and `137-142`).
Fourteen lines, character for character the same, except that `risk`'s description says "the
helper" in one and "the actor" in the other — which is exactly the difference the neighbouring
`DEADLY` and `DEFEND_WITH` constants already handle with `.format(who=...)`.

**(b) `roll` applies the outcome twice** (`twentyfourxx/engine.py:441-462`): 22 lines that are one
`world.take_hit(...)` call for the helper and the same call for the actor, differing only in which
object the five arguments come from. Six lines earlier (`411-416`) the same two sources are
already paired into a `claims` list for `check_defenses`.

**Decided: option B — do both.** Options A and C are kept below for the record.

**Option A (not taken) — −14 lines.**
Fix (b) only. Build one list of stakes and loop:

```python
@dataclass(frozen=True, slots=True)
class Stake:
    who: Crewmate
    risk: str
    deadly: bool
    defend_with: Slug | None
    hindrance: str
```

The same list feeds `check_defenses` and the `take_hit` loop, so `claims` disappears too. Keep the
helper-first ordering the current code uses, so the order of facts on the card does not change.
No JSON schema changes, no golden fixtures move.

**Option B — CHOSEN — −28 lines.**
Do A, and also fix (a): a shared frozen base `Staked(Frozen)` holding `risk`, `deadly`,
`defend_with`, `hindrance` and `_defend_fields`, with `Helper(Staked)` and
`Roll(Attempt, Staked)`. `risk`'s description takes a `who=` format argument, matching the
`DEADLY` and `DEFEND_WITH` constants beside it.

The cost is real and worth stating plainly: pydantic puts inherited fields **first**. So `Roll`'s
tool schema would change from
`what, actor_id, skill, helped, helped_by, hindered, risk, deadly, defend_with, hindrance`
to
`risk, deadly, defend_with, hindrance, what, actor_id, skill, helped, helped_by, hindered`.
That is what the game master model reads, in the order it reads it, with the least important
fields moved to the front. `tests/core/fixtures/schemas/twentyfourxx/master_tools.json`
regenerates with `AIDM_GOLDEN_REGEN=1`, so the mechanical cost is nil — the question is whether
you want to reorder a live prompt a week before launch.

**Option C (not taken).** Leave both. The duplication is 14 lines plus 22.

**Feature impact.** None in the code path. The one thing to watch after landing B: re-read the
regenerated `master_tools.json` and sanity-check a 24XX roll against a live master, because the
reordering is invisible to the test suite.

**Build note for B.** Regenerate the goldens with `AIDM_GOLDEN_REGEN=1 uv run pytest` and commit
the fixture diff in the same commit as the code, so the schema change is visible in review.

---

## 6. Six small subtractions — −15 lines, no feature impact

**Auto-accepted.** Six unrelated one-sitting edits, grouped because each alone is too small for a
slot.

**6a. One character-envelope helper on the seam — −8.**
`breathless/engine.py:152-157` and `twentyfourxx/engine.py:253-258` spread the same four-field
constructor over six lines; `loner3e/engine.py:155` and `tunnelgoons/engine.py:141` write the
identical expression on one. Four engines, two formattings. Add to `seam.py`:

```python
def sheet_character(
    self, name: str, player: BaseModel, packs: PackSelection | None = None
) -> AnyCharacter:
    return self.character(id=slug(name, ()), engine=self.id, packs=packs, payload=player)
```

`self.character` is already `type[Character[Any]]` (`seam.py:75`), so the payload type is erased
at that boundary today — the helper loses nothing.

**6b. `told_history` is named for the wrong reader and duplicates `_block` — −4.**
`core/prompt.py:36` says *"The recent blocks the master reads"*. Its only caller is
`app/roles.py:161`, under the heading `"WHAT THE PLAYER HAS READ"`, building the **narrator** and
interjection prompts. The master reads `render_history` (`turn/run.py:162`). Nothing in the
function is gated on `Fact.told` either, so the name promises a filter that does not exist.
Rename to `recent_history`, fix the docstring, and extract the block it shares with `_block`:

```python
def _whole(chapter: Chapter) -> str:
    return f"{_header(chapter)}\n\n{_told(chapter.exchanges[-SCENE_EXCHANGES:])}"
```

Output is byte-identical. Touches `roles.py:15,161` and five assertions in
`tests/core/test_prompt.py` (whose test name at line 49 also encodes the wrong reader).

**6c. `hire_check` on the seam — −2.**
The three hiring engines' `write_sheet` bodies are identical apart from the draft model and the
check (`breathless/engine.py:93-98`, `tunnelgoons/engine.py:93-98`,
`twentyfourxx/engine.py:128-133`). Two pass `lambda _answer: None`; only 24XX passes a real one.
Put a no-op `hire_check` on the seam so all three read the same.
*(The full template — declaring `sheet_draft: type[D]` and making `write_sheet` concrete — would
save 15 instead of 2, but needs a fourth type parameter `D: BaseModel` on `Engine`, propagating to
`RoomEngine`, `SceneEngine` and all four engine headers including `loner3e`, which hires nobody
and would carry a dummy. Not worth it.)*

**6d. `Counter` for the defence claims — −2.**
`twentyfourxx/world.py:239-241` counts claims with a three-line `claimed[id(item)] = ... + 1`
loop. `Counter(id(item) for _, item, _ in resolved)` is one line. Identity is the correct
semantics here — two actors can claim the same ship function — so add the one-line comment saying
so, which is currently missing.

**6e. One spelling of the optional-collaborator guard — −2.**
`app/runtime.py:275-297`: five adjacent `GameService` methods check `self.media is None` /
`self.reader is None`; three use a guard clause and two use a conditional expression. Use the
guard clause, which is the majority and what the two-condition cases already need.

**6f. Hoist the duplicated end-of-game sentence — +1.**
`turn/run.py:58` and `app/runtime.py:141` both write
`raise Refusal(f"{ended} The only way on is to restart.")`. `turn/run.py` already keeps its other
player-facing sentences as module constants (`NO_TURN`, `GAME_OVER`, `RULES_WAIT`); this one was
missed. Add `RESTART` beside them and import it. *(Both guards are needed — `runtime.act` must
refuse before `engine.act` mutates the draft, and the `_grow` branch never reaches `Turn.begin`.
Do not delete either.)*

---

## 7. Nine places `src/` breaks its own rules — +5 lines, no feature impact

**Auto-accepted.** None of these saves lines. All of them matter, because a senior reader with
`CLAUDE.md` open will grep for exactly these rules, and today each one has a counter-example.

**7a. "A world or entity method changes fields and writes the facts" — broken three times.**
`install_sheet` assigns a field on a world entity from engine code:
`breathless/engine.py:204-212`, `tunnelgoons/engine.py:161-165`,
`twentyfourxx/engine.py:396-404`. Each does `member.sheet = <Sheet>(...)` then returns a summary
string. Move each body to an entity method — `Survivor.sign_on(answer) -> str`, and the same for
`Npc` and `Crewmate` — leaving the engine as `return member.sign_on(answer)`. LOC ≈ 0; the bodies
move, they do not shrink.

**7b. "A function whose first argument is one of our objects is a method" — broken three times,
all in 24XX.**
`engines/twentyfourxx/engine.py:570-571` `_helping(world, args)` → `world.helping(args)`;
`twentyfourxx/world.py:324-325` `_broken(item)` and `:328-330` `_harmless(item)` → methods on
`Gear`. LOC 0.

**7c. "`core`, `turn`, `app` and `ui` know no world shape" — broken once.**
`app/runtime.py:420` calls `engine.world_of(state).disarm()`. It is the only place outside
`engines/` that touches a `World`. The package-boundary test does not catch it because it is a
method call, not an import. Add `Engine.disarm(state)` to `seam.py` beside `tick`
(`seam.py:278-281`). +2 lines.

**7d. "Names must explain themselves. Do not add a comment unless the reason is not visible."**
`config.py:134-135` is `source_max_chars`, with a comment saying *"Enforced as a byte count in
core/source.py"* — and `core/source.py:36-38` does indeed measure
`len(text.encode("utf-8"))` and say "bytes" in the refusal. The name is wrong and a comment exists
solely to warn the reader. Rename to `source_max_bytes` (and `max_chars` → `max_bytes` in
`source.py:15,23` and `runtime.py:382`). −1 line.
*Small caveat:* the settings page builds `.env` keys from field names, so the key becomes
`SOURCE_MAX_BYTES`; an existing local `SOURCE_MAX_CHARS=` would silently fall back to the default.
There is no `.env` in the repo and no doc mentions the key, so the blast radius is one checkout.

**7e. "Validate data at each boundary with strict Pydantic V2 models" — one silent opt-out.**
`core/entities.py:28-31`: `Frozen`, `Mutable` and `Loose` all set `strict=True`; `Echoed` does
not, and its docstring explains only `extra="allow"`. `Echoed` is the base for `_Function`,
`_ToolCall`, `_Said` (`app/builtin.py:20,25,31`) — the model-reply boundary. A reader cannot tell
whether the omission is a decision or a slip. Either add `strict=True` (those three models declare
only `str`, `Literal`, nested-model and tuple fields, so lax and strict accept the same payloads)
or add one docstring line saying why provider replies are read lax. LOC 0.

**7f. Two `decode()` calls exist only for a side effect, unmarked.**
`core/io.py:187` and `app/spawn.py:219` call `decode(raw)` and throw the result away — `decode` is
the only thing that rejects duplicate JSON keys. `reportUnusedCallResult` is off project-wide for
NiceGUI's sake, so nothing flags them, and the third caller (`seam.py:180`) does use the result,
making the bare two read like leftovers. Delete either line and duplicate-key rejection vanishes
silently. Add a named `check_json_keys(raw)` helper in `core/io.py` and use it at both. +4 lines.

**7g. Four dataclasses are on the wrong side of the frozen/mutable split.**
The codebase is otherwise crisp about it: `frozen=True, slots=True` for values, bare
`dataclass(slots=True)` for things that mutate. These four never reassign a field — verified by
grep — and only mutate container contents, which `frozen=True` permits:
`app/providers.py:12 Claims`, `app/runtime.py:46 Tasks`, `app/media.py:35 Illustrator`,
`app/speech.py:23 Reader`. LOC 0.

**7h. `GameService` should be `kw_only`.**
`app/runtime.py:73` has 17 fields and its single construction site (`runtime.py:429-437`) passes
**eight** positionally — including a bare `self` as the eighth, which is the `Runtime` arriving as
`gate`. `Turn` in the same layer is already `kw_only=True` (`turn/run.py:32`), so the two service
objects disagree. Each argument is already on its own line, so adding the names costs nothing.
LOC 0. `GameService(` appears once in `src/` and zero times in `tests/`.

**7i. `GameService` reaches past its own facade.**
`app/runtime.py:232` is `worldsmith(self.roles.spawner)`, and `runtime.py:15` imports `worldsmith`
from `app/spawn.py` purely for it. Every other role call goes through `Roles` —
`self.roles.master(turn)`, `self.roles.narrate(...)`, `self.roles.interject(...)` — and the last
two already take the engine as their first argument, so the shape exists. Add
`Roles.grow(engine, draft, request) -> Written`. +3 lines.

---

## 8. The hidden-canon check runs in one scene engine of three — +4 lines — **DECIDED: (a) all four tools**

**What is there now.** `loner3e/world.py:168-172` defines `check_unnamed`, which refuses
master-authored free text that names a cast member the player has not met. `loner3e/engine.py:187`
and `:193` call it on `change_tags` and `drive`.

The method reads only `self.cast`. Nothing about it is loner3e-specific — it is pure `SceneWorld`
state.

The other two scene engines accept master-authored free text that lands on **player-visible
cards** and do not check it:

| engine | tool | free text | reaches the player via |
|---|---|---|---|
| 24XX | `gain_item` (`engine.py:318-322`) | `args.name` | `Gained {name}` card |
| 24XX | `change_hindrances` (`:309-316`) | `args.gained` | `Hindered: ...` card |
| 24XX | `spend` (`:333-334`) | `args.why` | `₡N spent — {why}` card |
| breathless | `change_stress` (`:181-184`) | `args.why` | `Stress ±N` card |

So the invariant CLAUDE.md calls load-bearing — *"The narrator reads revealed facts only. Hidden
facts have no path into it."* — is enforced in one engine of three.

**What it becomes.** Move `check_unnamed` verbatim to `scenes/world.py` (0 lines, it just changes
file) and add one `world.check_unnamed(...)` call to each of the four tools above.

**LOC: +4.**

**Feature impact: yes, and it is the point.** The game master will occasionally be refused and
have to reword. That is exactly what loner3e already does to it today.

**The honest counter-argument:** it is also a new way for a turn to fail, days before launch, on
two engines that have never had it. And `card_line` text is short and mostly mechanical
("Gained rope"), so the leak is narrow in practice.

**DECIDED: (a) — enable on all four tools.** The three scene engines end up with one rule and one
enforcer. `check_unnamed` moves verbatim to `scenes/world.py`; `loner3e` keeps calling it exactly
as it does today; `24XX` gains three calls (`gain_item`, `change_hindrances`, `spend`) and
`breathless` one (`change_stress`).

**Build note.** Add one test per newly-guarded tool asserting the refusal, mirroring the existing
loner3e coverage — otherwise the new guard is the only behaviour change in this whole report with
no test behind it.

---

## 9. Player-facing messages: three fixes — −2 lines — **DECIDED: take all three**

Three separate defects in what the player actually sees. All small, all behavioural.

### 9a. The scenario form eats what the player typed — **a bug**

`ScenarioForm.choose_engine` (`create.py:208-211`) calls `self.form.refresh()`, and `form()`
(`:213-266`) rebuilds **all eight** widgets with no `value=` carried over. So changing the rules
on the New Scenario page **silently wipes the title, premise, scope, art style and narrator voice
the player just typed.** Only `supplements`, `character` and `style`'s placeholder actually depend
on the engine.

`CharacterForm` already does it right: it builds `name` and `brief` in `build()`
(`create.py:44-47`), outside the refreshable, and `choose_engine` (`:59-65`) refreshes only
`steps` and `preview`.

**Fix:** move `title`, `premise`, `scope`, `voice` out of `form()` into `build()` (`:191-193`),
matching `CharacterForm`. Leave `supplements`, `character`, `style` and `button` inside the
refreshable — `style`'s placeholder interpolates `engine.art_style` (`:248`), so it must stay.

**LOC ≈ 0** (about 15 lines relocate). Re-run `qa/s_create.py`.

### 9b. Five toast shapes for one event — +5

A `Refusal` shown to the player renders three different ways depending on which file caught it:

| site | shape |
|---|---|
| `game.py:728-729` (`_alert`) | negative, multi-line, top |
| `create.py:294` | negative, multi-line, **no position** |
| `create.py:133` | negative only — **long refusals are truncated** |
| `settings.py:75` | negative, multi-line, no position |
| `game.py:492,548` | warning, top |
| `create.py:125,274` | warning, no position |

**Fix:** move `_alert` into `widgets.py` as `alert()`, add `warn()` with the same
`multi_line=True, position="top"`, convert the ten call sites. **+5 lines.**

**Feature impact:** the `create.py` and `settings.py` toasts move to the top of the viewport, and
`create.py:133` stops truncating. Both are improvements, both are visible changes.
`qa/drive.py:169` reads `.q-notification__message` text and is unaffected.

### 9c. Two `ValidationError` renderers in two layers — −7

`core/entities.py:72-75` (`_refused`) and `ui/settings.py:99-103` (`refusal_text`) both turn a
`ValidationError` into `"{loc}: {msg}"`, and disagree on how many errors to show — first vs all.
`ui/settings.py:70` is also the only `model_validate` call in `ui/`, bypassing the project's own
`parse` boundary helper.

**Fix:** replace `Settings.model_validate(merged)` with `parse(Settings, merged)`, catch `Refusal`
instead of `ValidationError`, delete `refusal_text`. **−7 lines.**
**Feature impact:** the settings page reports only the *first* bad key instead of all of them.
Rewrites `tests/ui/test_settings.py:20,114`.

**DECIDED: take all three.** Net −2 lines.

**Build note for 9c.** After the switch, the settings page reports only the first bad key. If that
turns out to be annoying in use, the cheap reversal is to keep `parse` and widen `_refused`
(`core/entities.py:72-75`) to join every error — but that changes every model-output refusal
message in the game and moves goldens, so it is a separate decision, not a quick undo.

---

## 10. The two engine families disagree on shape — −2 lines — **DECIDED: 10a + 10b; leave the family**

Three findings about `rooms/` vs `scenes/`, from smallest to largest.

**10a. `guidance` is an attribute in one family and a method in the other.**
`RoomEngine.guidance: str` is a class attribute (`rooms/engine.py:58`, set at
`tunnelgoons/engine.py:88`). `SceneEngine.guidance(selection)` is an abstract method
(`scenes/engine.py:322-323`). Same name, same job, two shapes. Fix: hoist `guidance` to the seam
as an abstract method taking `PackSelection | None`; `RoomEngine` implements it trivially
(always `None` for room games). **+2 lines**, consistency only.

While there: `loner3e/engine.py:157-159` and `breathless/engine.py:163-165` are identical bodies
differing only in the dump function (`_revised` vs `_authored`), and the `AUTHORING` prose in
`breathless/worldsmith.py` and `twentyfourxx/worldsmith.py` shares three sentences **verbatim**
("The cast carries no dice until the player hires them in play…" — verified by diff). Duplicated
prompt prose drifts silently and no golden fixture catches an intentional-looking divergence. Move
the shared sentences to a constant beside `HIRED` in `engines/hiring.py`. **−4 lines.**

**10b. `RoomEngine`'s type parameters are in the opposite order to `Engine`'s.**
`class RoomEngine[N: Dweller, P: Person, G](Engine[P, N, G])` (`rooms/engine.py:55`) puts the
member first and the player second. `Engine[P: Person, M: Person, G]` (`seam.py:61`) and
`SceneEngine` (`Engine[C, C, G]`) do not. Reading `RoomEngine[Npc, Goon, TunnelGoonsGame]`
requires remembering the flip. Swap to `[P, N, G]`. **0 lines.**

**10c. The bigger question: `rooms/` is a generic family with one shipped engine.**

`rooms/` is 884 lines of Python — `RoomEngine[N, P, G]`, `Dungeon[N]`, `MapDraft[N]`,
`RegionDraft[N]`, `RoomWorld[N, P]` — with 25 generic annotations. Exactly one shipped engine
instantiates it: tunnelgoons (`Npc`, `Goon`). The only other user is a test double,
`tests/support/sixth.py`. CLAUDE.md says *"Do not add an abstraction until two things need it."*
Compare `scenes/`, which has three real users and is fully earned.

This is the one thing in `src/` that a senior reviewer may read as speculative generality.

Three options, and they are genuinely different bets:

- **(a) Leave it.** It costs 25 sets of brackets and is already paid for. `IDEAS.md` #18 (Maze
  Rats) might bring a second user — though the note there says that engine would rewrite the world
  on its own actor/item/place model, i.e. it probably would *not* use `rooms/`. **0 lines.**
- **(b) De-generify in place.** Drop `[N]`/`[P]` and make `Dweller`/`Person` concrete.
  **About −8 lines** and a large readability win. **But:** `tests/support/sixth.py` instantiates
  the family with `Dweller`/`Person` precisely to prove it is engine-agnostic. De-generifying
  forces that fixture to use tunnelgoons' concrete types, which would make `rooms/` import from
  `tunnelgoons/` — backwards. So (b) really means (c).
- **(c) Fold `rooms/` into `tunnelgoons/`.** One package, no generics, `family_dir` indirection
  gone, `rules.md` and `worldsmith.md` merged into tunnelgoons'. **About −35 lines** and one fewer
  package, but `tests/support/sixth.py` (99 lines) and much of `tests/engines/test_rooms.py` (418
  lines) would have to be rewritten or dropped, and reviving a second room-crawler later means
  re-extracting the family.

**DECIDED: take 10a and 10b (−2 net). Leave the family generic (10c option (a)).**

`rooms/` stays as it is. Revisit only if a second room-crawler actually lands — and note that
`IDEAS.md` #18 says Maze Rats would rewrite the world on its own actor/item/place model, so it
probably would not be that second user either. If `rooms/` still has one shipped engine after
MVP0, fold it then, when the ~500 lines of test rework is not competing with a launch.

---

## Considered and deliberately left out

Verified, real, but below the top 10:

- **`world_of` is written five times** (`seam.py:333`, both families, three engines, −12).
  Collapsing it needs a fourth type parameter `W: World[Any, Any]` on `Engine`, and `Game[P]`
  invariance is exactly the case CLAUDE.md flags as the one place `Any` is unavoidable. The three
  engine-level ones are genuinely typed and earn their lines.
- **`ui/game.py` is 734 lines with a 529-line `GamePage`** doing four jobs. The natural split
  (the composer into its own module) is **+37 lines**, against your stated preference. The cheap
  half — moving the stateless renderers `_card`, `_dice_group`, `_bubble`, `_inline_status`,
  `_clock` into `widgets.py` — is ~0 lines and takes `game.py` to ~656. Say the word if you want it.
- **`actor_id: Slug | None = Field(default=None, description=ACTOR)` appears 13 times**
  (24XX ×7, breathless ×4, base ×1, tunnelgoons ×1). A shared base would move it to the front of
  every tool schema, which is the same prompt-order cost as decision 5B for a smaller prize.
- **`breathless` overrides `Engine.answer`** (`engine.py:264-268`) to special-case one pending
  option, where tunnelgoons and 24XX solve the identical problem by registering a real tool and
  naming it in the option. Breathless's reason is real (`granted` is rolled, so the master must not
  hand itself a d12), but tunnelgoons' `LevelUp.actor_id` has the same hazard and handles it with a
  `"Leave empty."` description. Three engines, three answers. Fixing it properly means a second
  registry on the seam; worth doing after MVP0.
- **`preview_character` and `World.sheet_rows` answer the same question at two layers**, and in
  24XX they disagree: the creation preview shows gear names, the in-play panel shows names plus
  notes. Collapsing them changes what the master's `THE PARTY` block prints. Product call, not a
  refactor.
- **`Literal` aliases with a hand-written member tuple** — `Die`/`LADDER`, `Skill`/`SKILLS`,
  `Ability`/`ABILITIES`, `SkillDie`/`LADDER`. `config.py:152` already derives members with
  `get_args(Role.__value__)`; the engines spell them twice. Deriving them trips strict-mode
  inference, so it costs more than it saves.
- **`Role` lives in `config.py` but is a domain type** — `ui/game.py:14` imports it and nothing
  else from `config`. Moving it to `core/play.py` is 0 lines and 9 files of import churn.
- **`reportUnusedFunction` could move to `pyproject.toml`**, replacing five inline
  `# pyright: ignore` in `ui/app.py`. +1 line, but it disables the check project-wide.
- **The property rule bends four times** — `Subject.row()`, `NarratorView.others()`,
  `Turn.narrates()`, `Turn.landed()`. +4 lines for consistency. `Game.exchanges()` is the same
  shape with ~50 test call sites; leave that one.
- **`digest()` in `core/io.py`** would get `hashlib` out of `ui/widgets.py:27` and dedupe three
  `sha1(...)[:12]` sites. +1 line.
- **`typed(box)`** for the 13 repeats of `(x.value or "").strip()`. +1 line.
- **The hidden-name leak check exists twice** — `rooms/worldsmith.py:68-71` and
  `scenes/worldsmith.py:75-79`, the same five statements. Extracting `leaked_names` to
  `engines/base.py` saves 1 line; the two callers build `hidden` differently, so it is the most
  delicate extraction here for the least gain.
- **`Reader._planned` returns a three-deep anonymous tuple** (`app/speech.py:78-81`) and `clip`
  discards two thirds of it; `key` is derivable from `path.stem`. +1 line.

## Checked and clean — do not re-derive

- **Save/load**: `Engine.restore` (`seam.py:179-186`) is the only path; no engine overrides it.
- **Tool registration**: all six engines use `(*super().master_tools(), ...)`, and
  `Engine.__init__` already rejects a duplicated tool name. The ~20 two-line tool adapters look
  collapsible but are not — a generic splat helper needs `Callable[..., ...]` and `**kwargs`,
  which is `Any` in all but name. Item 3 is the one genuinely reducible adapter.
- **Naming rule** (`id`/`label`/`detail` shown, `name`/`brief` on disk): holds everywhere.
  `Thing.subject()` (`base.py:106-107`) is the single conversion point. `PendingOption.name` and
  `MasterTool.name` are wire names, correctly exempt.
- **Enum vs literal vs str**: consistent. Zero `Enum` in `src/`; every closed set is a PEP-695
  `type X = Literal[...]`.
- **`Refusal` vs bug**: correct. No validator raises `Refusal` directly. Both broad
  `except Exception` (`source.py:31`, `mcp.py:94`) are justified and commented.
- **Module layout** (imports, constants, classes, public, private): holds in all 40 non-empty
  modules, including the awkward cases.
- **Empty `__init__.py`**: all 12 are zero bytes.
- **Docstring discipline**: single-line, reason-only, ~1 per 25 lines, consistently.
