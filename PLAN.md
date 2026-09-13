# PLAN: the settled review in two phases

Phase 1 is `core` and the engines; phase 2 is `app`, `config` and the pages. Two phases, because
the two halves touch disjoint files and are checked in different ways: phase 1 is guarded by the
golden fixtures, phase 2 by the QA screenshots. The wider ruff rule set has already landed, so
nothing here selects a rule. Counted against the real code, `src` **grows by about 20 lines**,
from 10,069 to about 10,090. It does not shrink, and the review's −138 was wrong: a duplicate
traded for a shared helper costs the helper's own lines, and a fix that closes a defect often
costs more than it saves. Phase 1 takes about 20 lines out; phase 2 puts about 40 back. A step
that lands correctly can make `src` bigger, so do not read growth as a mistake.

The pages keep their half-built constructors. `GamePage`, `ScenarioForm` and `CharacterForm`
declare widget attributes with no value, so reading one before `build()` raises `AttributeError`
while the type checker believes it is always there. Fixing it honestly needs a frozen widget
record and a guarded accessor at some forty read sites, about +57 lines, and the maintainer chose
not to pay that. Nothing in this plan touches those attributes; leave them as they are.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each names its files and symbols; there are no line numbers, so find
   the symbol. Where a step gives a signature or a class, that is the exact shape. The tag that
   opens a step says who may run it beside what: steps tagged `[part A]`, `[part B]`, `[part C]`
   and `[part D]` touch disjoint files and run in parallel; two steps with the same tag are one
   worker's, in order; `[sequential after N]` runs once every step up to and including N has
   landed.
2. A rename or a deletion applies across `src`, `tests` and `qa` in the same step. Change a
   shape and its tests in the same step. A test of a deleted behaviour is deleted with it.
3. Golden files live in `tests/core/fixtures/`. **No step in this plan changes one.** If a golden
   drifts, the step is wrong, so stop and find out why rather than regenerating. Two steps rewrite
   text a role reads, and for those the goldens staying byte-identical is the acceptance test:
   the shared risk fields (phase 1, step 2) and the pack set (phase 1, step 3). Verify them; do
   not regenerate them.
4. Three steps change strings that a test asserts, and each changes the test in the same step:
   the party-duplicate message (phase 1, step 1), the refusal for the player's own id in a scene
   game (phase 1, step 3), and the cards hired members carry (phase 1, step 4). No golden holds
   any of them: every scripted turn acts as the player.
5. `PROGRESS.md` gets one entry per phase: `src`, `tests` and `qa` line counts before and after
   (`find src -name '*.py' | xargs cat | wc -l`, the same for `tests` and `qa`; at the start
   `src` is 10,069 and 655 tests pass), decisions made off-plan, and refuted review findings with
   the reason. Phase 1 creates the file.
6. `ruff format --check` formats the Python inside markdown fences, and this file's fences are
   indented class-body fragments, so `pyproject.toml` already excludes `PLAN.md`. Leave that line
   alone. `PROPOSALS.md` is gone; this plan replaces it.
7. Delete, do not preserve. No second way in stays for a caller that is gone.
8. `CLAUDE.md` is not edited by any step.
9. The standing rules hold: imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond
   the `Game[P]` bound; `__init__.py` files stay empty; a class owns its state; side effects stay
   at the edges; `Refusal` is the one message-bearing exception and an unreachable state is a bug,
   not a message. The game stays playable at the end of every phase: `uv run aidm`, open each
   shipped scenario, take a turn.

## Phase 1: core and the engines

About **−20** lines in `src`. No golden moves.

### Steps

1. **[part A] The core models: one duplicate check, one typed place, and the prose no model
   reads.** Files: `core/entities.py`, `core/views.py`, `core/play.py`, `core/model.py`,
   `tests/engines/test_views.py`.

   - `core/entities.py`: `Slug` **stays a bare assignment**. Measured on pydantic 2.13.4: a
     `type Slug = Annotated[...]` alias still enforces the pattern everywhere, but it publishes a
     `dict[Slug, X]` field as `additionalProperties` plus `propertyNames`, where the assignment
     publishes `patternProperties` carrying the slug regex — that would move four worldsmith
     goldens and tell the worldsmith less about map and cast keys. Only the comment is wrong, so
     only the comment changes, to one line that says what is true:

     ```python
     # assignment, not `type`: an alias publishes a dict key as `propertyNames`, without the pattern
     ```

   - `core/views.py`: in `NarratorView._everyone_is_a_subject`, the hand-rolled
     `len(set(self.party)) != len(self.party)` becomes `check_unique("party members", self.party)`,
     imported from `aidm.core.entities` beside `Frozen`, `Refusal` and `Slug`. The message changes
     from `the party repeats an id` to `duplicate party members: ['kael']`, so in
     `tests/engines/test_views.py` the `pytest.raises(ValidationError, match="repeats")` becomes
     `match="duplicate party members"`.
   - `core/views.py`: `NarratorView.place: str` becomes `place: Slug`. Both producers already hand
     it a `Slug` (`RoomEngine.narrator_view` passes `place.id`, `SceneEngine.narrator_view` passes
     `scene.place`), and `app/media.py`'s `scene_key` hashes it *because* it names a file.
   - `core/play.py`: `Answer` is never parsed from a model and never published, so its two
     descriptions go: `option_id: Slug | None = None` and `text: str = ""`. The
     `_answers_one_way` validator stays.
   - `core/model.py`: `ScenarioMeta.scope` keeps the live rule and loses the prose the player
     already reads as the textarea placeholder on the scenario page:

     ```python
     scope: str = Field(min_length=1)
     ```

2. **[part B] The seam, the hire writer, and the shared tool descriptions.** Files:
   `engines/seam.py`, `engines/hiring.py`, `engines/base.py`,
   `engines/{breathless,tunnelgoons,twentyfourxx}/tools.py`, `tests/app/test_master_tools.py`.

   - `engines/hiring.py`: `_no_check` declares a type parameter solvable only from the default
     position it holds — generic gymnastics standing in for `| None = None` — and it is this
     module's one private function placed *above* the public one, the only module-layout
     violation in `src`. `hiring`'s parameter becomes
     `check: Callable[[G], Check[A]] | None = None`, and `write` picks the check itself:

     ```python
     checked: Check[A] = _unchecked if check is None else check(draft)
     answered = await worldsmith(prompt(draft, member, terms), answer, checked)
     ```

     `WorldsmithAnswer.__call__` takes a check, never `None`, so one plain function stands in for
     the missing one, under `hiring` where a private function belongs — a
     `Callable[[BaseModel], None]` satisfies `Check[A]` for any `A`, so it needs no generics:

     ```python
     def _unchecked(_answer: BaseModel) -> None:
         """A write whose only bar is its own schema."""
     ```
   - `engines/hiring.py` → `engines/base.py`: move `ACTOR`, `DROP_ITEM` and `DropItem` beside
     `REVEAL`/`KILL`/`JOIN_PARTY`/`LEAVE_PARTY` and their arg models, which are exactly this
     shape. `ACTOR` is read by 13 `actor_id` fields in three engines and `DropItem` is an
     inventory tool; neither has anything to do with hiring. This step repoints the imports in
     the three `tools.py` files and in `tests/app/test_master_tools.py`. `breathless/engine.py`
     and `twentyfourxx/engine.py` also import `DROP_ITEM` and `DropItem` from `hiring`, but part C
     owns both files, so **step 4 repoints those two** — it is one import line each.
   - `engines/base.py`: `banded`'s docstring says "a six-sided read" while its callers read d4 to
     d12 pools. It becomes `"""Three bands, whatever the die: 1 to 2, 3 to 4, 5 and up."""`
   - `engines/seam.py`: `Engine.hiring()` is called three times to probe a flag, and each call
     builds the writer closure and throws it away. `__init__` keeps it once, before
     `self.master_tools()` reads it:

     ```python
     self.hire_writer = self.hiring()
     ```

     `master_tools` and `worldsmith_requests` test `self.hire_writer is None`; `write_hire` tests
     it, raises the same `ValueError` and calls `self.hire_writer(...)`.
   - `engines/seam.py`: move `worldsmith_requests` up beside `master_tools`, out of the run of
     abstract methods it is wedged into — they share a docstring sentence and are the same kind of
     thing. Then split the annotation block at the top of `Engine` in two, with one comment on
     each half: the ten a subclass sets (`id` … `character`), and the four `__init__` derives
     (`instructions`, `tools`, `requests`, `hire_writer: Hiring[G, M] | None`).
   - `engines/twentyfourxx/tools.py`: `Helper` and `Roll` repeat three fields and one validator,
     the largest verbatim clone in `src`. **No shared base class**: pydantic puts a base's fields
     first, which would reorder the published schema and move
     `tests/core/fixtures/schemas/twentyfourxx/master_tools.json`. Share the three pieces that
     can be shared without moving a field. Two constants beside the other tool text:

     ```python
     DEFEND_WITH = (
         "Exact id of the {who}'s item or a ship function that breaks to spare them. Null when "
         "nothing shields them."
     )
     HINDRANCE = (
         "What the hit leaves behind once the gear absorbs it, as a hindrance. Empty when the "
         "gear breaks harmlessly."
     )
     ```

     One check helper, in the public-function run under the classes:

     ```python
     def check_risk(risk: str, defend_with: Slug | None, hindrance: str) -> None:
         if defend_with is not None and not risk:
             raise ValueError("defend_with needs the risk it shields against")
         if hindrance and defend_with is None:
             raise ValueError("hindrance needs the defend_with that earns it")
     ```

     In `Helper` and in `Roll`, in the position each field holds today:

     ```python
     defend_with: Slug | None = Field(default=None, description=DEFEND_WITH.format(who="helper"))
     hindrance: str = Field(default="", description=HINDRANCE)

     @model_validator(mode="after")
     def _defend_fields(self) -> Self:
         check_risk(self.risk, self.defend_with, self.hindrance)
         return self
     ```

     `Roll` passes `who="actor"`. The two `risk` descriptions differ by more than one word and
     stay as they are. `Defend.hindrance` says something else and is not touched. The rendered
     text is byte-identical, so the master-tools golden must not move — that is the test.

3. **[part C] The pack set gets an owner, and the player is not a party member.** Files:
   `engines/scenes/packs.py`, `engines/scenes/engine.py`, `engines/scenes/world.py`,
   `core/io.py`, the pack call sites in `engines/{breathless,loner3e,twentyfourxx}/engine.py`,
   `tests/engines/test_scenes.py`, `tests/breathless/test_engine.py`,
   `tests/twentyfourxx/test_worldsmith.py`.

   - `core/io.py`: `_read` becomes public as `read_model(path, model)` and moves into the
     public-function run (its three callers in `Library` keep working). `read_packs` in
     `engines/scenes/packs.py` re-implements it by hand but calls `path.read_text` directly, so an
     unreadable or non-UTF-8 pack raises `OSError`/`UnicodeDecodeError` instead of the `Refusal`
     every other file read in the repo gives.
   - `engines/scenes/packs.py`: nine methods on `SceneEngine` are about the installed packs and
     nothing about playing, and the state they read (`self.packs`) has no owner. Add the owner
     here and fold `read_packs` into it:

     ```python
     @dataclass(frozen=True, slots=True)
     class PackSet[K: ScenePack]:
         """Every pack installed for one engine, and what a game may select from them."""

         engine: EngineId
         installed: Mapping[Slug, K]

         @classmethod
         def read[P: ScenePack](
             cls, engine: EngineId, directory: Path, model: type[P]
         ) -> "PackSet[P]":
             packs = {
                 content_id(path.stem): read_model(path, model)
                 for path in sorted(directory.glob("*.json"))
             }
             if SRD_PACK not in packs:
                 raise ValueError(f"the {engine!r} engine ships no {SRD_PACK!r} pack")
             return PackSet(engine, packs)

         def srd(self) -> K:
             return self.installed[SRD_PACK]

         def supplements(self) -> tuple[tuple[Slug, K], ...]:
             return tuple((key, pack) for key, pack in self.installed.items() if key != SRD_PACK)

         def require(self, selection: PackSelection | None) -> PackSelection:
             if selection is None:
                 raise Refusal(f"a {self.engine!r} game needs a table set")
             return selection

         def chosen(self, selection: PackSelection | None) -> tuple[K, ...]:
             return tuple(self.installed[pack_id] for pack_id in self.require(selection).ids)

         def content(self, selection: PackSelection, dump: Callable[[K], JsonValue]) -> str:
             selected = {pack_id: dump(self.installed[pack_id]) for pack_id in selection.ids}
             return f"SELECTED PACK CONTENT\n{json.dumps(selected)}"
     ```

     `read` takes its own type parameter and returns `PackSet[P]`, not `Self`. With the
     class-scoped `K`, basedpyright cannot solve it from an unsubscripted `PackSet.read(...)`:
     it reports the result partially unknown, `SceneEngine.packs` becomes `PackSet[Unknown]`,
     and the gate fails.

     `select(selection)` moves here too, body unchanged but reading `self.installed` and naming
     `self.engine` in its three refusals.
   - `engines/scenes/engine.py`: `packs: dict[Slug, K]` becomes `packs: PackSet[K]`, built in
     `__init__` as `self.packs = PackSet.read(self.id, self.directory / "packs", self.pack)` —
     the SRD check moves with it. Delete `selected`, `selected_packs`, `srd_pack`,
     `pack_content` and `select`. Keep the three the seam contract needs, each now one line:
     `supplement_options` builds its `DecisionOption`s from `self.packs.supplements()`,
     `select_packs` ends `self.packs.select(parse(PackSelection, {"ids": (SRD_PACK,
     *supplements)}))`, and `admit` opens `selection = self.packs.require(packs)`. `validate`
     becomes `self.packs.select(self.packs.require(state.packs))` and `author` opens
     `selection = self.packs.select(self.packs.require(packs))` — both call the two deleted
     methods today; `supplement_steps` and
     `chosen_packs` stay, reading `self.packs.supplements()` and `self.packs.installed`.
   - The ~20 call sites in `breathless/engine.py`, `loner3e/engine.py` and
     `twentyfourxx/engine.py` gain the prefix: `self.srd_pack()` → `self.packs.srd()`,
     `self.selected_packs(state)` → `self.packs.chosen(state.packs)`, and
     `self.selected(selection)` → `self.packs.require(selection)`. `pack_content`'s two
     mutually exclusive knobs become one
     `dump` callable, and each engine passes its own private function beside the constant that
     explains it — in `breathless/engine.py`:

     ```python
     def _authored(pack: Pack) -> JsonValue:
         return pack.model_dump(mode="json", include=AUTHORED)
     ```

     with `AUTHORED = {"locations", "complications", "missions"}` among the module constants and
     `_authored` in the private-function run at the foot of the file, which is where CLAUDE.md's
     module layout puts it. The same in `loner3e/engine.py`:

     ```python
     def _revised(pack: Pack) -> JsonValue:
         """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
         return pack.model_dump(mode="json", exclude_defaults=True)
     ```

     taking the docstring off `guidance`. `twentyfourxx` never called it. The dumps are the same
     dicts as today, so the worldsmith prompt goldens must not move — **verify, do not
     regenerate.**
   - `engines/scenes/world.py`: `require_member_here` is a bare alias for `require_living_here`,
     which returns the player for their own id — so in a scene game `join_party("player")` does
     not refuse; it appends the player to `party` and only blows up at commit with *the player
     cannot travel with themselves*. Rooms refuses it at once. Give the alias a body:

     ```python
     def require_member_here(self, entity_id: Slug) -> C:
         if entity_id == self.player.id:
             raise Refusal("the player is not a party member")
         return self.require_living_here(entity_id)
     ```

     `require_living_here` **stays**: `Loner3eEngine.change_tags`, `drive`, `restore_luck` and
     `roll` resolve the player through it, and renaming it into `require_member_here` would refuse
     the player their own tags. `join_party` and `hire` on the player's own id now refuse with a
     readable message. Add one test in `tests/engines/test_scenes.py` that `join_party` on the
     player's id refuses with "not a party member".
   - Tests: `ENGINE.packs["srd"]` becomes `ENGINE.packs.srd()` in
     `tests/twentyfourxx/test_worldsmith.py` and `tests/breathless/test_engine.py`;
     `engine.select(...)` becomes `engine.packs.select(...)` and the twin-pack setup becomes
     `engine.packs = PackSet(engine.id, {**engine.packs.installed, "twin": engine.packs.srd()})`
     in `tests/engines/test_scenes.py`.

4. **[part C] The three scene engines: one helper, one band read, one card prefix.** Files:
   `engines/breathless/engine.py`, `engines/breathless/world.py`,
   `engines/twentyfourxx/engine.py`, `engines/twentyfourxx/world.py`,
   `tests/breathless/test_world.py`, `tests/breathless/test_tools.py`,
   `tests/twentyfourxx/test_tools.py`, `tests/twentyfourxx/test_world.py`.

   - `breathless/engine.py` and `twentyfourxx/engine.py`: repoint `DROP_ITEM` and `DropItem` to
     `aidm.engines.base`, which step 2 moves them to. One import line each.
   - `twentyfourxx/engine.py`: `roll` is the least readable block in the engines. `_helping`
     returns `Crewmate | None` while `args.helped_by` stays a separate `Helper | None`, so four
     conditions re-narrow both. Return the pair as one thing, beside `Pool`:

     ```python
     @dataclass(frozen=True, slots=True)
     class Helping:
         member: Crewmate
         args: Helper
     ```

     and, in the private run under the classes — free, not a method, because it builds an
     engine-side value and the world it reads is the layer below:

     ```python
     def _helping(world: TwentyfourxxWorld, args: Helper | None) -> Helping | None:
         return None if args is None else Helping(world.require_actor(args.actor_id), args)
     ```

     `roll` calls `helping = _helping(world, args.helped_by)` and drops the `helper_args =
     args.helped_by` local; every `helper is not None and helper_args is not None` becomes
     `helping is not None`, and the reads become `helping.member` and `helping.args`. `_pool`
     takes `helping: Helping | None` in place of `helper`, checks `helping.member is actor` for
     the "cannot help their own roll" refusal, and its walrus on `args.helped_by` goes.
   - `breathless/engine.py`: `loot_check` hand-rolls the 1-2 / 3-4 / 5+ bands twenty lines after
     `roll` reads exactly those bands through `banded`. Lift the two notes to module constants
     beside the engine's other master-facing prose, as `loner3e` does with `TWIST_NOTE` and
     `DEFEAT_NOTE`:

     ```python
     TROUBLE_NOTE = "The scavenge turns up trouble right here; nothing is found."
     NOTHING_NOTE = "The scavenge finds nothing, and trouble is coming."
     ```

     and read the bands once, keeping the `LADDER` lookup for the find size:

     ```python
     outcome = banded(face, "trouble", "nothing", "found")
     found = next(die for die in LADDER if face <= die) if outcome == "found" else None
     if found is None:
         draft.note(TROUBLE_NOTE if outcome == "trouble" else NOTHING_NOTE)
     ```

   - `breathless/world.py`: `take_loot` is the only one of 46 world and entity mutators that
     returns a bare `Fact`. It returns `list[Fact]`, and `BreathlessEngine.answer` drops the
     tuple-wrap: `return tuple(self.world_of(draft).player.take_loot(...))`.
   - `breathless/world.py` and `twentyfourxx/world.py`: every card that can belong to someone
     other than the player goes through `self.card_line(...)`, which `Thing` has carried all
     along. In breathless, `catch_breath`'s three-line conditional becomes
     `card=self.card_line("Caught breath — skills and loot die restored")`, which leaves
     `PLAYER_ID` unused in `breathless/world.py` — drop it from the `aidm.engines.base` import or
     `ruff check` fails. `use_med_kit`'s
     `card="Med kit used"` becomes `card=self.card_line("Med kit used")` — the file prefixes
     `change_stress` through `Thing.change` but not these two. In 24XX, `card_line` appears
     nowhere at all: `change_hindrances`, `gain_item`, `repair_item`, `spend`, `maim`,
     `raise_skill` and `earn` all wrap their card, so a hired crew member's card stops reading
     "Gained Rope" with no name on it. The break cards written by `take_hit` are not touched.
     `take_loot` is the player's own and keeps its card as it is.
   - The mid-line roll prefix (the name sits inside the sentence) cannot use `card_line`;
     `breathless/engine.py` and `twentyfourxx/engine.py` already call that local `prefix` and stay
     as they are.
   - Tests: the cards for hired members now carry their name. Run the suite and repoint each
     failing assertion to the prefixed text. Note the old member wording is not the new one with
     a prefix bolted on: `"Mira caught breath — skills and loot die restored"` becomes
     `"Mira: Caught breath — skills and loot die restored"` — lowercase to capital, space to
     colon. The player's cards do not move, so every assertion that names the player stays as it
     is, and no golden turn holds a member's card.

5. **[part D] The rooms family and tunnel goons.** Files: `engines/rooms/worldsmith.py`,
   `engines/rooms/world.py`, `engines/rooms/engine.py`, `engines/tunnelgoons/engine.py`,
   `engines/tunnelgoons/world.py`, `tests/tunnelgoons/`.

   - `rooms/worldsmith.py`: `_start_unmet` and `_extension_unmet` are the same twelve lines with
     one boolean inverted — `check_map` wants the start known to the player, `check_extension`
     wants it hidden. One function:

     ```python
     def _map_unmet[N: Dweller](draft: MapDraft[N], *, start_known: bool) -> list[str]:
         places = draft.places
         if draft.start not in places:
             return [f"a starting place {draft.start!r}"]
         unmet: list[str] = []
         if places[draft.start].known != start_known:
             unmet.append(
                 "the starting place known to the player"
                 if start_known
                 else "a starting place hidden from the player"
             )
         if missing := sorted(set(places) - draft.reachable(draft.start)):
             unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
         return unmet
     ```

     `check_map` calls it with `start_known=True`. `check_extension` keeps its own empty-map
     guard, which now raises before the overlap check instead of joining it — today a places-less
     draft whose ids also collide names both faults in one sentence, and after this it names only
     the first. No test asserts that pair. Then it calls the shared function with
     `start_known=False`:

     ```python
     def check_extension[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> None:
         if not draft.places:
             raise Refusal("the extension needs at least one new place")
         if unmet := _map_unmet(draft, start_known=False) + _overlap_unmet(draft, world):
             raise Refusal("the extension needs " + "; ".join(unmet))
     ```

     Same refusal strings, same order.
   - `rooms/world.py`: `move` and `unlock_way` each spell out the same four lines that reveal a
     way and its back-way. One private method on `RoomWorld`, beside them:

     ```python
     def _open_way(self, here: Place, destination: Place) -> None:
         """Walked or unlocked, a way is known from both sides."""
         for way in (self.way(here.id, destination.id), self.way(destination.id, here.id)):
             if way is not None:
                 way.known = True
     ```

     Both callers keep their own three-line lookup before it: `move` needs the way itself for the
     locked check and lists the ways out in its refusal, and `unlock_way` refuses differently.
   - `rooms/world.py` and `rooms/engine.py`: "who else is here" is filtered inside the view. The
     world owns it, as `SceneWorld.others` does, beside `things_at`:

     ```python
     def others(self) -> Iterator[N]:
         return (npc for npc in self.at(self.current.id) if npc.known and npc.id not in self.party)
     ```

     `RoomEngine.player_view` then asks: `here_panel(other.subject() for other in world.others())`,
     the same line `SceneEngine.player_view` already has. `place_lines` keeps its own filter: it
     lists props as well as npcs, so `others()` cannot stand in for it.
   - `tunnelgoons/engine.py`: `roll` raises a `Refusal` for a state `Roll._one_target` has already
     made impossible, duplicating the validator's own message. The narrowing becomes honest, the
     way `level_up` already handles the `LevelUp` pair: the two-line guard goes and the read
     carries the reason.

     ```python
     # `Roll._one_target` has held one of the two: with no npc, a difficulty was named.
     ds = npc.hp.current if npc is not None else (args.difficulty or 0)
     ```

   - `tunnelgoons/world.py`: `Adventurer.level` re-makes the card-prefix decision by hand. Rebind
     the local, do not pass a keyword: the two-line `if self.id != PLAYER_ID` prefix becomes
     `card = self.card_line(card)` on the line that builds it, and the return stays
     `self.fact(card, card=card)`. Passing `card=self.card_line(card)` instead would keep the card
     right and quietly strip the name from the **trace**, which no test asserts for a member.
     `PLAYER_ID` stays imported here; the file still uses it. The rendered text is unchanged, so
     `tests/tunnelgoons/test_world.py` stays green. In `tunnelgoons/engine.py`, the mid-line roll
     prefix local `who` is renamed `prefix`, the name the other two engines use.

6. **[sequential after 5] One name for the cached reader.** Files: `core/io.py`,
   `engines/seam.py`, `app/roles.py`, `turn/run.py`, `ui/theme.py`, `tests/engines/test_seam.py`.
   `read_prompt` also reads CSS, in `ui/theme.py`'s `install`. Rename it `read_cached_text` and
   change its eight call sites (three in `engines/seam.py`, two in `app/roles.py`, one each in
   `turn/run.py`, `ui/theme.py` and `tests/engines/test_seam.py`) and their five import lines.
   Nothing else changes; it runs last so that no parallel worker is holding one of these files.

## Phase 2: the app, the settings and the pages

About **+40** lines in `src`, most of it the shared connection pool and the task nursery. No
golden moves, and no step changes text a role or the player reads. The check for the pages is
`qa/run_all.sh` — its screenshots must show the same pixels.

### Steps

1. **[sequential after 2] The session builds itself, and the background tasks move out.** Files:
   `app/runtime.py`, new `app/background.py`, `tests/app/test_game_service.py`,
   `tests/app/test_mcp.py`, `tests/app/test_launcher.py`, `tests/support/table.py`,
   `qa/server.py`. It runs after step 2 because it calls `close_posting`, which step 2 writes.
   It does **not** touch `ui/app.py`; step 4 owns that file and makes the one call-site change
   named below.

   - `Runtime` has four `field(init=False)` attributes with no default, so `Runtime(settings)` is
     legal Python and returns an object whose `engines`, `spawner`, `library` and `store` each
     raise `AttributeError`; only `Runtime.start()` works, and nothing in the type says so. The
     two lines of `start` move into `__post_init__`, which takes its docstring:

     ```python
     def __post_init__(self) -> None:
         """Reads every engine's prompts and packs, then mounts the library and the saves."""
         self.engines = build_engines()
         self._mount()
     ```

     `start` is deleted. Its **fifteen** call sites become `Runtime(settings)` /
     `Runtime(settings, lambda _: spawner)` — same arguments, same order:
     `tests/app/test_game_service.py` ×6, `tests/app/test_launcher.py` ×5, and one each in
     `tests/app/test_mcp.py`, `tests/support/table.py`, `qa/server.py` and `ui/app.py`. The last
     one is step 4's, since step 4 owns `ui/app.py`; the other fourteen are this step's.
   - `GameService` does six jobs in ~295 lines. The task nursery is the half that has nothing to
     do with playing a turn, so it moves to a new `app/background.py`:

     ```python
     @dataclass(slots=True)
     class Tasks:
         """Work the session started and does not wait for: retained while it runs."""

         running: set[Task[None]] = field(default_factory=set)

         def retain(self, task: Task[None]) -> None:
             """Retained because asyncio may collect an unreferenced task early."""
             self.running.add(task)
             task.add_done_callback(self._done)

         async def settled(self) -> None:
             await gather(*self.running)

         async def close(self) -> None:
             tasks = list(self.running)
             for task in tasks:
                 task.cancel()
             await gather(*tasks, return_exceptions=True)

         def _done(self, task: Task[None]) -> None:
             self.running.discard(task)
             if task.cancelled():
                 return
             if (failed := task.exception()) is not None:
                 LOGGER.exception("background task failed", exc_info=failed)
     ```

     `app/background.py` declares its own `LOGGER = logging.getLogger(__name__)`; the log text
     `"background task failed"` is asserted in `tests/app/test_game_service.py` and survives the
     logger-name change, because the assertion reads `caplog.text`.

     `GameService` loses `_background`, `_retain`, `_settled`, `settled` and the cancelling half of
     `close`, and gains `tasks: Tasks = field(default_factory=Tasks)`. Every `self._retain(x)`
     becomes `self.tasks.retain(x)`; `close` becomes `self.hush()` then `await
     self.tasks.close()`. The media fan-out **stays** on `GameService` — it is at least about a
     game session — so `Illustrator | None` and `Reader | None` keep threading through `resume`.
   - `Runtime.close` also closes the shared HTTP pool that step 2 adds, as its last line:
     `await close_posting()`, imported from `aidm.app.providers`.
   - Tests: `tests/app/test_game_service.py` pokes `game._retain(...)` and `game._background`;
     both become `game.tasks.retain(...)` and `game.tasks.running`, and the
     `reportPrivateUsage` ignores come off. `tests/support/table.py`'s `drain` calls
     `service.tasks.settled()`.

2. **[part A] One connection pool, no blocking write, no stray child, no double-spend.** Files:
   `app/providers.py`, `app/spawn.py`, `app/speech.py`, `app/media.py`.

   - `app/providers.py`: `post_bearer` builds and tears down a connection pool on every call —
     once per conversation round for a built-in master (up to `max_rounds`, 30) and once per
     spoken line for the reader, each a fresh TLS handshake. One pool for the process, made
     lazily so nothing is built at import:

     ```python
     @cache
     def posting() -> AsyncClient:
         """One pool for the process: a client per call pays a new handshake."""
         return AsyncClient()


     async def close_posting() -> None:
         if posting.cache_info().currsize:
             await posting().aclose()
             posting.cache_clear()
     ```

     `post_bearer` keeps its signature and passes the per-call timeout to the request:
     `await posting().post(url, headers=..., json=body, timeout=timeout)`. It stays a free
     function in this module, because `tests/app/test_builtin.py`, `test_speech.py` and
     `test_media.py` monkeypatch it by name in each consumer module. `Runtime.close` calls
     `close_posting` (step 1).
   - `app/speech.py` and `app/media.py`: four blocking disk calls run on the event loop that also
     serves every open tab's poll. Both files need `to_thread` from `asyncio`; neither imports it
     today. while `Runtime.new_scenario` already threads its blocking read.
     `Reader.read`'s `publish(path, write)` becomes `await to_thread(publish, path, write)`;
     `Illustrator._draw`'s and `_drawn_icon`'s `publish(...)` calls do the same. In
     `Illustrator._generate` the reference images are read off the loop before the parts are
     built:

     ```python
     uris = await to_thread(lambda: [_data_uri(path) for path in references])
     parts.extend({"type": "image_url", "image_url": {"url": uri}} for uri in uris)
     ```

   - `app/media.py`: `_drawn_icon` releases its claim at the `with` exit, *before* the file
     exists, so a second caller entering in that window fails the cache check, wins the freed
     claim and pays the image provider for the same icon again. The path, the `publish` and the
     `return path` all move inside the `with self.claims.hold(...)` block, as `_draw` and
     `Reader.read` already do.
   - `app/spawn.py`: on the timeout path `communicate()` is cancelled mid-read, `_kill` sends
     `SIGKILL` and returns, and nothing awaits the process — the classic
     `ResourceWarning: subprocess N is still running` at shutdown. `_kill` becomes
     `async def _kill(process)` and awaits `shield(process.wait())` after the signal (and after
     the `returncode is not None` return), with `shield` from `asyncio`; `_spawn`'s `finally`
     becomes `await _kill(process)`. The shield is the point: `GameService.hush` cancels the
     interjection task, so the common path reaches this `finally` already cancelled, and a bare
     `await` there would raise before reaping anything.
   - `app/spawn.py`: `CodexDriver.read_result` and `_last_said` hold the same event-stream parse
     verbatim. One private function beside `_object`:

     ```python
     def _events(output: str) -> list[JsonValue]:
         return [event for line in output.splitlines() if (event := _object(line)) is not None]
     ```

     Both call sites become `events = _events(output)`. This costs three lines and buys one
     parse; it is here because the two copies must not drift.
   - `app/speech.py`: `Reader.clip` and `Reader.read` open with the same three-step walk
     (`requests_of` → `clip_key` → `_path`). One private method replaces `_path`:

     ```python
     def _planned(self, exchange: Exchange) -> tuple[tuple[tuple[str, str], ...], str, Path]:
         """What to speak, the key it hashes to, and the file that key names."""
         requests = requests_of(exchange, self.voice, self.config.voices)
         key = clip_key(self.config.model, requests)
         return requests, key, self.saves / f"{key}.wav"
     ```

     `clip` becomes `_, _, path = self._planned(exchange)`; `read` becomes
     `requests, key, path = self._planned(exchange)`.

3. **[part B] The settings name their roles once and freeze.** Files: `config.py`,
   `tests/ui/test_settings.py`.

   - `Settings._keys_present` spells the three roles a fourth time — after `type Role`, the
     fields and `for_name`'s `match` — and it is the one of the four that basedpyright does not
     exhaustiveness-check, so a new role can be forgotten here in silence. It reads the alias
     instead:

     ```python
     named: tuple[Role, ...] = get_args(Role.__value__)
     for role in named:
         config = self.roles.for_name(role)
         if config.provider in ("openrouter", "local"):
             posting.append((role, config.provider))
     ```

     `Role.__value__`, not `Role`: `get_args` on a PEP 695 alias returns `()`, which would skip
     every check in silence — the settings page unwraps the alias the same way in `_unaliased`.
     Import `get_args` from `typing`.
   - `Settings` is the one config model not frozen, while all six of its nested configs inherit
     `Configured(Frozen)`. Add `frozen=True` to its `SettingsConfigDict`. One place does assign to
     a `Settings` field: `test_only_a_real_edit_is_written` in `tests/ui/test_settings.py` opens
     `settings.roles = RoleSettings(...)`, which then raises. It builds the settings it wants
     instead:

     ```python
     settings = updated(
         offline_settings(tmp_path),
         roles=RoleSettings(narrator=RoleConfig(model="sonnet")).model_dump(),
     )
     ```

4. **[part C] The pages: one banner, one gap scale, one error convention.** Files:
   `ui/widgets.py`, `ui/theme.css`, `ui/app.py`, `ui/settings.py`, `ui/create.py`, `ui/game.py`.
   No test changes: `_page` in `tests/ui/test_game.py` sets the widget attributes directly, and
   those attributes are not touched.

   - `ui/app.py`: `Runtime.start` is gone (step 1), so `_register_pages`'s caller becomes
     `Runtime(settings)`. This step owns the file, so it makes that one-line change.
   - `ui/settings.py` and `ui/app.py`: `_register_pages` wraps a `Refusal` into `str | None` for
     one page, which forces `SettingsForm.__init__`'s odd `Awaitable[str | None]` and a branch in
     `save`. Delete `apply_settings` and pass `runtime.reload_settings` straight to
     `settings_page`; `apply` becomes `Callable[[], Awaitable[None]]` in both `SettingsForm` and
     `settings_page`, and `save` catches the refusal where it happens, as `create.py` and
     `game.py` already do:

     ```python
     try:
         await self.apply()
     except Refusal as refused:
         ui.notify(
             f"{refused} The keys are written; they apply on the next restart.", type="warning"
         )
         return
     ```

   - `ui/widgets.py` and `ui/game.py`: the decision banner is verbatim in `GamePage.chat` and
     `GamePage.way_on_panel`. One context manager beside `section()`:

     ```python
     @contextmanager
     def banner(icon: str) -> Generator[None]:
         """The decision strip: one card row with the icon that names it."""
         with ui.row().classes("game-card game-decision w-full items-center no-wrap game-gap-md"):
             ui.icon(icon).classes("game-card-icon")
             yield
     ```

     Both sites become `with banner("record_voice_over"):` and `with banner("arrow_forward"):`.
   - `ui/theme.css` and every `ui/*.py`: `theme.py` calls itself the single source for every hex
     value; the spacing scale belongs with it. The ten gap values the pages use today, each kept
     exactly:

     ```css
     .game-gap-0 { gap: 0 }
     .game-gap-3xs { gap: .15rem }
     .game-gap-2xs { gap: .2rem }
     .game-gap-xs { gap: .25rem }
     .game-gap-sm { gap: .3rem }
     .game-gap-md { gap: .4rem }
     .game-gap-lg { gap: .5rem }
     .game-gap-xl { gap: .75rem }
     .game-gap-2xl { gap: 1rem }
     .game-gap-3xl { gap: 1.25rem }
     ```

     Every inline `gap:` in `ui/app.py`, `ui/create.py`, `ui/game.py` and `ui/widgets.py` becomes
     one of these classes, which also settles the split spelling (`widgets.py` writes `.5rem`
     where `game.py` writes `0.5rem` for the same gap). Two calls keep a `.style(...)` for their
     other half: `game.py`'s `.style("gap: 0; min-width: 0")` keeps `min-width`, and
     `widgets.py`'s `page_body` keeps `max-width`. The one call that stays whole is
     `ui.query(".nicegui-content").style("padding: 0; gap: 0")` — it reaches NiceGUI's own div,
     which the page never builds and cannot give a class. The values are unchanged, so the QA
     screenshots must be pixel-identical.
   - The imports these edits need, none of which the files carry today: `Refusal` from
     `aidm.core.entities` in `ui/settings.py`; `banner` from `aidm.ui.widgets` and `replace` from
     `dataclasses` in `ui/game.py`.
   - `ui/create.py`: `ScenarioForm._discard_uploads` runs only after a successful write — the
     refusal path returns before it, and an abandoned page leaks its temp directory, which the
     comment there admits. `build()` registers it instead:
     `ui.context.client.on_disconnect(self._discard_uploads)`, which covers both paths — and the
     comment inside `_discard_uploads` goes with the leak it described.
   - `ui/game.py`: `poll_turn` calls `refresh()` whenever anything in `Observed` differs,
     including `facts`, which climbs several times a turn — and `refresh()` rebuilds the whole
     chat history and the whole chronicle each time. `Observed` already carries the five fields
     needed to tell "a fact landed" from "the turn closed":

     ```python
     def refresh(self, *, whole: bool) -> None:
         self.live_turn.refresh()
         self.decision_panel.refresh()
         self.way_on_panel.refresh()
         if not whole:
             return
         self.scene_header.refresh()
         self.chat.refresh()
         self.sidebar.refresh()
         self.journal.refresh()
     ```

     and in `poll_turn`, with `replace` imported from `dataclasses`. The flag must be taken
     **before** `self.seen = now`, beside the existing `landed = ...`; computed after it the
     comparison is `x != x`, always `False`, and the chat would never redraw again:

     ```python
     landed = now.exchanges > self.seen.exchanges
     # Only the fact count moved: the live turn is the only part that can have changed.
     whole = replace(now, facts=0) != replace(self.seen, facts=0)
     self.seen = now
     ```

     and the `self.refresh()` line becomes `self.refresh(whole=whole)`.

     The live fact cards still update every tick, because `live_turn` refreshes unconditionally.
     A player sees less flicker mid-turn and nothing else.
