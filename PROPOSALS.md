# Simplification proposals

Source: four independent full-codebase audits (three Opus subagents + one direct). Every number
below was verified by re-running the measurement, not taken from an agent's word.

**Scale:** `src/` 10,248 lines · `tests/` 12,226 · `qa/` 2,104.

**Verdict up front:** this codebase is well-built, not bloated. `CLAUDE.md` is largely obeyed and
mostly earns its keep. The waste is a dozen places where a good rule was applied past the point
where it paid. Realistic total: **~350 source lines and ~300 test lines**, plus `qa/` (0 or 2,104,
your call in P4).

Each proposal is either **RECOMMEND** (do it) or **DECIDE** (pick an option).

---

## P1 — Bind master tools straight to world methods

**RECOMMEND.** Largest single cut available.

### What exists

Every master tool is spelled in 4–5 places: a description constant, an args model, a registration
line in a `master_tools()` override, an engine handler method, and usually the world method that
does the real work.

Verified: **13 of 33 handler methods are pure one-line forwarders** — the entire body is
`return self.world_of(draft).<name>(args.<field>)`.

```
seam.py           reveal, kill, join_party, leave_party
scenes/engine.py  enter, leave
rooms/engine.py   move_item, unlock_way, move, meanwhile
twentyfourxx      take_lead, ship_upgrade
breathless        use_med_kit
```

A further ~8 are two-liners that call `world.check_unnamed(...)` and then forward.

### What it becomes

One helper beside `master_tool`, in `engines/seam.py` (it needs `world_of`):

```python
def world_tool[G, W, A](
    name: str, description: str, args: type[A],
    resolve: Callable[[W, A, Random], Sequence[Fact]],
) -> MasterTool[G]
```

wrapping `lambda draft, a, rng: resolve(self.world_of(draft), a, rng)`. Registration becomes:

```python
world_tool("move", MOVE, Move, lambda w, a, _: w.move(a.to_id, a.with_ids)),
```

The 13 forwarder methods disappear.

### Why it is over-engineered

A layer that only forwards. The `CLAUDE.md` rule that created it — *"an engine tool method resolves
ids and rolls dice"* — does real work for `roll`, `job`, `defend`, which genuinely resolve ids and
roll. For 13 of 33 tools there is nothing to resolve.

### Feature impact

**None.** Tool names, descriptions, JSON schemas and refusal texts are unchanged. MCP and the
builtin completion loop both read `engine.tools` unchanged.

### Size and risk

~120–150 lines, 0 files. 3–5 hours. Risk **medium-low** — `tests/app/test_master_tools.py` (535
lines) and `tests/twentyfourxx/test_tools.py` (958) drive tools through `Turn.call`, so they should
be untouched.

**Do not** attempt the decorator variant (`@tool(DESC, Args)` on the handler, deriving the name from
`__name__`, deleting all 7 `master_tools()` overrides) as the first step. It is a bigger win
(~200 lines) but decorated generic methods under `basedpyright` strict with `Engine[P, M, G]` is
where this turns into a type-checker fight. Try it on `seam.py` alone afterwards; abandon the moment
a `# pyright: ignore` appears.

---

## P2 — Extract the duplicated hidden-name leak scan

**RECOMMEND.** Smallest high-value item. This one is safety logic.

### What exists

The rule *"no text the player reads may name something hidden"* — the `CLAUDE.md` invariant *"hidden
facts have no path into the narrator"* — is implemented **twice**, with a byte-identical inner loop:

`engines/scenes/worldsmith.py:73-81`
```python
read = "\n".join((draft.title, draft.focus, draft.situation))
leaked = set(named_unmet(read, (everyone[eid] for eid in hidden)))
for entity_id in (*present, *followers, *hidden):
    entity = everyone[entity_id]
    text = "\n".join((entity.brief, *(value for _, value in entity.rows())))
    watchers = (everyone[other] for other in hidden if other != entity_id)
    leaked.update(named_unmet(text, watchers))
```

`engines/rooms/worldsmith.py:64-71`
```python
read = "\n".join((place.name, place.brief, place.description))
leaked.update(named_unmet(read, hidden))
for thing in things:
    text = "\n".join((thing.brief, *(value for _, value in thing.rows())))
    watchers = (other for other in hidden if other.id != thing.id)
    leaked.update(named_unmet(text, watchers))
```

Identical modulo id-vs-object indirection. Both exclude the entity from its own watcher set.

### What it becomes

One free function in `engines/base.py`, beside the existing `named_unmet`:

```python
def leaked_names(things: Iterable[Thing], hidden: Sequence[Thing]) -> set[str]
```

Both families call it. The surrounding checks (`scene_unmet`, `_map_unmet`) stay where they are —
they verify genuinely different invariants.

### Why it is over-engineered

It is not over-abstracted; it is **under**-abstracted, which costs the same. Two things need it, so
`CLAUDE.md`'s "two things" bar is met. Duplicated *safety* logic is the worst kind to let drift: a
fix to one side is a silent spoiler leak on the other.

### Feature impact

**None** if extracted faithfully.

### Size and risk

~30 lines removed, ~15 added. 2–3 hours. Risk **medium** — not mechanically, but this is the highest
silent-regression risk on the list. Get `tests/engines/test_integrity_boundaries.py` (184 lines) and
`tests/engines/test_scene_bar.py` (669) green before and after. If the two turn out to differ in any
way you cannot reconcile, **do not merge** — document the difference instead.

---

## P3 — The `rooms` family: 870 lines, one production implementer

**DECIDE.** Two agents independently flagged this and both said to ask you first.

### What exists

`engines/rooms/` is **870 lines** (`world.py` 493, `engine.py` 238, `worldsmith.py` 74, `tools.py` 65)
serving exactly one production engine, `TunnelGoonsEngine` (449 lines). Every class is generic for
that single instantiation:

```
Dungeon[N: Dweller]              MapDraft[N]        RegionDraft[N]
RoomWorld[P: Person, N: Dweller] RoomEngine[P, N, G]
```

The only production binding is `(Goon, Npc, TunnelGoonsGame)`. By contrast `scenes/` has three
implementers and earns its generics.

`Engine[P, M, G]`'s player-vs-member split also exists for TunnelGoons alone — the three scene
engines all bind `Engine[C, C, G]`.

### Two facts that cut against deleting it

1. `tests/support/sixth.py` (105 lines) is a **second** `RoomEngine` implementer. It is test-only
   and exists to test the family, which is circular justification — but "one implementer" is
   technically false.
2. **`IDEAS.md#18` plans a Maze Rats engine "self-contained on the same seam."** If that lands as a
   second room crawler, a merge is wasted work that must be reverted.

### Options

- **(a) De-genericise, keep the module split.** `Dungeon`, `MapDraft`, `RegionDraft`, `RoomWorld`,
  `RoomEngine` stop being generic over `Dweller`/`Person`; `tunnelgoons/world.py` subclasses
  concretely. Removes ~5 generic declarations, ~40 type-parameter mentions, and the 2-line narrowing
  override. **~60–80 lines, 4–6 hours, low risk.** Survives Maze Rats landing.
- **(b) Merge `rooms/*` into `tunnelgoons/*`.** 4 files deleted, ~870 lines absorbed, `Dweller`/`Npc`
  collapse. **~100 net lines, 1–2 days.** Must be reverted if Maze Rats happens.
- **(c) Leave it.** Correct if Maze Rats is imminent.

**Recommendation: (a) now, revisit (b) only if you cancel idea 18.** The question that decides this
is yours: *is Maze Rats still on?*

---

## P4 — `qa/`: 2,104 lines, 20% of the repo's Python

**DECIDE.** Nobody but you can answer this one.

### What exists

`qa/` is a parallel harness that no test runs:

- `qa/agents.py` (273 lines) is a **second** `ScriptedSpawner`, duplicating
  `tests/support/table.py:111-144`, with its own `!roll`/`!crash`/`!refuse`/`!fail`/`!bad`/`!slow`
  script language, its own per-engine default-roll table, and its own fault injection.
- `qa/server.py` (99) boots the real app with those agents.
- `qa/drive.py` (187) is a Playwright driver pinned to
  `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` — unrunnable on a machine without that path.
- Eleven `s_*.py` scenario scripts: 1,395 lines.

It is in `basedpyright.include` and in the default `uv` groups, so it gates `uv run basedpyright`.

**Live drift already exists:** `tests/support/table.py`'s stub does `del tools`; `qa/agents.py`
honours the parameter. Two stubs of one Protocol that already disagree about the surface they stub.

### Options

- **(a) Keep, deduplicate.** Make `qa/agents.py` a subclass/config of `tests/support/table.py`'s
  `ScriptedSpawner` rather than a rewrite. **~120 lines, removes the drift risk.**
  `pythonpath = ["tests"]` already permits the import.
- **(b) Keep as-is, drop from `basedpyright.include`.** One line; stops 2,104 lines of screenshot
  scripts gating the type check.
- **(c) Delete `qa/` entirely** (−2,104 lines, −`playwright`), porting the parts that earn their keep
  — the double-send/reload-storm cases in `s_burst.py` and the eight-turn soak in `s_endure.py` —
  into async tests under `tests/ui/`. Biggest single line reduction in the repo, and the one most
  likely to throw away something you use.

**Regardless of which you pick: align the two stubs' signatures (~20 min).** They cannot be allowed
to keep disagreeing.

---

## P5 — `Subject` and `DecisionOption` are one idea under two names

**RECOMMEND.**

### What exists

Four near-identical `id`/`label`/`detail` value models in two parallel hierarchies:

```
core/play.py:65   DecisionOption(Frozen)   id: Slug; label: str = Field(min_length=1); detail: str = ""
core/play.py:71     PendingOption(...)     + name, args
core/views.py:27  Subject(Frozen)          id: Slug; label: str; detail: str
core/views.py:44    Companion(Subject)     + sheet, chattiness
```

Plus `DecisionOption` subclassed four more times in `twentyfourxx/worldsmith.py` (`SkillChoice`,
`Specialty`, `Body`, `Origin`), and `app/launch.py:16 CatalogEntry` which is the same three fields
plus three more.

`core/views.py` already imports from `core/play.py`, so there is no import-direction obstacle.

### Second, related defect

`engines/base.py:56-67` formats strings by **constructing a validated Pydantic model**:

```python
@property
def tag(self) -> str:      return self.subject().tag
@property
def headline(self) -> str: return self.subject().headline
def subject(self) -> Subject:
    return Subject(id=self.id, label=self.name, detail=self.brief)
```

`Subject` is `Frozen` (`extra="forbid", frozen=True, strict=True`), so every `entity.tag` runs a full
strict construction to produce `f"{label}[{id}]"`. `Person.headline` calls `super().headline`, doing
it twice. This runs in loops — `cast_lines`, `scene_lines`, `map_so_far` (O(places × ways)).

Measured: **13× slower than the f-string** — but ~1μs absolute, so treat this as a **clarity** fix,
not a performance one. I am not going to sell you a microsecond.

### What it becomes

One model in `core/play.py` carrying `id`/`label`/`detail` + the `tag`/`headline`/`row()`
projections. `Subject`, `Companion`, `PendingOption` all extend it. Separately, make
`Thing.tag`/`headline`/`mention` plain f-strings that share a free function with `Subject`'s, so the
two cannot drift.

Keep `Thing.subject()` for the places that genuinely hand a `Subject` across the seam
(`Engine.companions`, `narrator_view`, `PlayerView.player`).

### Feature impact

**None.** Serialised shape and rendered output are byte-identical.

### Size and risk

~30 lines, ~15 import sites. 2–3 hours. Risk **low**. One judgement call: `Subject.label` has no
`min_length`, `DecisionOption.label` does. Unifying tightens validation on `Subject` — which is built
from `Thing.name`, already `Field(min_length=1)`, so nothing can break.

**Keep the `name/brief` ↔ `label/detail` dual vocabulary itself.** It is the one thing stopping disk
field names leaking into prompts, and `tests/app/test_context_boundary.py:46-58` pins it. Only the
per-call adapter is wrong.

---

## P6 — Twelve single-field tool-arg models

**DECIDE.** The mechanical risk is nil; the prompt-quality risk is real.

### What exists

Twelve Pydantic models whose entire body is one field differing only in its `description`:

```
base.py:298-316            Reveal, Kill, JoinParty, LeaveParty   (2 lines each)
scenes/tools.py:17-22      Enter, Leave
rooms/tools.py:29          UnlockWay
loner3e/tools.py:56        RestoreLuck
twentyfourxx/tools.py      TakeLead, ShipUpgrade
breathless/tools.py:44,102 UseMedKit, Actor
```

**Verified: `UseMedKit` and `Actor` are byte-identical** —
`actor_id: Slug | None = Field(default=None, description=ACTOR)` — declared 58 lines apart in the
same file, both in use.

Verified: `schema_of` already pops `title`, so **the published JSON schema is identical either way**
(`tests/core/fixtures/schemas/*/master_tools.json` contains zero `"title"` keys).

### Options

- **(a) Full collapse.** Two models in `core/tools.py` beside `NoArgs`: `EntityArg` and `ActorArg`.
  Per-tool wording moves into the tool's `description`, which already carries it
  (`REVEAL = "A hidden entity here becomes known to the player."`). **~55 lines.** Changes the
  `entity_id` description in 8 tool schemas — you hand a live LLM one fewer hint. Whether that
  measurably degrades behaviour is **unknown**, and I will not pretend otherwise.
- **(b) Half collapse.** Delete only the exact duplicate (`Actor` ≡ `UseMedKit`) and the four in
  `base.py`. **~20 lines, zero schema change, zero prompt risk.**
- **(c) `create_model` factory** keyed on description. Keeps every word, deletes every class — but
  the resolver's `args` parameter loses its static type, colliding with the `Do not use Any` rule.
  **Not recommended.**

**Recommendation: (b).** Take the free 20 lines; leave (a) as a deliberate prompt experiment for a
day when you can measure it, not a refactor.

---

## P7 — Delete the MCP forwarding chain

**RECOMMEND.** Found independently by two agents.

### What exists

A four-deep chain for one call:

```
app/mcp.py:80,82        runtime.published_tools() / runtime.call(name, args)
app/runtime.py:348-357  -> turn.published_tools() / turn.call(...)   [10 lines, both pure forwards]
turn/run.py:131-132     -> tuple(self.engine.tools.values())         [2 lines, pure forward]
turn/run.py:107         -> engine.tools[name].call(draft, raw, rng)
```

`Runtime.turn` (`runtime.py:344-346`) is itself a property forwarding to `self.admitted.turn`.
`app/spawn.py:151-153` declares a `Tools` Protocol for exactly these two methods.

The builtin completion loop already receives the `Turn` **directly** (`app/roles.py:60` passes
`turn` as the `tools` argument). So `Runtime.published_tools`/`Runtime.call` exist *only* for the MCP
path, duplicating what builtin does without them.

### What it becomes

`mcp.py` holds the `Runtime`, reads `runtime.turn` itself, raises `Refusal(NO_TURN)` when it is
`None` — the same two lines that live in `Runtime.call` today. `Runtime.published_tools`,
`Runtime.call` and `Turn.published_tools` all go.

### Feature impact

**None.**

### Size and risk

~25 lines across 3 files. 1–2 hours. Risk **low-medium** — `tests/support/table.py:165-173` and
`tests/app/test_master_tools.py` drive tools through `runtime.call`.

Smaller safe variant: delete `Turn.published_tools` and `Runtime.published_tools` only, keep
`Runtime.call` as the test-facing seam. **~10 lines, no test churn.**

Keep the `Tools` Protocol either way — `builtin.py` needs it and `qa/agents.py` stubs it.

---

## P8 — Merge the two save-validation paths

**RECOMMEND.** A DRY defect with a performance tail.

### What exists

Two functions doing the same job with different return types:

- `app/launch.py:119-148` `_save_option` (30 lines): read raw → `routed` → `engine.restore(raw)` →
  check character title → check `played_by` → build `LaunchTarget` → compare slug →
  `state.scenario.drift(...)` → `SaveOption`.
- `app/runtime.py:403-425` `Runtime._resumed` (23 lines): `store.read` → `engine.restore(saved)` →
  compare `(scenario_id, character_id)` → `state.scenario.drift(...)` → state.

`LauncherCatalog.read` calls `_save_option` for **every** save on **every** home-page render, and
`engine.restore` is a full strict Pydantic validation of the entire game. The moment the player
clicks Resume, `_resumed` validates the identical file **again**.

### What it becomes

One `resumed(engine, raw, target) -> AnyGame` raising `Refusal` with the reason. `_save_option`
becomes a projection of the returned state into `SaveOption`; `_resumed` becomes the same call.

### Why it matters beyond lines

The launcher's `unresumable` list is derived from one implementation while the game page uses the
other. They can disagree about whether a save is playable — which is exactly the bug a player would
report as "it's listed but won't open."

### Feature impact

**None** if the refusal messages are preserved. Home page gets faster in proportion to save count.

### Size and risk

~30 lines net. 2 hours. Risk **low**. Preserve `_save_option`'s `None` return for "vanished between
`slugs()` and `read`" (`launch.py:127-130`) — that is a real race guard, not noise.

---

## P9 — Batch of small cuts (one commit)

**RECOMMEND** all but the first. ~90 lines, ~6 concepts, half a day, near-zero risk each.

### 9a. `for_name` → `getattr` — **DECIDE**

`config.py:89-96` and `:109-114` are two `match` statements (8 and 6 lines) whose whole job is
`getattr(self, name)`, where `name` is a `Literal` already matching the field names. All four audits
found this.

**But:** the `match` gives a compile-time exhaustiveness check. Add a fourth `Role` and
`basedpyright` flags the missing case today; `getattr` fails at runtime instead.

- **(a)** `getattr` — 2 lines each, ~14 saved, loses the check.
- **(b)** Keep `for_name`, but delete the `get_args(Role.__value__)` reflection dance in
  `_keys_present` (`config.py:151-152`) and iterate `RoleSettings.model_fields` instead. ~6 lines,
  keeps the check.
- **(c)** Decline. Legitimate given your strict-typing stance.

**Recommendation: (b).** You bought the exhaustiveness check deliberately; don't sell it for 14 lines.

### 9b. Collapse the render trio — **RECOMMEND**

`engines/seam.py:197-228`: `render_request` (6 lines) and `render_opening` (4 lines) are both thin
wrappers over a 6-positional-parameter `_render`, differing in exactly **one** argument. Verified
5 callers use the former, 2 the latter.

Becomes one method taking `source`, `scope`, `family: Sections` explicitly. The `opening_sections`
class attribute — a hand-written stand-in for what `family_sections` returns against an empty world —
can stay as a value passed at the call site.

~12 lines. The golden prompt fixtures will confirm byte-identical output; that is what they are for.

### 9c. Null-object the media/speech `| None` — **RECOMMEND**

`Illustrator.open` and `Reader.open` both return `Self | None` when the feature is disabled. That
`| None` then leaks into `GameService` as **six** guard clauses (`runtime.py:106-107`, `:275-278`,
`:280-283`, `:285-289`, `:291-296`, `:298-301`), each opening `if self.x is None: return None`.

The `| None` is not a domain fact, it is a setting. Null implementations whose methods do nothing
remove all six guards. ~20 lines, near-zero risk.

(Do **not** also try to extract the shared `claim → check disk → generate → publish → log` skeleton
in the same pass — the icon/reference-image path and the multi-voice WAV assembly differ more than
they look.)

### 9d. Dissolve `Roles` into three free functions — **RECOMMEND**

`app/roles.py:53-108`: `Roles` is a frozen dataclass with **one** field (`spawner`) and three async
methods. It owns no state — and `runtime.py:232` proves it, reaching back through the wrapper
(`worldsmith(self.roles.spawner)`) to get the field out again.

`CLAUDE.md`: *"a class owns its state and the methods that read or change it."* Becomes
`master(spawner, turn)`, `narrate(spawner, ...)`, `interject(spawner, ...)` as module functions
beside the `render_*` functions already free in that file. ~14 lines.

### 9e. Micro-dataclasses — **RECOMMEND**

`Struck(facts, loser)` (`loner3e/world.py:131`), `Helping(who, terms)` (`twentyfourxx/engine.py:89`),
`GeneratedImage(data, suffix)` (`media.py:29`) each name a two-element return with one producer and
one consumer that never crosses a module. Plain tuples.

More important: `breathless/engine.py:56` and `twentyfourxx/engine.py:81` define **two different
classes both named `Pool`** in sibling modules. Keep both (genuinely different), rename to
`SkillPool` / `DicePool`. ~20 lines.

### 9f. Move `ui/dictation.py` into `ui/widgets.py` — **RECOMMEND**

A 9-line module holding one 4-line `ui.element` subclass, imported only by `ui/game.py`, which
already imports from `widgets`. One file deleted, 20 minutes.

### 9g. Rename `check_json_keys` — **RECOMMEND (naming only)**

`core/io.py:177-179` is a three-line function whose body is `decode(raw)` with the result discarded.
It reads like a deletable no-op, and one audit proposed deleting it.

**I tested this. Do not delete it.** `parse_json` silently accepts duplicate keys:

```
>>> parse_json(M, '{"a": 1, "a": 2}')   ->   a=2
```

The separate `decode()` pass with the `_unique_keys` hook is the **only** thing rejecting a doubled
id. Removing it is a silent correctness regression. Rename it to `reject_duplicate_keys` so nobody
makes that mistake later.

---

## P10 — Prune the test suite

**DECIDE.** Tests are 119% of source. Some of that is triple payment for one guarantee.

### What exists

**Wiring tests `CLAUDE.md` forbids** (*"test behavior and boundaries, not prose or wiring"*):
`tests/engines/test_seam.py:63-76` asserts `instructions.startswith("Roll high.")` — i.e. that string
concatenation happened. `:87-98` asserts a literal list of 7 tool names already pinned by
`tests/core/fixtures/schemas/*/master_tools.json`. `test_rooms.py:35,47` are the same two shapes.
`test_seam.py:100-124` defines a third engine subclass just to count calls to a method.

**Synthetic engines:** `tests/support/fifth.py` (106) and `sixth.py` (105) are two complete fake
engines existing so tests can assert the framework works. `sixth.py` earns its place — `test_rooms.py`
needs maps the shipped scenario cannot produce (`can_move_offscreen`, `_offscreen_place`).
`fifth.py`'s job could be done by `Loner3eEngine`, which the rest of the suite already uses.

**Prompt substrings the goldens already pin:** `tests/app/test_context_boundary.py` asserts
`"luck: 6/6" in master`, `"Kael[player]" in master`, etc. — while
`tests/core/fixtures/prompts/{engine}/master.txt` pins the exact rendered prompt byte-for-byte. A
golden is a drift detector; asserting a substring on top of it is paying rent twice and tells you
less than the diff.

**Triple-covered rules in `test_scene_bar.py` (669 lines):** "the scene must not list the player"
tested at `:157`, `:256` and `:544`. Word-boundary matching in `named_unmet` tested four times
(`:301`, `:315`, `:329`, `:343`) when `named_unmet` is *already* unit-tested directly at
`tests/engines/test_engines_base.py:112,123` with exactly those four properties.

### Options

- **(a) Wiring tests only.** Delete the 4 wiring tests + the counting subclass. **~60 lines**, zero
  judgement required.
- **(b) (a) + `fifth.py`** and rehome the scene-family tests onto `Loner3eEngine`. **~180 lines.**
- **(c) (b) + prune the duplicates**: collapse the four scene-level `named_unmet` tests into one
  wiring-proof, merge the three player-listing tests, delete the positive prompt-substring
  assertions. **~350–400 lines.**

**Keep regardless**, in all options: `test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon`
(`test_context_boundary.py:41-59`, asserts the exact field set of `NarratorView` — the security
invariant) and the two negative assertions that a secret appears in the master prompt and **not** in
the narrator prompt. Those are boundary tests, not prose tests.

**Recommendation: (a) now, (c) only after P2 lands** — P2 changes the leak-scan code those tests
cover, and you want them at full strength while you do it.

---

# Examined and deliberately rejected

Listed so nobody deletes them later on a vague hunch.

| Thing | Why it stays |
|---|---|
| **The three-AI-role split** | There are only *two* code paths, not three. The narrator and worldsmith already share one function (`ask`); the master has no typed answer and no retry. The sharing already happened. |
| **The `engines/registry.py` seam** | 14 lines, and the *only* module allowed to name a concrete engine — enforced by `tests/core/test_package_boundary.py:76-97`, which also forbids any UI module from containing an engine-id string. A seam with teeth. |
| **The scenes/rooms family split** | A list of scene runs and a graph of places are genuinely different topologies. `rooms/world.py` is 493 lines with no analogue in `scenes/world.py`. Merging them is an architecture rewrite, not a simplification. |
| **The mutable-state / frozen-value split** | Load-bearing, not bookkeeping. `Game.draft()` deep-copies, `commit()` re-validates, and `Turn.apply` rolls back both draft and RNG on refusal. That transaction is sound *only* because value models cannot be mutated behind it. |
| **`Refusal` vs bug** | Caught in exactly the six places that hand a message to a model or player; everything else propagates. Clean, cheap, correct. |
| **`Frozen`/`Mutable`/`Loose`/`Echoed`** | 10 lines total. Each has a distinct `extra=`/`frozen=` combination with real users. `Echoed`'s `extra="allow"` is load-bearing for round-tripping assistant messages. |
| **`Generation`/`Request`/`advance`** | Looks like an over-built dispatch table. It is not: `Generation` is a Pydantic field on a mutable draft, so it *cannot* hold a callback. The id-keyed registry is the only way back to one. |
| **`schema_of` / `_inline_refs`** | Reimplements `$ref` inlining, which neither stdlib nor Pydantic offers, and the inlining is what stops Python class names leaking into prompts. |
| **`MountedLifespan`** | Looks like a hand-rolled `AsyncExitStack`. It is not: `manager.run()` is an anyio task group, and anyio cancel scopes must be entered and exited in the same task. The docstring is correct. |
| **The reflective settings form** | Two audits disagreed; I counted. `Settings` has **38 leaf fields** (34 rendered). Hand-writing 34 widgets is ~100–140 lines against ~130 lines of reflection. It is **not** a lines win — it only becomes one if you also drop ~20 settings from the UI, which is a feature cut, not a simplification. |
| **`turn/` as a one-module package** | Buys the enforced import boundary `CLAUDE.md` names explicitly. Merging into `app/` costs the boundary to save a directory. |

---

# One open question flagged, not proposed

`NOISE_KEYS` (`core/tools.py:14`) strips `pattern` and `maxLength` from every published schema, which
means **the model is never shown the `Slug` grammar it is required to obey**. That may be deliberate
(token cost — the comment says *"drop what the model reads for free from parsing"*) or it may be
costing you malformed ids and wasted re-prompts.

That is a prompt-quality experiment to measure, not a refactor to perform. Flagged so it is a
decision rather than an accident.

---

# Suggested order

| Order | Proposal | Lines | Hours | Risk |
|---|---|---|---|---|
| 1 | P9 batch (b, 9b–9g) | ~90 | 4 | very low |
| 2 | P7 MCP chain | ~25 | 1.5 | low |
| 3 | P8 save paths | ~30 | 2 | low |
| 4 | P5 Subject/DecisionOption | ~30 | 2.5 | low |
| 5 | P6 (b) arg models | ~20 | 1 | none |
| 6 | P2 leak scan | ~15 net | 2.5 | medium |
| 7 | P1 world_tool | ~150 | 4 | medium-low |
| 8 | P3 / P4 / P10 | your call | — | — |

Items 1–5 are **~195 lines and 5 hours with no decision required.**
