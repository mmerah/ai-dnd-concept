# PROPOSALS — code quality and pattern consistency in `src`

Scope: `src/aidm` only (10,069 lines). No feature work.

**Baseline.** `uv run pytest` (655 passed in 7s), `ruff check`, `ruff format --check` and
`basedpyright` (0 errors under `uv sync --all-groups`) are green today, and
`tests/core/test_package_boundary.py` proves the `core <- engines <- turn <- app <- ui` flow holds
with no cycles and no settings leaking below `app`. Nothing below is a lint fix.

**Method.** One reviewer per layer (core/seam, the six engines, app/turn/ui), plus a full read and
a clone scan. Every factual claim was re-verified against the running code.

**Ranked by lines removed, as asked.** Part 1 deletes code. Part 2 is the three reorganisations
that *cost* lines and buy reviewer-legibility instead — kept, ranked last, and labelled honestly so
you can refuse them on that basis alone.

| | Net `src` LOC |
|---|---|
| Part 1 (proposals 1-12) — **all settled** | **−167** |
| Part 2 — 13 settled (option C) | **+5** |
| Part 2 — 14, 15 pending | +0 to +47 |
| Settled so far | **−162** |

LOC figures are estimates from the actual blocks, ±20%.

**Honest headline:** there is no large LOC win hiding in this codebase. There is no dead code —
I checked every function in `src` for callers and found none unreachable. The wins are ~170 lines
across twelve small, verifiable deletions. Anything bigger would be re-architecture, not cleanup.

**Status key.**

| | |
|---|---|
| **AUTO** | No feature impact and the code shrinks. Accepted unless you object. |
| **CALL** | Needs your decision — options listed. |
| **BEHAVIOUR** | Something a player or a role would notice. Never auto-accepted. |
| **SETTLED** | Your decision is recorded on the proposal. |

---

# Part 1 — removes code

## 1. The one-line sweep — **−45 lines** — **AUTO**

Eighteen fixes, each a handful of lines, none needing a decision. About **90 minutes** together.
Strike any row you disagree with.

| # | Now | Becomes | LOC |
|---|---|---|---|
| S1 | `core/entities.py:10-11` — `Slug` is the only type alias in the repo spelled as a bare assignment, defended by the comment `# assignment, not 'type': pydantic reads the metadata`. **The comment is false on pydantic 2.13.4** — I verified the pattern is still enforced through a `type` alias as a bare field, as `Slug \| None`, inside `tuple[Slug, ...]` and as a `dict[Slug, int]` key. | `type Slug = Annotated[...]`, comment deleted | −1 |
| S2 | `ui/app.py:183-188` wraps a `Refusal` into `str \| None` for one page, forcing `ui/settings.py:19`'s odd `Awaitable[str \| None]` signature and a branch at `:73-78` | pass `runtime.reload_settings` directly; `SettingsForm.save` catches `Refusal` as `create.py:132,291` and `game.py:576` already do | −10 |
| S3 | `engines/hiring.py:45-50` `_no_check` declares a typevar solvable only from the default position it occupies — generic gymnastics standing in for `\| None = None`. It is also this module's one private function placed **above** the public one, the only CLAUDE.md module-layout violation in `src` | `check: Callable[[G], Check[A]] \| None = None` | −5 |
| S4 | `app/runtime.py:341-352` — `Runtime` has four `field(init=False)` attributes with **no default**, so `Runtime(settings)` is legal Python and returns an object where `engines`, `spawner`, `library` and `store` each raise `AttributeError`. Only `Runtime.start()` works, and nothing in the type says so | move `start`'s two lines into `__post_init__`; delete `start` or keep it as a one-line alias | −4 |
| S5 | `config.py:124-128` spells the three roles a **fourth** time (after `type Role`, the fields, and `for_name`'s `match`) — and it is the only one of the four that basedpyright does not exhaustiveness-check, so a new role can be forgotten here silently | `for role in get_args(Role)`, as `ui/settings.py:141` already does | −4 |
| S6 | `engines/scenes/packs.py:24` re-implements `core/io.py:207 _read` by hand, but calls `path.read_text` directly — so an unreadable or non-UTF-8 pack raises `OSError`/`UnicodeDecodeError` instead of the `Refusal` every other file read in the repo produces | make `_read` public as `read_model(path, model)` and call it | −4 |
| S7 | `tunnelgoons/engine.py:169-174` raises a `Refusal` for a state `Roll._one_target` (`tools.py:43`) has already made impossible, duplicating the validator's message. CLAUDE.md: an unreachable state is a bug, not a message | restructure so the narrowing is honest, as `engine.py:210` already does for `LevelUp` | −2 |
| S8 | `app/spawn.py:119` and `:251` hold the same event-stream parse verbatim | one `_events(output)` beside `_object` | −2 |
| S9 | `app/speech.py:43` and `:49` both open with the same three-step walk (`requests_of` → `clip_key` → `_path`) | one `_planned(exchange)` returning all three | −4 |
| S10 | `core/views.py:78-79` hand-rolls `len(set(...)) != len(...)`, losing the offending ids from the message, one layer above `base.py:208` doing the same check on the same data through the helper | `check_unique("party members", self.party)` — *message text changes* | −1 |
| S11 | `breathless/world.py:157` `take_loot` returns a bare `Fact` — the **only** one of 46 world/entity mutators that does not return `list[Fact]` | `list[Fact]`; drop the tuple-wrap at `breathless/engine.py:261` | −1 |
| S12 | `core/views.py:59` `place: str`, while both producers hand it a `Slug` and the consumer hashes it *because* the type is `str` (`media.py:167` `"""Hashed because 'place' names a file."""`) | `place: Slug` | 0 |
| S13 | `core/io.py:158` `read_prompt` also reads **CSS** at `ui/theme.py:69` | rename `read_cached_text`; 8 call sites | 0 |
| S14 | `engines/hiring.py:10,15,35` hold `ACTOR` (used on **13** `actor_id` fields across three engines, none of them hiring tools) and `DROP_ITEM`/`DropItem` (an inventory tool). A reader opening `hiring.py` for the hire flow finds neither | move all three to `engines/base.py`, beside `Reveal`/`Kill`/`JoinParty`/`LeaveParty` and their constants, which are exactly this shape | 0 |
| S15 | `engines/seam.py:101,133,329` call `self.hiring()` three times to probe a flag — each call *builds* the writer closure and throws it away | `self.hire_writer = self.hiring()` in `__init__`, beside the other derived state | −2 |
| S16 | `engines/seam.py:327` — a concrete `worldsmith_requests` is wedged between two runs of abstract methods, 230 lines from its twin `master_tools` (`:93`), with which it shares a docstring sentence. `:66-79` puts 13 bare annotations in one run: 10 the subclass contract, 3 built by `__init__` | move it beside `master_tools`; split the annotation block with one comment on each half | +2 |
| S17 | `config.py:96` — `Settings` is the one config model **not** frozen (verified: `RoleConfig.model_config['frozen'] is True`, `Settings`'s is `None`), while all six of its nested configs inherit `Configured(Frozen)` and nothing anywhere assigns to a `Settings` field | add `frozen=True` | +1 |
| S18 | `ui/create.py:296` `_discard_uploads()` runs only on success; the refusal path returns at `:293`, and an abandoned page leaks its temp dir — acknowledged in the comment at `:301` | `ui.context.client.on_disconnect(self._discard_uploads)` in `build()` — covers both | −1 |

---

## 2. 24XX's `Roll` and `Helper` duplicate what they stake — **−18 lines** — **SETTLED: A**

**Now.** `twentyfourxx/tools.py:85-146`. `Helper` and `Roll` repeat the same three fields and the
same validator. `hindrance` (5 lines) and `_defend_fields` (7 lines) are **byte-identical**;
`risk` and `defend_with` differ by one word each ("the helper" / "the actor"):

```python
    defend_with: Slug | None = Field(
        default=None,
        description="Exact id of the helper's item or a ship function that breaks to spare "
        "them. Null when nothing shields them.",
    )
    hindrance: str = Field(
        default="",
        description="What the hit leaves behind once the gear absorbs it, as a hindrance. "
        "Empty when the gear breaks harmlessly.",
    )

    @model_validator(mode="after")
    def _defend_fields(self) -> Self:
        if self.defend_with is not None and not self.risk:
            raise ValueError("defend_with needs the risk it shields against")
        if self.hindrance and self.defend_with is None:
            raise ValueError("hindrance needs the defend_with that earns it")
        return self
```

This is the largest verbatim clone in `src`.

**Change to.** A `Risked(Frozen)` base in the same module carrying `risk`, `defend_with`,
`hindrance` and the validator. `Helper(Risked)` keeps only `actor_id` and `hindered`;
`Roll(Attempt, Risked)` keeps only its own five fields.

**Feature impact.** None, under option A.

**Decision 2 — settled: A.** Build the two descriptions from one template with a `{who}` slot:
`DEFEND_WITH.format(who="the helper's")` / `.format(who="the actor's")`. The rendered text is
byte-identical, so `tests/core/fixtures/schemas/twentyfourxx/master_tools.json` must **not** move
— that golden staying green is the acceptance test for this change.

**Size.** 1 file, **25 min.**

---

## 3. 24XX's `roll` resolves the helper once, not four times — **−12 lines** — **AUTO**

**Now.** `twentyfourxx/engine.py:394-443`. `_helping` returns `Crewmate | None` while
`args.helped_by` stays a separate `Helper | None`, so every use re-narrows both — four times:

```python
if helper is not None and helper_args is not None:                   # :404
    if (helper_item_id := helper_args.defend_with) is not None:      # :406
if helper is not None and helper_args is not None and helper_args.risk:   # :420, :429
if helper is not None and (helper_args := args.helped_by) is not None:    # :463
```

**Change to.** Return the pair as one object, so one check narrows both:

```python
@dataclass(frozen=True, slots=True)
class Helping:
    member: Crewmate
    args: Helper

def _helping(world: TwentyfourxxWorld, args: Helper | None) -> Helping | None:
    return None if args is None else Helping(world.require_actor(args.actor_id), args)
```

Call sites become `if helping is not None and helping.args.risk:`. The `helper_args =
args.helped_by` local (`:398`) goes away with it.

**Why it matters.** This is the least readable block in the six engine packages — 50 lines of
`roll` where a third of the conditions restate something the caller already knows, and the only
place in the engines where a `| None` value and its companion are tracked separately.

**Feature impact.** None. **Size.** 1 file, **30 min.**

---

## 4. Fold the two near-identical map checks in `rooms` — **−12 lines** — **AUTO**

**Now.** `rooms/worldsmith.py:38-63`. `_start_unmet` and `_extension_unmet` are twelve lines
duplicated with one boolean inverted — `check_map` wants the start place known to the player,
`check_extension` wants it hidden. Everything else is the same.

**Change to.**

```python
def _map_unmet[N: Dweller](draft: MapDraft[N], *, start_known: bool) -> list[str]:
    places = draft.places
    if draft.start not in places:
        return [f"a starting place {draft.start!r}"]
    unmet: list[str] = []
    if places[draft.start].known != start_known:
        unmet.append("the starting place known to the player" if start_known
                     else "a starting place hidden from the player")
    if missing := sorted(set(places) - draft.reachable(draft.start)):
        unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    return unmet
```

`check_extension` keeps its own `if not places:` guard and passes `start_known=False`.

**Feature impact.** None — same refusal strings, same order. **Size.** 1 file, **20 min.**

---

## 5. `RoomWorld`: one way-opener, one `others()` — **−10 lines** — **AUTO**

**Now.** Two duplications in `rooms/world.py`, both confirmed by the clone scan:

- `move` (`:197-212`) and `unlock_way` (`:239-249`) each spell out the same four-line
  "reveal the way and its back-way" block:
  ```python
  way.known = True
  back = self.way(destination.id, here.id)
  if back is not None:
      back.known = True
  ```
  and the same three-line lookup preamble before it.
- **"Who else is here"** is filtered in the *view* (`rooms/engine.py:132-137`) and again inside
  `place_lines` (`world.py:336-337`) — while `scenes/world.py:130` owns the identical filter as
  `others()` and its engine simply asks (`scenes/engine.py:197`). Views should ask, not filter.

**Change to.** A private `_open_way(here, destination)` on `RoomWorld`, and a public
`others()` beside `things_at`:

```python
def others(self) -> Iterator[N]:
    return (npc for npc in self.at(self.current.id) if npc.known and npc.id not in self.party)
```

**Feature impact.** None. **Size.** 2 files, **20 min.**

---

## 6. Delete the `description=` prose no schema ever publishes — **−9 lines** — **AUTO**

**Now.** In this codebase `description` has exactly one job: it reaches a model through
`schema_of` / `schema_text`, and `master_tool` (`core/tools.py:38`) *enforces* it on tool args.
There are five `schema_of`/`schema_text` call sites — I checked all five.

`core/play.py:94-102` gives `Answer.option_id` and `Answer.text` carefully written descriptions.
`Answer` is only ever constructed in `ui/game.py:290,468,476` and `app/runtime.py:143,152`. It is
never parsed from model output and never published. Same for `core/model.py:29-33`
`ScenarioMeta.scope`, whose player-facing wording already lives at `ui/create.py:240` as the
textarea placeholder.

Prose written for a reader who never sees it is the most expensive kind of dead code: the next
reader assumes the model reads it and maintains it forever.

**Change to.** `option_id: Slug | None = None`, `text: str = ""`, and `scope: str =
Field(min_length=1)` (the length rule is live; the prose is not).

**Feature impact.** None. **Size.** 2 files, **10 min.**

---

## 7. Collapse the repeated NiceGUI boilerplate — **−25 lines** — **SETTLED: A**

**Now.** Two things, both in `ui/`:

- The decision banner is **verbatim** at `game.py:280-284` and `game.py:321-325` (found by the
  clone scan):
  ```python
  with (
      ui.row()
      .classes("game-card game-decision w-full items-center no-wrap")
      .style("gap: 0.4rem")
  ):
      ui.icon("record_voice_over").classes("game-card-icon")
  ```
- **37 inline `.style(...)` calls across `ui/*.py`, of which 32 are nothing but `gap:`** — seven
  `gap: 0`, five `gap: 0.5rem`, five `gap: 0.4rem` — and `widgets.py` spells them `.5rem`/`.2rem`
  while `game.py` spells the same values `0.5rem`/`0.2rem`. `theme.py:12` calls itself
  *"The single source for every hex value"*; the spacing scale belongs in the same place.

**Change to.** A `banner(icon)` context manager in `ui/widgets.py` beside `section()`, and
`.game-gap-0` / `-sm` / `-md` classes in `theme.css` replacing the inline gaps. Most of those
inline styles are the third line of a chained builder call, so each one removed is a line removed.

**Feature impact.** None if the classes carry the same gap values — pixel-identical.

**Decision 7 — settled: A.** Banner **and** the full gap sweep: every inline `gap:` in `ui/*.py`
becomes a `.game-gap-*` class in `theme.css`. −25 lines, 6 files, **40 min.** The `qa/` Playwright
screenshots are the check that nothing moved a pixel.

---

## 8. `breathless`'s loot roll reads its bands by hand — **−8 lines** — **AUTO**

**Now.** `breathless/engine.py:275-280` hand-rolls the 1-2 / 3-4 / 5+ bands twenty lines after the
same file reads exactly those bands through the shared helper:

```python
# :224  result = banded(rolled.kept, "fail", "success-but", "success")
# :275  if face <= 2: ...  elif face <= 4: ...  else: found = next(...)
```

The two note strings at `:276` and `:278` are also the only master-facing prose in this engine
written inline rather than as module constants — compare `TWIST_NOTE`/`DEFEAT_NOTE` at
`loner3e/engine.py:46-56`.

**Change to.** `outcome = banded(face, "trouble", "nothing", "found")`, keeping the `LADDER` lookup
for the find size, and lift the two notes to constants.

While there: `base.banded`'s docstring (`base.py:340`) says *"The three bands of a six-sided
read"*, but its actual callers read d4-d12 pools. Reword to "1 to 2, 3 to 4, 5 and up, whatever
the die."

**Feature impact.** None — identical bands. **Size.** 2 files, **25 min.**

---

## 9. Give the scene-engine pack machinery an owner — **−7 lines, −9 methods** — **AUTO**

**Now.** `engines/scenes/engine.py` carries nine methods that are all about the installed pack set
and nothing about playing: `supplement_options` (`:100`), `select_packs` (`:107`), `selected`
(`:114`), `selected_packs` (`:118`), `chosen_packs` (`:121`), `supplement_steps` (`:239`),
`srd_pack` (`:252`), `pack_content` (`:255`), `select` (`:268`). `SceneEngine` ends up with ~30
public methods. The state they all read is `self.packs: dict[Slug, K]`, and it has no owner —
CLAUDE.md's first rule points the other way.

`pack_content` is the worst: `(selection, *, include=None, exclude_defaults=False)` — two mutually
exclusive knobs used by exactly one caller each (`breathless/engine.py:157` passes `include=`,
`loner3e/engine.py:160` passes `exclude_defaults=`, `twentyfourxx` never calls it).

**Change to.** A `PackSet[K]` value object in `engines/scenes/packs.py` with `srd()`,
`supplements()`, `select()`, `require()`, `chosen()` and `content(selection, dump)`. `SceneEngine`
holds `self.packs: PackSet[K]` and keeps three thin methods the seam contract needs. Call sites
read `self.packs.srd().skills` — same length, and it now says where the data lives.
`content`'s single `dump` callable replaces the two knobs; each engine passes its own lambda next
to the constant that explains it.

**Feature impact.** None. The worldsmith prompt goldens must render byte-identical —
**verify, do not regenerate.**

**Size.** `packs.py` 27 → ~68 lines; `scenes/engine.py` −55; ~20 call-site prefixes across three
engines. **60 min.**

---

## 10. Delete the hand-rolled card prefixes — and give 24XX the names it never prints — **−8 lines** — **ACCEPTED**

**Now.** `base.py:86` exists for exactly this, and is used in `base.py:94` and four times in
`loner3e/world.py`:

```python
def card_line(self, line: str) -> str:
    return line if self.id == PLAYER_ID else f"{self.name}: {line}"
```

Everywhere else the decision is re-made by hand, or not made at all:

- **Hand-rolled** — `breathless/world.py:150-154` is a three-line conditional producing exactly
  `card_line`'s output; `tunnelgoons/world.py:56-58` is another.
- **Three names for one inline expression** — `prefix` at `breathless/engine.py:234` and
  `twentyfourxx/engine.py:413`, `who` at `tunnelgoons/engine.py:184`.
- **Missing entirely** — verified: `card_line` appears **nowhere** in `twentyfourxx/`. Every
  `Crewmate` card is unprefixed: hindrances (`:121`), `gain_item` (`:130`), `repair_item` (`:138`),
  `spend` (`:143`), `maim` (`:150`), `raise_skill` (`:162`), `earn` (`:170`). When a hired crew
  member picks something up, the player's card feed says **"Gained Rope"** with no name on it.
- **Split inside one engine** — breathless prefixes `change_stress` (through `base.change`) but not
  `use_med_kit` (`world.py:129`).

**Change to.** Every card that can belong to someone other than the player goes through
`self.card_line(...)`. The three mid-line roll prefixes cannot (the name sits inside the sentence)
— there, settle on the name `prefix` in all three.

**Feature impact.** Card text changes for hired members: `"Caught breath — …"` becomes
`"Mira: Caught breath — …"`, and 24XX crew cards gain a name they never had. This fixes a real
readability bug, and you have accepted the visible change. Tests assert the old strings at
`tests/breathless/test_world.py:156`, `tests/breathless/test_tools.py:105`,
`tests/tunnelgoons/test_world.py:98`.

**Size.** 5 engine files + 3 test files, **35 min.**

---

## 11. `require_member_here` means two different things in the two families — **−3 lines** — **ACCEPTED**

**Now.** `base.py:224` declares the contract: *"Alive and here with the player."*

`rooms/world.py:161` looks only in `npcs`, so the player's own id is refused cleanly.
`scenes/world.py:127` is a bare alias with no body of its own:

```python
def require_member_here(self, entity_id: Slug) -> C:
    return self.require_living_here(entity_id)
```

and `require_living_here` → `require_here` (`:105`) returns the player for their own id.

**I ran it.** In a scene engine, `join_party` on `"player"` does **not** refuse. It appends the
player to `party`, writes the fact `Kael[player] travels with the player`, and only blows up at
commit with `the state this leaves is invalid: payload: Value error, the player cannot travel with
themselves`. In tunnel goons the same call refuses at once with `unknown id 'player'`.

`SceneWorld` also carries four resolvers for three jobs: `require` (`:97`), `require_here`
(`:105`), `require_living_here` (`:116`), `require_member_here` (`:127`).

**Change to.** Delete the alias, rename `require_living_here` → `require_member_here` (the name the
base declares), and give it the guard rooms already has:

```python
if entity_id == self.player.id:
    raise Refusal("the player is not a party member")
```

**Feature impact.** `join_party` and `hire` on the player's own id now refuse with a readable
message instead of failing at commit. Strictly better, but the game master reads different text.

**Size.** 3 src files + 2 test files, **25 min.**

---

## 12. Publish a drawn icon **inside** its claim — **0 lines** — **AUTO**

**Now.** `app/media.py:109-116`. The claim is released at the `with` exit — *before the file
exists*:

```python
with self.claims.hold(f"icon:{subject.id}") as drawing:
    if not drawing:
        return None
    generated = await self._generate(...)
path = self.saves / ICON_DIR / f"{subject.id}{generated.suffix}"
publish(path, lambda staged: staged.write_bytes(generated.data))
```

A second caller entering `_drawn_icon` in that window fails the cache check (no file yet), wins the
freed claim, and pays the image provider for the same icon **again**. `Claims` exists precisely so
*"two callers never both pay for one image or clip"* (`providers.py:13`), and both sibling paths
get it right — `_draw` and `Reader.read` publish inside the hold.

**Change to.** Move the two lines inside the `with`.

**Feature impact.** None visible. Closes a paid-API double-spend race. The only zero-LOC item in
Part 1; it earns its place because it is a live bug and costs five minutes.

---

# Part 2 — costs lines, buys legibility

These do **not** reduce LOC. They exist because a senior reader's first judgement is formed by
file size and class shape, and `ui/game.py` and `GameService` are what they will open first.
Refusing any of them on the LOC ground alone affects nothing else in the report — as 13 shows,
where the split was refused and the defect under it fixed in place for +5 lines instead of +40.

## 13. Constructors that leave the object half-built — **+5 lines** — **SETTLED: C**

*(Proposed as a three-way split of `ui/game.py`. Split refused on the LOC ground; this is option C
— the underlying defect fixed in place.)*

**Now.** Three UI classes declare attributes as bare annotations with **no value**, so the object
is unusable until a second method runs, and the type checker believes the attributes are always
there:

| Class | Where | Unset attributes | Made valid by |
|---|---|---|---|
| `GamePage` | `ui/game.py:96-116` | 14 | `build()`, 70 lines later |
| `ScenarioForm` | `ui/create.py:157-170` | 7 | `build()` → `form()` |
| `CharacterForm` | `ui/create.py:24-31` | 2 | `build()` |

`GamePage(runtime, session).refresh()` raises `AttributeError`. This is the one pattern in `src`
that reads as unfinished to an outside reader: a constructor that does not establish the object's
invariants, with the type system asserting otherwise.

(`Runtime`'s four `field(init=False)` attributes are the same defect and are already fixed in the
sweep, S4.)

**Change to.** Build the widgets where they are declared, and drop the bare annotations.

- `GamePage`: move the widget construction from `build()` into `__init__` where it does not depend
  on NiceGUI slot context, and give the rest honest `| None = None` types with the one assignment
  in `build()`. No attribute keeps a bare annotation.
- `CharacterForm`: `self.name` / `self.brief` are built at `create.py:43-47` inside `build()` —
  move them up.
- `ScenarioForm`: `form()` is `@ui.refreshable_method` and legitimately rebuilds its seven widgets
  on every engine change, so pre-declaring cannot be avoided by moving code. Instead, have `form()`
  **return** its widget set as a small frozen `Fields` dataclass and assign
  `self.fields: Fields | None = None` in `__init__`. One honest optional replaces seven lies.

**Code impact.** ~40 lines touched across `ui/game.py` and `ui/create.py`. `ui/game.py` stays one
file at 692 lines. `tests/ui/test_game.py` constructs `GamePage` — check it still does.
**30 min.**

**Feature impact.** None.

**What C gives up.** `ui/game.py` remains the largest file in the repo, `GamePage` keeps 31
methods, and the transcript renderers stay stranded in a page module. If a reviewer's first move is
`wc -l src/aidm/ui/*.py`, that is what they see. The defect that actually breaks — the unset
attributes — is fixed either way.

## 14. `GameService` does six jobs — **+35 lines** — **CALL**

**Now.** `app/runtime.py:45-338`, ~295 lines, 17 fields, 30 members: session lifecycle, turn
orchestration, worldsmith growth, party interjections, an asyncio task nursery, **and** media
fan-out. The `Illustrator | None` / `Reader | None` pair is threaded through `resume()`'s keyword
list (`:68-99`), `Runtime._open` (`:465`) and nine methods purely to answer "is media on?".

**Change to.** `app/present.py` — a `Presenter` owning `presents`, `scene_art`, `icon`,
`newest_clip`, `illustrate`, `speak`, `_present`; and `app/background.py` — a `Tasks` nursery
owning `_background`, `_retain`, `_settled`, `settled` and the cancelling half of `close`.
`GameService` lands at ~17 members and reads as one job.

**Code impact.** 2 new files, `runtime.py` −90. `tests/app/test_game_service.py:536-542` pokes
`game._retain`/`game._background`; `tests/support/table.py:263` calls `service.settled()`.
**60 min.**

**Feature impact.** None.

**Decision 14.**
- **A.** Both extractions, keeping four one-line delegating methods on `GameService` so `ui/` is
  untouched. **+35 lines.**
- **B (recommended, given the LOC preference).** `Tasks` only — it is generic plumbing with no
  relation to playing a turn, and it is the half that reads as misplaced. **+12 lines.**
- **C.** Neither.

---

## 15. Four async and resource defects — **+12 lines** — **CALL**

Four unrelated small defects in the same area, cheapest to fix together.

**15a. One `AsyncClient`, not one per request.** `app/providers.py:38-49` builds and tears down a
connection pool on every call. `builtin._complete` calls it once per conversation round — up to
`max_rounds = 30` (`config.py:38`) per master turn — and `speech.read` (`:63-70`) calls it once
**per spoken line**. That is a fresh TLS handshake each time. *+10 lines, 4 files.*

**15b. Blocking disk writes on the event loop.** `Runtime.new_scenario` correctly threads its
blocking read (`runtime.py:442`, `await to_thread(...)`). Four identical calls are **not** threaded,
with no comment saying why: a multi-MB WAV write (`speech.py:72-79`), two multi-MB image writes
(`media.py:98-101`, `:115`), and up to four reference-image reads per scene (`media.py:213`). They
block the single loop that also serves every open tab's 1 Hz poll. The defect is the
*inconsistency* as much as the blocking. *+4 lines.*

**15c. The killed child is never reaped.** `spawn.py:240-251`: on the timeout path `communicate()`
is cancelled mid-read, `_kill` sends `SIGKILL` and returns immediately, and nothing awaits the
process — the classic source of `ResourceWarning: subprocess N is still running` at shutdown. Make
`_kill` async and `await process.wait()` after the signal. *+3 lines.*

**15d. The page rebuilds everything at 1 Hz.** `poll_turn` (`game.py:187`) calls `refresh()`
(`:191-198`) whenever *anything* in `Observed` differs — including `facts`, which increments
several times per turn. `refresh()` rebuilds the **entire** chat history (one `ui.chat_message` per
line of every exchange) and the **entire** chronicle (one `ui.expansion` per turn played). A
50-turn game rebuilds 50 expansions and the whole transcript up to ~10× per turn. `Observed`
(`:67-83`) already carries exactly the five fields needed to tell "a fact landed" from "the turn
closed", so the fix is a `whole: bool` parameter. *+3 lines.* **BEHAVIOUR** — visible as *less*
flicker mid-turn.

**Decision 15 — which to take.**
- **A (recommended).** All four. **+12 lines, ~75 min.**
- **B.** 15b + 15c only (the resource leaks), leave the client and the refresh. **+7 lines.**
- **C.** 15d only — the one a player can see. **+3 lines, 15 min.**
- **D.** None.

---

# Also found, ranked out

Promote any of these and I will fold it in. None of them removes more than a handful of lines.

- **Six methods never touch `self`** — the sharpest pair in one file: `twentyfourxx/world.py:245`
  `TwentyfourxxWorld._break` mutates a `Crewmate`'s sheet and a `Gear` and lives on neither, while
  its mirror `Crewmate.repair_item` (`:132`) does the same job the right way 113 lines above. Also
  `loner3e/world.py:163 strike`, `:176 check_conflict`, `breathless/engine.py:297 _pool`,
  `loner3e/engine.py:170 _meanings`. CLAUDE.md is explicit about this. *±0 lines, 40 min.*
- **Property-vs-method.** CLAUDE.md: *"A property takes no argument, has no side effect and reads
  its own fields."* `base.py:58` `Thing.tag` and `:62` `Thing.headline` are **properties literally
  implemented as** `self.subject().tag` — where `subject()` (`:103`) is a **method** meeting the
  same definition. Also `Game.exchanges()`, `Thing.rows()`, `Sheeted.carried()`,
  `Person.forbidden()`, `Item.notes()`, `World.sheet_rows()`. Cheapest honest fix: one line on
  `Thing` saying hooks stay methods. *−0 to −8 lines depending on scope.*
- **Bare dice numbers.** LONER 3E names its die once (`DIE_FACE`) and uses it in the tool, the roll
  and the pack validator. Nobody else does: bare `6` twice in `twentyfourxx/engine.py:476,492`,
  `roll((12,), ...)` in `breathless/engine.py:252` (whose `12` is silently coupled to a
  `min_length=12` in `breathless/worldsmith.py:31`), `if worn == 4` in `breathless/world.py:137`,
  `granted >= 10` twice, `roll((6, 6), ...)` in `tunnelgoons/engine.py:180`, and `"Hull armor"`
  repeated 162 lines from `SHIP_FUNCTIONS`. Three tool descriptions also retype a constant's value
  in the text the model reads — a drift that becomes a play bug, not a lint. *+8 lines.*
- **Widen the ruff rule set.** `pyproject.toml:55` selects `E, F, I, UP, B, TID252, N, ARG`. Adding
  `SIM, RUF, C4, RET, PERF` catches exactly the drift this report is full of, automatically, for
  free from here on; `FBT` has at least one real hit (`ui/widgets.py:22`
  `page_header(title, badge=None, home=True, *, look=None)` takes a positional bool while every
  other boolean in `src` is keyword-only). A reviewer opens `pyproject.toml` before any source
  file. *Removes lines wherever it fires. ~1 h.*
- **Split `app/spawn.py`.** 311 lines holding five jobs. `run_cli`'s docstring says *"The only
  thing in the codebase that starts a process"* — yet half the file never touches one, and
  `app/builtin.py:10` imports `final_message` from a module called `spawn` while running an HTTP
  loop. *+25 lines.*
- **`app/mcp.py:9` imports `Runtime`** to use two of its members, while `app/spawn.py:130` already
  declares the `Tools` protocol describing exactly that, which `Runtime` satisfies structurally.
  *−1 line.*
- **`(widget.value or "").strip()` — 12 times** across `ui/game.py:442,471,484` and
  `ui/create.py:123,129,147,151,267,268,269,279,280`. One `def typed(field) -> str` in
  `ui/widgets.py`. *−6 lines.*
- **`Look.palette` is mutable in fact.** `core/views.py:141` types it `Mapping[str, str]`; pydantic
  coerces it to a plain `dict` and I confirmed `Look(...).palette["x"] = "y"` succeeds on the built
  model — inside a `Frozen` value model. It is also the only `Mapping[...]` field on any model in
  `src`. Making it `Rows` costs ~30 lines of reshaped engine literals, which is why it is here and
  not in the sweep. *+30 lines.*
- **LONER 3E's `Roll.actor_id` is required and non-null** (`loner3e/tools.py:61`) while the other
  three engines spell it `actor_id: Slug | None = Field(default=None, description=ACTOR)`. The rule
  genuinely differs (LONER hires nobody), but the field name should not pretend otherwise — its
  three sibling tools already use `entity_id`. *±0 lines, regenerates one golden.*
- **`SceneDraft`/`NextDraft` live in `scenes/tools.py`**, so `scenes/world.py:17` imports its own
  world shape from the *tools* module. Rooms keeps the equivalent `MapDraft` in `rooms/world.py`.
  *±0 lines, 13 files touched.*
- **`tunnelgoons/worldsmith.py:25` `AbilitiesDraft` has no docstring**, while breathless and 24XX
  both name theirs `SheetDraft` *with* one. `schema_of` keeps `description`, so tunnel goons hands
  the worldsmith one line less than the other two for the same job. *+2 lines.*
- **`breathless/engine.py:161,168` render an item's die by hand** although `Supply.notes()`
  (`world.py:34`) returns exactly that, and `world.py:183` uses it correctly. *−2 lines.*
- **`PendingDecision` is built in the engine three times of five** (`loner3e/engine.py:233`,
  `breathless/engine.py:286`, `twentyfourxx/engine.py:349`) and in the world/entity twice
  (`tunnelgoons/world.py:61`, `loner3e/world.py:156`). A pending decision is a view, not a fact.
- **Three deep-copy spellings** for pydantic models in one layer: `deepcopy(x)` (`seam.py:301`,
  `model.py:122`) and `x.model_copy(deep=True)` (`scenes/engine.py:138`).
- **`tunnelgoons/world.py:47`** defines the method `level(ability, boost)` beside the field
  `GoonSheet.level: int` its own body increments, while the tool, the engine method, the option
  builder and the decision builder are all `level_*`. Rename to `level_up`.
- **`Game.generation`** (`core/model.py:109`) is `Field(default=None, exclude=True)` — a pending
  worldsmith request is silently dropped from every save, with no comment.
- **`twentyfourxx/world.py:289`** uses `.tag` for the player in a trace where every other engine
  uses `.mention`; **`:232`** keys a dict by `id(item)` with no line saying why. **`runtime.py:318`**
  calls `LOGGER.exception(..., exc_info=failed)` outside an `except`. **`ui/create.py:284`** relies
  on `or` binding tighter than a ternary. **`ui/game.py`** has five bare timer floats, two of them
  a different `0.1`.

---

# Considered and rejected

- **Fold `rooms/` into `tunnelgoons/`.** The family is 693 lines instantiated by one production
  engine, which looks like premature abstraction — CLAUDE.md: *"Do not add an abstraction until two
  things need it."* But I measured it: only 42 lines across the four files carry type-parameter
  noise, and folding turns them into concrete types at the **same** line count. Real saving is
  ~40 lines, and it costs a consistency loss (tunnel goons becomes the one engine shaped unlike the
  other three, with no `family_dir`). Not worth it. If anything, add one line to `RoomEngine`
  saying what the family *is* — "a map of places the player walks between, as against a scene
  family's run of scenes" — so the single user stops looking accidental.
- **Bind the world type into `Engine`'s generics** to delete the five one-line `world_of`
  overrides. Not possible: a PEP 695 type parameter cannot appear in another parameter's bound —
  basedpyright rejects `G: Game[W]` with *"TypeVar constraint type cannot be generic"*. The
  overrides are the correct workaround, and breathless correctly has none because `BreathlessWorld`
  is a bare `SceneWorld[Survivor]` alias.
- **A shared cached-media base for `Illustrator` and `Reader`.** They share a shape (optional
  feature, `.open()` returning `Self | None`, `Claims`, sha1-keyed disk cache, errors swallowed to
  a warning) but the bodies differ enough that a base class would be three abstract hooks over ~20
  saved lines. Net worse.
- **`SKILL_SPREAD` should be a tuple** like every other constant in `breathless/world.py`. The list
  is load-bearing: `check_spread` (`:205`) compares it against `sorted(...)`, which returns a list,
  and a list never equals a tuple.
- **Dead code.** There is none. I walked every function in `src` for callers across `src`, `tests`
  and `qa`; every single-use helper is a legitimate private helper, a pydantic validator or a UI
  callback.
- **`basedpyright` reports 1101 errors.** Only when the `qa` dependency group is absent.
  `uv sync --all-groups` — what CI runs — gives `0 errors`.
