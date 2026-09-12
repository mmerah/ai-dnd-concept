# PROPOSALS — code quality and pattern consistency in `src`

Scope: `src/aidm` only. No feature work.

**Baseline.** `uv run pytest` (655 passed), `ruff check`, `ruff format --check` and
`basedpyright` (0 errors with `uv sync --all-groups`) are all green today, and
`tests/core/test_package_boundary.py` proves the `core <- engines <- turn <- app <- ui` flow holds
with no cycles and no settings leaking below `app`. Nothing below is a lint fix. These are the
design and consistency findings that survive after the linters are already clean — what a senior
Python reader judges next.

**Method.** One reviewer per layer (core/seam, the six engines, app/turn/ui), plus a full read.
Every factual claim was re-verified against the running code before it was written down.

**Status key.**

| | |
|---|---|
| **AUTO** | No feature impact and the code gets smaller or simpler. Accepted unless you object. |
| **CALL** | Needs your decision — options are listed. |
| **BEHAVIOUR** | Something a player or a role would notice. Never auto-accepted. |

---

## 1. Split `ui/game.py` — 692 lines, one class, 31 methods, 27 attributes — **CALL**

**Now.** `GamePage` (`ui/game.py:86`) does everything: page layout, seven
`@ui.refreshable_method` panels, two polling timers, ten browser event handlers, the composer
(text box, send, dictation, enable/disable), the restart dialog, the dice tray, and the async play
calls. Largest file in the repo by 150 lines. 12 free functions trail below it.

**Change to.** Three modules, each owning its own widgets:

- **`ui/transcript.py`** — `chat` (`:258`), `live_turn` (`:298`), `journal` (`:369`), and the
  renderers `_card` (`:637`), `_dice_group` (`:649`), `_bubble` (`:667`), `_inline_status`
  (`:680`), `_clock` (`:690`), with the constants `STEP_COPY` (`:33`) and `MARK_LABELS` (`:60`).
  These become free functions taking `(session, view, history)`; `GamePage` keeps one-line
  `@ui.refreshable_method` wrappers.
- **`ui/composer.py`** — a `Composer` class owning `box`, `send`, `action_button`, `over_label`
  and `Dictation`; methods `submit` (`:470`), `act` (`:479`), `dictated` (`:527`),
  `dictation_failed` (`:533`), `_set_composer` (`:538`), `_clear_box` (`:445`),
  `_clear_spent_draft` (`:439`), plus the free `can_type`, `placeholder`, `draft_spent`,
  `insert_at_caret` and the `DICTATION_FAILURES` map.
- **`ui/game.py` keeps** the shell (`build`, `foot`, `nav_rail`, drawer, restart dialog), the
  polling loop (`poll_turn`, `poll_media`, `_landed`, `_scroll`, `scrolled`, `catch_up`) and the
  runtime calls (`play`, `_run`, `restart`).

`game.py` lands at roughly 300 lines; `GamePage` at ~18 methods.

**Code impact.** ~700 lines moved, no logic edited. `tests/ui/test_game.py:14-23` imports
`can_type`, `draft_spent`, `insert_at_caret`, `near_end`, `placeholder`, `standing_proposal` from
`aidm.ui.game` — repoint those 6 names. The Playwright suite in `qa/` must still pass.
**60-90 min.**

**Feature impact.** None.

**Decision 1 — how far to split.**
- **A (recommended).** Three modules. Best cohesion; `Composer` becomes independently testable.
- **B.** Two modules — extract `transcript.py` only, leave the composer on `GamePage`. Half the
  work, leaves ~10 of the 14 unset attributes in proposal 2.
- **C.** Extract only the free render helpers (~15 min). Does not fix the thing a reviewer points
  at: `GamePage` stays a 27-attribute object.
- **D.** Leave it.

---

## 2. Constructors that leave the object half-built — **CALL**

**Now.** Four classes declare attributes as bare annotations with no value, so the object is
unusable until a *second* method runs, and the type checker believes the attributes are always
there:

| Class | Where | Unset attributes | Made valid by |
|---|---|---|---|
| `GamePage` | `ui/game.py:89-117` | 14 | `build()` |
| `ScenarioForm` | `ui/create.py:157-170` | 7 | `build()` → `form()` |
| `CharacterForm` | `ui/create.py:24-31` | 2 | `build()` |
| `Runtime` | `app/runtime.py:341-352` | 4 (`field(init=False)`, no default) | `Runtime.start()` |

`Runtime(settings)` is legal Python and returns an object where `engines`, `spawner`, `library`
and `store` each raise `AttributeError`. `GamePage(runtime, session).refresh()` raises. This is the
one pattern in `src` that reads as unfinished.

**Change to.**
- `Runtime`: move the two lines from `start` into `__post_init__`, so the only constructor there
  is is the correct one. Keep `start` as a one-line alias if you like the named entry point.
  Call site: `ui/app.py:107`.
- `GamePage`: once proposal 1 lands, `Composer.__init__` and `Transcript.__init__` build their own
  widgets, and `GamePage` keeps only what it builds itself (drawer, tabs, rail, dice).
- `CharacterForm` / `ScenarioForm`: `form()` is `@ui.refreshable_method` and rebuilds its widgets
  on every engine change, so the fix is to have `form()` *return* its widget set and assign it,
  rather than pre-declare the names.

**Code impact.** ~70 lines across `ui/game.py`, `ui/create.py`, `app/runtime.py`, `ui/app.py`.
`tests/support/table.py` and `tests/app/` build a `Runtime`. **40 min**, plus whatever proposal 1
costs.

**Feature impact.** None.

**Decision 2 — scope.**
- **A (recommended).** All four.
- **B.** `Runtime` + `GamePage` only (18 of the 27). The two forms are fiddlier because of the
  refreshable rebuild.
- **C.** `Runtime` only (10 minutes, and it is the one that is a public entry point).

---

## 3. `GameService` does six jobs; give two of them away — **CALL**

**Now.** `app/runtime.py:45-338`, ~295 lines, 17 fields, 30 members. It holds session lifecycle,
turn orchestration, worldsmith growth, party interjections, an asyncio task nursery, **and** media
fan-out. The `Illustrator | None` / `Reader | None` pair is threaded through `resume()`'s keyword
list (`:68-99`), `Runtime._open` (`:465`) and nine methods purely to answer "is media on?".

**Change to.** Two extractions, both mechanical:

- **`app/present.py`** — a `Presenter` holding `media`, `reader` and the engine; owns `presents`
  (`:110`), `scene_art` (`:280`), `icon` (`:285`), `newest_clip` (`:288`), `illustrate` (`:292`),
  `speak` (`:299`), `_present` (`:269`). `Runtime._open` builds it once instead of passing two
  optionals through.
- **`app/background.py`** — a `Tasks` nursery owning `_background` (`:65`), `_retain` (`:308`),
  `_settled` (`:313`), `settled` (`:320`) and the cancelling half of `close` (`:323`). Generic
  plumbing with no relation to playing a turn.

`GameService` lands at ~17 members and reads as one job: run the turn and keep the save honest.

**Code impact.** 2 new files (~60 and ~55 lines), `runtime.py` down to ~380.
`tests/app/test_game_service.py:536-542` pokes `game._retain` / `game._background` and
`tests/support/table.py:263` calls `service.settled()` — both repoint. `ui/game.py` calls
`session.scene_art()`, `session.icon()`, `session.newest_clip()`, `session.presents`. **60 min.**

**Feature impact.** None.

**Decision 3 — how far.**
- **A (recommended).** Both, and keep four one-line delegating methods on `GameService` so `ui/`
  is untouched.
- **B.** Both, and update the six `ui/` call sites to go through `session.present`. Cleaner, wider
  diff.
- **C.** `Presenter` only — the nursery is 15 lines and reads fine where it is.
- **D.** Neither.

---

## 4. A non-player's card is prefixed five different ways, and 24XX never prefixes at all — **BEHAVIOUR**

**Now.** `base.py:86` exists for exactly this:

```python
def card_line(self, line: str) -> str:
    return line if self.id == PLAYER_ID else f"{self.name}: {line}"
```

It is used in `base.py:94` and four times in `loner3e/world.py`. Everywhere else the same decision
is re-made by hand, or not made at all:

- **Hand-rolled** — `breathless/world.py:150-154` (a three-line conditional producing exactly
  `card_line`'s output) and `tunnelgoons/world.py:56-58`.
- **Inline, three names for one expression** — `breathless/engine.py:234` and
  `twentyfourxx/engine.py:413` call it `prefix`; `tunnelgoons/engine.py:184` calls it `who`.
- **Missing entirely** — every `Crewmate` card in `twentyfourxx/world.py` is unprefixed:
  hindrances (`:121`), `gain_item` (`:130`), `repair_item` (`:138`), `spend` (`:143`), `maim`
  (`:150`), `raise_skill` (`:162`), `earn` (`:170`). So when a hired crew member picks something
  up, the player's card feed says **"Gained Rope"** with no name on it.
- **Split inside one engine** — breathless prefixes `change_stress` (through `base.change`) but
  not `use_med_kit` (`world.py:129`).

**Change to.** One rule: every card that can belong to someone other than the player goes through
`self.card_line(...)`. The three mid-line roll prefixes cannot (the name sits inside the sentence)
— there, settle on the name `prefix` in all three.

**Code impact.** ~20 lines across 5 engine files. Tests assert the old strings at
`tests/breathless/test_world.py:156`, `tests/breathless/test_tools.py:105`,
`tests/tunnelgoons/test_world.py:98`. **35 min.**

**Feature impact.** Card text changes for hired members: `"Caught breath — …"` becomes
`"Mira: Caught breath — …"`, and 24XX crew cards gain a name they never had. This is the fix to a
real readability bug, not a cosmetic change — but it is visible, so it is your call.

---

## 5. `require_member_here` means two different things in the two engine families — **BEHAVIOUR**

**Now.** `base.py:224` declares the contract: *"Alive and here with the player."* The two families
honour it differently.

`rooms/world.py:161` looks only in `npcs`, so the player's own id is refused cleanly.
`scenes/world.py:127` is a bare alias with no body of its own:

```python
def require_member_here(self, entity_id: Slug) -> C:
    return self.require_living_here(entity_id)
```

and `require_living_here` → `require_here` (`:105`) returns the player for their own id. Verified
consequence: in every scene engine, `join_party` on `"player"` **does not refuse**. It appends the
player to `party`, writes the fact `"Kael[player] travels with the player"`, and only blows up at
commit with `the state this leaves is invalid: payload: Value error, the player cannot travel with
themselves`. In tunnel goons the same call refuses at once with `unknown id 'player'`.

`SceneWorld` also has four resolvers for three jobs: `require` (`:97`), `require_here` (`:105`),
`require_living_here` (`:116`), `require_member_here` (`:127`).

**Change to.** Delete the alias, rename `require_living_here` → `require_member_here` (the name the
base declares), and give it the guard rooms already has:

```python
def require_member_here(self, entity_id: Slug) -> C:
    if entity_id == self.player.id:
        raise Refusal("the player is not a party member")
    ...
```

**Code impact.** ~15 lines. Call sites `loner3e/engine.py:195,199,203,211,215`; tests at
`tests/engines/test_scenes.py:69-75`, `tests/twentyfourxx/test_world.py:109`. **25 min.**

**Feature impact.** `join_party` and `hire` on the player's own id now refuse with a readable
message instead of failing at commit. Strictly better, but the game master sees different text.

---

## 6. Publish a drawn icon **inside** its claim — **AUTO**

**Now.** `app/media.py:109-116`:

```python
with self.claims.hold(f"icon:{subject.id}") as drawing:
    if not drawing:
        return None
    generated = await self._generate(_icon_request(subject, self.style), ICON_RATIO)
path = self.saves / ICON_DIR / f"{subject.id}{generated.suffix}"
publish(path, lambda staged: staged.write_bytes(generated.data))
```

The claim is released at the `with` exit — *before the file exists*. A second caller entering
`_drawn_icon` in that window fails the `self.icon(...)` cache check (no file yet), wins the freed
claim, and pays the image provider for the same icon again. `Claims` exists precisely so
*"two callers never both pay for one image or clip"* (`providers.py:13`), and both sibling paths
get it right — `_draw` and `Reader.read` publish inside the hold.

**Change to.** Move the two lines inside the `with`.

**Code impact.** 2 lines, 1 file. **5 min.**

**Feature impact.** None visible. Closes a paid-API double-spend race.

---

## 7. One `httpx.AsyncClient`, not one per request — **CALL**

**Now.** `app/providers.py:38-49` builds and tears down a connection pool on every call:

```python
async def post_bearer(provider, path, body, timeout) -> bytes:
    async with AsyncClient(timeout=timeout) as client:
        reply = await client.post(...)
```

`builtin._complete` calls it once per conversation round — up to `max_rounds = 30`
(`config.py:38`) per master turn — and `speech.read` (`speech.py:63-70`) calls it once **per
spoken line** in a list comprehension. That is a fresh TLS handshake each time.

**Change to.** Hold one `AsyncClient` and pass `timeout=` per request.

**Code impact.** ~25 lines across `providers.py`, `builtin.py`, `media.py`, `speech.py`.
**30 min.**

**Feature impact.** None functionally. A latency win.

**Decision 7 — who owns the client.**
- **A (recommended).** `Runtime` owns it and passes it to `Illustrator` / `Reader` / `RoleRunner`;
  closed in `Runtime.close`. Explicit lifetime; touches 4 constructors.
- **B.** A module-level lazily-created client in `providers.py`. 10 lines, but a global with no
  owner, and `reload_settings` remounts everything around it.
- **C.** Leave it.

---

## 8. Move the big disk writes off the event loop, and reap the killed child — **CALL**

**Now.** `Runtime.new_scenario` correctly threads its blocking read (`runtime.py:442`,
`await to_thread(given_text, ...)`). Four identical blocking calls are **not** threaded, with no
comment saying why:

| Site | What blocks |
|---|---|
| `speech.py:72-79` | a multi-MB PCM→WAV write |
| `media.py:98-101`, `media.py:115` | a multi-MB image write |
| `media.py:213` `_data_uri` | up to 4 reference images read per scene |
| `runtime.py:337` `store.write` | the whole save JSON, once per turn |

They block the single event loop that also serves every open tab's 1 Hz poll.

Separately, `spawn.py:240-251`: on the timeout path `communicate()` is cancelled mid-read, `_kill`
sends `SIGKILL` and returns immediately, and nothing ever awaits the process. That is the classic
source of `ResourceWarning: subprocess N is still running` at shutdown. Fix: make `_kill` async
and `await process.wait()` after the signal.

**Code impact.** ~20 lines across `speech.py`, `media.py`, `spawn.py`. **30 min.**

**Feature impact.** None. The timed-out spawn now blocks microseconds longer while the kill is
acknowledged.

**Decision 8 — how far.**
- **A (recommended).** Thread media + speech; fix the reap. Leave `GameService.save` synchronous,
  so `save()` keeps its signature and the one-writer invariant needs no re-reasoning.
- **B.** Thread the save too — `async def save`, 7 call sites become `await`. Consistent, but it
  opens an interleaving point in the middle of turn commit and `Runtime.admit`'s one-writer rule
  needs a fresh look.
- **C.** Fix only the reap, and add one comment at `providers`/`io` saying disk writes are
  deliberately synchronous. Cheapest, and defensible for the save — not for the WAV.

---

## 9. Refresh only what changed, instead of all seven panels every tick — **BEHAVIOUR**

**Now.** `GamePage.poll_turn` runs at 1 Hz (`game.py:187`) and calls `self.refresh()` whenever
*anything* in `Observed` differs — including `facts`, which increments several times per turn as
master tool calls land. `refresh()` (`:191-198`) rebuilds everything, including the **entire** chat
history (one `ui.chat_message` per line of every exchange) and the **entire** chronicle (one
`ui.expansion` per turn played). A 50-turn game rebuilds 50 expansions and the whole transcript up
to ~10 times per turn. The code already knows this hurts — `game.py:292`: *"every `ui.audio`
registers a route, and a refresh rebuilds them all."*

**Change to.** `Observed` (`:67-83`) already carries exactly the right five fields. Split the
refresh:

```python
def refresh(self, *, whole: bool) -> None:
    self.live_turn.refresh()
    if not whole:
        return
    self.scene_header.refresh(); self.chat.refresh()
    self.decision_panel.refresh(); self.way_on_panel.refresh()
    self.sidebar.refresh(); self.journal.refresh()
```

and at `:433` pass `whole=` everything-but-`facts`-changed. The live fact cards still update,
because `live_turn` always refreshes.

**Code impact.** ~8 lines, 1 file. **15 min.**

**Feature impact.** Visible as *less* flicker and scroll-jank mid-turn. Nothing is removed from
the page. Listed as BEHAVIOUR because the page visibly changes how it updates.

---

## 10. Put stateless methods on the class that owns the state — **AUTO**

**Now.** Six methods never touch `self`. The sharpest pair sits in one file:
`twentyfourxx/world.py:245` `TwentyfourxxWorld._break(actor, item, hindrance)` mutates a
`Crewmate`'s sheet and a `Gear` and lives on neither — while its mirror image
`Crewmate.repair_item(item, cost)` (`:132`) does the same job the right way, 113 lines above it.

CLAUDE.md: *"A class owns its state and the methods that read or change it. A function whose first
argument is one of our objects is a method; a free function is for what has no owner"* and
*"a world or entity method changes fields and writes the facts."*

**Change to.**

| Now | Becomes |
|---|---|
| `twentyfourxx/world.py:245` `TwentyfourxxWorld._break` | `Crewmate.break_gear(item, hindrance)`, beside `repair_item` |
| `loner3e/world.py:163` `Loner3eWorld.strike` | free `strike(...)` beside `outcome_for` (`:197`) |
| `loner3e/world.py:176` `check_conflict` | free, same place |
| `breathless/engine.py:297` `_pool` | module-level, beside `_skill` (`:313`) |
| `loner3e/engine.py:170` `_meanings` | module-level, beside `_oracle_line` (`:268`) |

`install_sheet`, `test_luck`, `guidance`, `starting_items` and `world_of` also never touch `self`
but are override hooks and stay methods — `install_sheet` in particular cannot move onto the member
(`worldsmith.py` imports `world.py`; the reverse would cycle).

**Code impact.** ~45 lines, 5 files. `strike`, `check_conflict` and `_break` have no direct test
call sites. **40 min.**

**Feature impact.** None.

---

## 11. Give the scene-engine pack machinery an owner — **AUTO**

**Now.** `engines/scenes/engine.py` carries nine methods that are all about the installed pack set
and nothing about playing: `supplement_options` (`:100`), `select_packs` (`:107`), `selected`
(`:114`), `selected_packs` (`:118`), `chosen_packs` (`:121`), `supplement_steps` (`:239`),
`srd_pack` (`:252`), `pack_content` (`:255`), `select` (`:268`). `SceneEngine` ends up with ~30
public methods. The state they all read is `self.packs: dict[Slug, K]`, and it has no owner.

`pack_content` is the worst of them: `(selection, *, include=None, exclude_defaults=False)`, two
mutually exclusive knobs used by exactly one caller each — `breathless/engine.py:157` passes
`include=`, `loner3e/engine.py:160` passes `exclude_defaults=`, and `twentyfourxx` never calls it.

**Change to.** A `PackSet[K]` value object in `engines/scenes/packs.py`:

```python
@dataclass(frozen=True, slots=True)
class PackSet[K: ScenePack]:
    by_id: Mapping[Slug, K]

    @classmethod
    def read(cls, directory: Path, model: type[K], engine: EngineId) -> Self: ...
    def srd(self) -> K: ...
    def supplements(self) -> tuple[DecisionOption, ...]: ...
    def select(self, ids: Sequence[Slug]) -> PackSelection: ...   # checks and refuses
    def require(self, packs: PackSelection | None) -> tuple[K, ...]: ...
    def chosen(self, picks: Picks) -> tuple[K, ...]: ...
    def content(self, selection: PackSelection, dump: Callable[[K], JsonValue]) -> str: ...
```

`SceneEngine` holds `self.packs: PackSet[K]` and keeps three thin methods the seam contract needs.
Call sites read `self.packs.srd().skills` instead of `self.srd_pack().skills` — same length, and it
now says where the data lives. `content`'s single `dump` argument replaces the two knobs; each
engine passes its own lambda next to the constant that explains it.

**Code impact.** `packs.py` 27 → ~75 lines; `scenes/engine.py` −55 lines; ~20 call-site prefixes
across three engines. The worldsmith prompt goldens in `tests/core/fixtures/prompts/` must render
byte-identical — **verify, do not regenerate**. **60 min.**

**Feature impact.** None.

---

## 12. Empty `engines/hiring.py` of the three things that are not hiring — **AUTO**

**Now.** `hiring.py` is the seam for one operation, and it has become the place other engines reach
for anything shared:

- `hiring.py:10` **`ACTOR`** — the string `"Exact id of a hired party member here who acts. Null
  for the player."` Imported by `breathless/tools.py:8`, `tunnelgoons/tools.py:7`,
  `twentyfourxx/tools.py:7` and used on **13** `actor_id` fields, none of them hiring tools.
- `hiring.py:15` **`DROP_ITEM`** and `hiring.py:35` **`DropItem`** — an inventory tool. Imported by
  `breathless/engine.py:47` and `twentyfourxx/engine.py:23`. The behaviour they drive lives in
  `base.ItemSheet.drop_item`.

**Change to.** Move all three to `engines/base.py`, which already holds exactly this shape — the
shared tool payloads `Reveal`/`Kill`/`JoinParty`/`LeaveParty` (`base.py:281-294`) beside their
description constants `REVEAL`/`KILL`/`JOIN_PARTY`/`LEAVE_PARTY` (`base.py:14-17`). `hiring.py`
then holds `HIRE`, `HIRE_TOOL`, `SIGNED_ON`, `HIRE_UNWRITTEN`, `Hire`, `Hiring`, `hiring` — hiring,
and nothing else. `hiring.py` already imports `Person` from `base`, so the move is one-directional.

Leave the two verbatim `drop_item` handlers (`breathless/engine.py:210`,
`twentyfourxx/engine.py:312`) alone: a mixin to share six lines would need a generic bound that
neither loner3e nor tunnel goons can satisfy. Two copies is the bar, not a mandate.

**Code impact.** ~12 lines moved, 6 files (import lines). **20 min.**

**Feature impact.** None. The published tool schemas are byte-identical.

---

## 13. Name the dice and thresholds, and quote the constants in the tool text — **AUTO**

**Now.** LONER 3E names its die once (`loner3e/world.py:17`,
`DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows`) and uses it in the
tool, the twist roll and the pack validator. Nobody else does.

| Site | Now | Becomes |
|---|---|---|
| `twentyfourxx/engine.py:476,492` | bare `6` | `LUCK_DIE` (new — *not* `DEFAULT_DIE`; the unskilled die and the oracle die are two rules that share a number) |
| `breathless/engine.py:252` | `roll((12,), ...)` | `COMPLICATION_DIE = 12` — and `breathless/worldsmith.py:31` reads `min_length=COMPLICATION_DIE` instead of a second literal `12`. The die size and the table length are one fact in two files today. |
| `breathless/world.py:137` | `if worn == 4:` | `if worn == LADDER[0]:` — the rule is "already at the bottom of the ladder"; `4` also happens to be `STRESS_MAX` in the same file |
| `breathless/world.py:97,165` | `granted >= 10` / `granted < 10` | `MED_KIT_DIE: Die = 10` |
| `tunnelgoons/engine.py:180` | `roll((6, 6), ...)` | `DIE_FACE = 6`, matching loner3e |
| `twentyfourxx/world.py:188` | `harmless=name == "Hull armor"` | `HULL_ARMOR`, also used in `SHIP_FUNCTIONS` 162 lines above |

Same problem in the **text the model reads**. Tunnel goons interpolates
(`worldsmith.py:29`, `f"…exactly {ABILITY_POINTS} across the three."`); the others retype the value:
- `twentyfourxx/tools.py:75` `"The player pays ₡10."` → `f"…₡{UPGRADE_COST}."`
- `breathless/tools.py:59` `"an extraordinary stunt at d12."` → `f"…at d{STUNT_DIE}."`
- both `TEST_LUCK` descriptions name a die in prose → interpolate.

A rule number in two places drifts, and one of the two is what the game master reads — so the drift
is a play bug, not a lint.

**Code impact.** ~30 lines, 8 files. The rendered schema text is identical, so the goldens do not
move. **40 min.**

**Feature impact.** None.

---

## 14. Frozen means frozen, and delete the prose nobody reads — **CALL**

Three findings, all about the repo's own rule *"State models are mutable. Value models are
frozen."* Verified against pydantic 2.13.4.

**14a. `Settings` is the one config model that is not frozen.** `RoleConfig.model_config['frozen']
is True`; `Settings.model_config['frozen'] is None`. Every nested config inherits
`Configured(Frozen)`; the container of six frozen value models is itself mutable, and nothing
anywhere assigns to a `Settings` field. Add `frozen=True` to `config.py:96`. *1 line, no feature
impact.*

**14b. `Look.palette` is mutable in fact.** `core/views.py:141` types it `Mapping[str, str]`;
pydantic coerces it to a plain `dict`, and I confirmed `Look(...).palette["x"] = "y"` succeeds on
the built model. It is also the only `Mapping[...]` field on any model in the codebase — every
other frozen model spells collections as `tuple[...]`.

**14c. `description=` prose that no schema ever publishes.** `description` has exactly one job
here: it reaches a model through `schema_of` / `schema_text`, and `master_tool` (`tools.py:38`)
*enforces* it on tool args. `core/play.py:94-102` `Answer.option_id` and `Answer.text` carry
carefully written descriptions — and `Answer` is only ever constructed in `ui/game.py` and
`app/runtime.py`, never parsed from model output, never published. Same for
`core/model.py:29-33` `ScenarioMeta.scope`, whose player-facing wording already lives at
`ui/create.py:240` as the textarea placeholder. I confirmed the five `schema_of`/`schema_text` call
sites and neither model is among them. Prose written for a reader who never sees it is the most
expensive kind of dead code: the next reader assumes the model reads it. *~10 lines deleted.*

**Code impact.** 14a: 1 line. 14b: ~30 lines (4 engine palette literals reshaped), 6 files.
14c: ~10 lines, 2 files. **35 min total.**

**Feature impact.** None for any of the three.

**Decision 14 — what `Look.palette` becomes.**
- **A (recommended).** `Rows` — the `tuple[tuple[str, str], ...]` alias already in that module.
  Truly frozen, matches the `Rows`/`Sections` vocabulary; costs one `dict()` at the single reader
  (`ui/theme.py:45`).
- **B.** `dict[str, str]` — honest about what pydantic produces, and matches `PendingOption.args`
  (`play.py:75`), the codebase's other mutable-inside-frozen field. Abandons the frozen-value rule
  for both, but says so.
- **C.** Do 14a and 14c, leave the palette. *(14a and 14c are unconditional — they have no options
  and no impact.)*

---

## 15. Settle property-vs-method for argument-free accessors — **CALL**

**Now.** CLAUDE.md: *"A property takes no argument, has no side effect and reads its own fields;
anything else is a method."* The codebase breaks its own rule inside a single class:
`engines/base.py:58` `Thing.tag` and `:62` `Thing.headline` are **properties** literally
implemented as `self.subject().tag` — where `subject()` (`:103`) is a **method** that also takes no
argument and reads only its own fields.

Others in the same shape: `core/model.py:117` `Game.exchanges()` (beside `Exchange.narration` and
`Exchange.transcript`, which are properties over the same data), `base.py:70` `Thing.rows()`,
`:137` `Sheet.rows()`, `:152` `Sheeted.carried()`, `:119` `Person.forbidden()`, `:176`
`Item.notes()`, `:267` `World.sheet_rows()`.

A reader who writes `thing.tag` and then `thing.subject()` cannot infer the convention.

**Code impact.** API change — call sites lose their parens. Size depends entirely on scope.

**Decision 15 — scope.**
- **A (recommended).** `Thing.subject` only. 1 declaration, ~20 call sites across the engines,
  **20 min**. Fixes the one place where a property is literally built on top of a method.
- **B.** A + the overridable empty-returners (`rows`, `carried`, `forbidden`, `notes`,
  `sheet_rows`): ~60 call sites, **45 min**. Note these are subclass hooks, and a `@property`
  override chain (`Sheeted.rows` → `Thing.rows`) is heavier to read than a method override — a
  defensible reason to leave them as methods, **but then say so in one line on `Thing`**.
- **C.** B + `Game.exchanges`: 5 `src` call sites and ~40 test call sites across `tests/app/`,
  `tests/turn/` and every `test_play.py`. Most consistent, most churn.
- **D.** Leave them all as methods and add the one-line note on `Thing` explaining that hooks stay
  methods. **5 min**, and it closes the question honestly.

---

# Appendix — the one-line sweep

Sixteen fixes, each a handful of lines. All **AUTO** except the two marked. Together about
**90 minutes**. Strike any line you disagree with.

| # | Now | Becomes |
|---|---|---|
| S1 | `core/entities.py:10-11` — `Slug` is the only type alias in the repo spelled as a bare assignment, defended by the comment `# assignment, not `type`: pydantic reads the metadata`. **The comment is false on pydantic 2.13.4** — I verified the pattern is enforced through a `type` alias as a bare field, `Slug \| None`, `tuple[Slug, ...]` and `dict[Slug, int]`. | `type Slug = Annotated[...]`, comment deleted |
| S2 | `core/io.py:158` `read_prompt` also reads **CSS** at `ui/theme.py:69` | rename `read_cached_text`; 8 call sites |
| S3 | `engines/scenes/packs.py:24` re-implements `core/io.py:207 _read` by hand but calls `path.read_text` directly, so an unreadable pack raises `OSError` instead of the `Refusal` every other file read produces | make `_read` public as `read_model(path, model)` and call it |
| S4 | `(widget.value or "").strip()` — 12 times across `ui/game.py:442,471,484` and `ui/create.py:123,129,147,151,267,268,269,279,280` | one `def typed(field) -> str` in `ui/widgets.py` |
| S5 | `config.py:124-128` spells the three roles a **fourth** time (after `type Role`, the fields, and `for_name`'s `match`) — and it is the only one of the four that basedpyright does not exhaustiveness-check | `for role in get_args(Role)`, as `ui/settings.py:141` already does |
| S6 | `ui/app.py:183-188` wraps a `Refusal` into `str \| None` for one page, forcing `ui/settings.py:19`'s odd `Awaitable[str \| None]` signature and a branch at `:73` | pass `runtime.reload_settings` directly; `SettingsForm.save` catches `Refusal` like `create.py:132,291` and `game.py:576` already do |
| S7 | `app/mcp.py:9` imports `Runtime` to use two of its members | take `Tools` (`spawn.py:130`) — the protocol already exists and `Runtime` satisfies it structurally |
| S8 | `breathless/world.py:157` `take_loot` returns a bare `Fact` — the **only** one of 46 world/entity mutators that does not return `list[Fact]` | `list[Fact]`; drop the tuple-wrap at `breathless/engine.py:261` |
| S9 | `core/views.py:59` `place: str`, while both producers hand it a `Slug` and the consumer hashes it *because* the type is `str` (`media.py:167`) | `place: Slug` |
| S10 | `core/views.py:78-79` hand-rolls `len(set(...)) != len(...)`, losing the offending ids, one layer above `base.py:208` doing the same check on the same data via the helper | `check_unique("party members", self.party)` — *message change only* |
| S11 | `engines/hiring.py:45-50` `_no_check` declares a typevar solvable only from the default position it occupies, and is this module's one private function placed **above** the public one (the only CLAUDE.md module-layout violation found) | `check: Callable[[G], Check[A]] \| None = None` |
| S12 | `engines/seam.py:101,133,329` call `self.hiring()` three times to probe a flag — each call *builds* the writer closure to throw it away | `self.hire_writer = self.hiring()` in `__init__`, beside the other derived state |
| S13 | `engines/seam.py:327` — a concrete `worldsmith_requests` is wedged between two runs of abstract methods, 230 lines from its twin `master_tools` (`:93`), which it shares a docstring sentence with | move it beside `master_tools` |
| S14 | `engines/seam.py:66-79` — 13 bare annotations in one run, 10 the subclass contract, 3 built by `__init__`; a subclass that forgets `directory` fails with `AttributeError` mid-`__init__` | split the block with a one-line comment on each half |
| S15 | `tunnelgoons/engine.py:169-174` raises a `Refusal` for a state `Roll._one_target` (`tools.py:43`) has already made impossible, duplicating the validator's message. CLAUDE.md: an unreachable state is a bug, not a message | restructure so the narrowing is honest, as `engine.py:210` already does for `LevelUp` |
| S16 | `ui/create.py:296` `_discard_uploads()` runs only on success; the refusal path returns at `:293`, and an abandoned page leaks its temp dir (acknowledged in the comment at `:301`) | `ui.context.client.on_disconnect(self._discard_uploads)` in `build()` — *covers both paths* |

---

# Also found, ranked out of the top 15

Promote any of these and I will fold it in.

- **Split `app/spawn.py`.** 311 lines holding five jobs: CLI drivers, output scraping, process
  control, two protocols, and the model-answer retry loop. `run_cli`'s docstring says *"The only
  thing in the codebase that starts a process"* — yet half the file never touches one, and
  `app/builtin.py:10` imports `final_message` from a module called `spawn` while running an HTTP
  loop. Move the drivers + scraping to `app/drivers.py`, `ask`/`worldsmith` to `app/roles.py` where
  their callers live. ~200 lines moved, 30-40 min.
- **The `rooms` family has exactly one user.** 693 lines of `RoomEngine[N, P, G]` /
  `RoomWorld[N, P]` / `Dungeon[N]` generics, instantiated by `TunnelGoonsEngine` alone (the only
  other subclass is a test double). `scenes/` has three users. CLAUDE.md: *"Do not add an
  abstraction until two things need it."* Options: fold it into `tunnelgoons/` (~700 lines, 2-3 h,
  and tunnel goons then becomes the one engine shaped unlike the other three), or keep it and say
  why in one line on `RoomEngine`. Recommend the one line.
- **Widen the ruff rule set.** `pyproject.toml:55` selects `E, F, I, UP, B, TID252, N, ARG`. Adding
  `SIM, RUF, C4, RET, PERF` catches exactly the drift this report is full of; `FBT` has at least
  one real hit (`ui/widgets.py:22` `page_header(title, badge=None, home=True, *, look=None)` takes
  a positional bool while every other boolean in `src` is keyword-only). A reviewer opens
  `pyproject.toml` before any source file. ~1 h including the fixes.
- **LONER 3E's `Roll.actor_id` is required and non-null** (`loner3e/tools.py:61`) while the other
  three engines all spell it `actor_id: Slug | None = Field(default=None, description=ACTOR)`. The
  rule genuinely differs (LONER hires nobody), but the field name should not pretend otherwise —
  its three sibling tools already use `entity_id`. Rename it. 2 src lines + a regenerated
  `tests/core/fixtures/schemas/loner3e/master_tools.json`.
- **`SceneDraft`/`NextDraft` live in `scenes/tools.py`**, so `scenes/world.py:17` imports its own
  world shape from the *tools* module. Rooms keeps the equivalent `MapDraft` in `rooms/world.py`.
  Move them; `scenes/tools.py` is then master tool payloads only, the shape `rooms/tools.py`
  already has. ~40 lines moved, 13 files (import lines).
- **`rooms/worldsmith.py:38-63`** — `_start_unmet` and `_extension_unmet` are twelve lines
  duplicated with one boolean flipped. Fold into `_map_unmet(draft, *, start_known)`. The most
  nearly verbatim duplication in the engines.
- **`twentyfourxx/engine.py:394-438`** — `_helping` returns `Crewmate | None` while
  `args.helped_by` stays a separate `Helper | None`, so four conditions re-narrow both. Return the
  pair as one object. The least readable block in the six packages.
- **`breathless/engine.py:275-280`** hand-rolls the 1-2 / 3-4 / 5+ bands twenty lines after the
  same file reads them through `base.banded` (`:224`). Also: the two note strings there are the
  only master-facing prose in that engine written inline rather than as module constants.
- **`tunnelgoons/worldsmith.py:25` `AbilitiesDraft` has no docstring**, while breathless and 24XX
  both name theirs `SheetDraft` *with* one. `schema_of` keeps `description`, so tunnel goons hands
  the worldsmith one line less than the other two for the same job.
- **`breathless/engine.py:161,168`** render an item's die by hand (`f"d{item.die}"`) although
  `Supply.notes()` (`world.py:34`) exists and returns exactly that; `world.py:183` uses it
  correctly. 24XX goes through `notes()` everywhere.
- **`rooms/world.py`** has no `others()`, so "who else is here" is filtered in the view
  (`rooms/engine.py:132`) and again inside `place_lines` (`world.py:336`); `scenes/world.py:130`
  owns the same filter properly.
- **`tunnelgoons/world.py:47`** defines the method `level(ability, boost)` beside the field
  `GoonSheet.level: int` that its own body increments — while the tool, the engine method, the
  option builder and the decision builder are all `level_*`/`level_up`. Rename to `level_up`.
- **Three deep-copy spellings** for pydantic models in one layer: `deepcopy(x)`
  (`seam.py:301`, `model.py:122`) and `x.model_copy(deep=True)` (`scenes/engine.py:138`).
- **`PendingDecision` is built in the engine three times out of five** (`loner3e/engine.py:233`,
  `breathless/engine.py:286`, `twentyfourxx/engine.py:349`) and in the world/entity twice
  (`tunnelgoons/world.py:61`, `loner3e/world.py:156`). A pending decision is a view, not a fact.
- **`twentyfourxx/world.py:289`** uses `.tag` for the player in a trace where every other engine
  uses `.mention`; **`:232`** keys a dict by `id(item)` with no line saying why (`Gear` is mutable,
  so identity is the only key).
- **`Game.generation`** (`core/model.py:109`) is `Field(default=None, exclude=True)` — a pending
  worldsmith request is silently dropped from every save, with no comment. Either the reason is not
  visible (CLAUDE.md wants the one line) or it is a save-correctness question worth its own look.
- **`app/runtime.py:318`** calls `LOGGER.exception(..., exc_info=failed)` outside an `except`
  block; **`ui/create.py:284`** relies on `or` binding tighter than a ternary; **`ui/game.py`**
  has five bare timer floats including two different `0.1`s.

---

# Considered and rejected

- **Bind the world type into `Engine`'s generics** to delete the five one-line `world_of`
  overrides. Not possible: a PEP 695 type parameter cannot appear in another parameter's bound
  (`G: Game[W]` — basedpyright: *"TypeVar constraint type cannot be generic"*). The overrides are
  the correct workaround, and breathless correctly has none because `BreathlessWorld` is a bare
  `SceneWorld[Survivor]` alias.
- **`Illustrator` and `Reader` share a cached-media base.** They do share a shape, but the bodies
  differ enough that a base class would be three abstract hooks over ~20 saved lines.
- **`SKILL_SPREAD` should be a tuple** like every other constant in `breathless/world.py`. The list
  is load-bearing: `check_spread` (`:205`) compares it against `sorted(...)`, which returns a list,
  and a list never equals a tuple. Leave it.
- **`basedpyright` reports 1101 errors.** Only when the `qa` dependency group is absent.
  `uv sync --all-groups` — what CI runs — gives `0 errors`. Not a defect.
