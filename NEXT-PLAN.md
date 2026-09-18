# NEXT-PLAN: human code

Done after `PLAN.md`. The target: `src/aidm/engines` reads like code one person wrote. One class
per thing, its fields written out. One place per tool. A world that writes its own facts. One type
parameter at most, and only on a container. No family layer, no hook an engine must know exists
before it can be read top to bottom.

This plan adds lines. Every step was prototyped on `3ebf53f` with the four checks green, and the
sum is about **+250 `src`, +250 `tests`**. The measure of done is a reader, not a count: after the
last step someone opens `engines/tunnelgoons/world.py` and knows what a goon is without opening
another file. Prompts and saves change only where a step says so and says why.

Symbol names are as of `PLAN.md` phase 3 done. One phase, seven steps, in this order, each one
green on the full check before the next (`uv run pytest`, `uv run ruff check`, `uv run ruff
format --check`, `uv run basedpyright`, `UV_CACHE_DIR` unset). Two rules beyond CLAUDE.md:

- No `# type: ignore`, no `cast`. A step that cannot type without one stops and says so in
  `PROGRESS.md`.
- A copy is fine. Two engines each carrying ten plain lines beat one base carrying a hook, a
  flag or a renamed accessor to share them.

1. **The hire flow belongs to the engines that hire.** `Engine.hires`, `Engine.hire`,
   `Engine.write_hire`, `Engine.write_sheet`, `Engine.worldsmith_requests`, the `Request` and
   `Written` classes, `Engine.requests` go. `Engine.unwritten: dict[Slug, Fact]` names the
   fact filed when a request fails (`EXTEND`, `DEPARTURE`, `COMPLICATION`, `HIRE`, each engine
   its own); `Engine.validate` checks `request.operation in self.unwritten`; `Engine.advance(
   draft, request, worldsmith) -> str | None` is abstract and each engine's is one `match
   request.operation` returning the telling. `TunnelGoonsEngine` and `TwentyfourxxEngine` each
   carry `hire` (the tool method, registered right after `leave_party` so the schema goldens
   hold), `write_hire` and their own `HIRE_TOOL`/`Hire`/`SIGNED_ON`/`HIRE_UNWRITTEN` in their
   `tools.py`; Loner has none. `World.require_hireable` and the `hired` branch of
   `World.require_actor` move to those two worlds. `app/runtime.py` `_grow` reads
   `engine.unwritten[op]` and the telling. `tests/engines/test_hire_tool.py` imports from the
   engine's `tools.py`.
2. **A world writes its own facts.** `engines/base.py`: `World.facts: list[Fact] = Field(
   default_factory=list, exclude=True)` and `World.tell(fact: Fact) -> None`. `Thing.fact` stays
   the one builder of a fact about a thing (`told=self.known` lives there and nowhere else).
   `Thing.change` and `Thing.reveal` become `World.change(thing, gauge, amount, label, why)` and
   `World.reveal(thing, *, card="")`. Every method under `src/aidm/engines` that returned
   `list[Fact]` or `tuple[Fact, ...]` (about 70) tells and returns `None`; an entity method that
   changes its own fields and has no world (`Loner3eCast.change_tags`, `drive`, `refill`,
   `spend_luck`, `lose`, `recover`; `Crewmate.change_hindrances`, `gain_item`, `repair_item`,
   `spend`, `hinder`, `raise_skill`, `earn`; `CrewSheet.drop_item`; the Tunnel Goons level-up)
   returns the `Fact` it built and the caller tells it. `core/facts.py`: `Rolled.trace: str`
   replaces `Rolled.fact`; `WAY_OFFERED`, `SCENE_LEFT`, `MOVES_OFFSCREEN` become strings told
   with `told=True`; `Loner3eWorld.strike` returns the loser's name and the effect lines, so
   `_absorbed` and its slice go. `turn/run.py` `Turn.apply`: `world = self.engine.world_of(
   candidate); world.facts.clear(); play(...); facts = tuple(world.facts)`. `Engine.land`
   clears the list after `validate` (a save round-trips to `[]`, so the live state must too).
   `Engine.answer` returns `None`. Traces do not change: the turn goldens hold. Tests that read a
   return value read `world.facts`; `tests/support/table.py` `change` absorbs most of it.
   Measured: `src` +25, `tests` +46.
3. **No family layer.** `engines/rooms/` is one engine's: `rooms/world.py` becomes
   `tunnelgoons/map.py` (`Dungeon` stays as the map shape `MapProposal` and `attach` need, with
   `npcs: dict[Slug, Npc]` and no parameter; `Dweller`, `Prop`, `Place`, `Way` beside it),
   `rooms/worldsmith.py` folds into `tunnelgoons/worldsmith.py`, `rooms/tools.py` into
   `tunnelgoons/tools.py`, `rooms/engine.py` into `tunnelgoons/engine.py` (its tool methods,
   `new_game`, `author`, `act`, `extend`, `write_next`, `install`, and the three view builders as
   plain methods). `rooms/rules.md` is appended to `tunnelgoons/rules.md`, `rooms/worldsmith.md`
   moves to `tunnelgoons/`; `Engine.family_dir` goes and `__init__` reads one `rules.md`.
   `engines/scenes/` keeps `world.py` (`SceneWorld`, `SceneProposal`, `NextProposal`,
   `merged_cast`), `worldsmith.py`, `tools.py`, and gains `views.py`: `scene_sections(world)`,
   `here_sections(world, rules)`, `scene_panels(world)`, each a piece, so that each scene
   engine's `master_sections` and `player_view` write their own tuple in the golden's order
   (24XX puts GEAR, THE JOB, THE SHIP between YOU PLAY FOR and HERE WITH THE PLAYER).
   `scenes/engine.py` goes: `next_scene`, `enter`, `leave`, `meanwhile`, `new_game`, `author`,
   `act`, `write_next`, `install`, `narrator_view`, `over` become methods on `Loner3eEngine` and
   `TwentyfourxxEngine`, a copy each; `SceneEngine.sheet_sections` and `panels` are not needed
   and go. `scenes/rules.md` and `scenes/worldsmith.md` are appended to each scene engine's own.
   The prompt goldens hold (same text, one file). `tests/support/fifth.py` and `sixth.py` go:
   the room tests in `tests/engines/test_rooms.py` run on Tunnel Goons; `test_scenes.py`,
   `test_seam.py` and `test_scene_bar.py` parametrize over the two scene engines through
   `support/table.py`; the tempo-floor test subclasses `TunnelGoonsWorld`.
4. **One class per thing.** `engines/base.py` keeps `Gauge`, `Thing` (`id`, `name`, `brief`,
   `known`, `tag`, `mention`, `headline`, `subject`, `fact`, `card_line`, `rows`, `line`) and
   `Person` (`alive`, `chattiness`, `changed_tags`). `Sheet`, `Sheeted`, `Person.hired`,
   `hireable`, `required`, `carried`, the `_player_carries_a_sheet` validator go. Tunnel Goons:
   `Goon(Person)` with `hp`, `abilities`, `inventory`, `level`, `kit`; `Npc(Person)` with
   `place`, `hp`, `abilities: AbilityScores | None`, `inventory`, `level`; `hired` is
   `self.abilities is not None` on `Npc`; the level-up method is `gain_level` (`level` is the
   field); `level_decision`, `rows`, `sign_on`, `required` are their own methods, a copy each
   where both need one. This flattens the saved `sheet`: `characters/kael/tunnelgoons.json` and
   `tests/core/fixtures/schemas/tunnelgoons/worldsmith_answer.json` are rewritten, and the
   step says so in `PROGRESS.md`. 24XX: `Crewmate(Person)` with `sheet: CrewSheet | None`
   written out (`CrewSheet` is a real thing: gear, skills, credits, hindrances), `require_sheet`,
   `hired`, `carried`, `required` its own; its file and golden do not move. Loner:
   `Loner3eCast(Person)` spells `required` itself. Inherited fields are not redeclared.
   `rooms/worldsmith.py`'s `required_unmet` reads `required()` on the engine's class.
   Measured on Tunnel Goons alone: `src` +60 before the base shrinks by about 75.
5. **One type parameter, on containers only.** `Engine[W: World]`, `Game[W]`, `World[P:
   Person]` (`player: P`), `SceneWorld[C: Person](World[C])`, `SceneProposal[C]`,
   `NextProposal[C]`; `Scenario[P]` and `Character[P]` stay (pydantic validates the payload by
   them). `M` and `K` leave `Engine`; `Engine.member`, `Engine.game` go; `MasterTool`, `PackSet`,
   `check_map`, `check_extension`, `check_scene` lose theirs. `PackSet.srd(model)` and
   `chosen(selection, model)` carry one `isinstance` between them; each engine's `__init__`
   keeps `self.srd = self.packs.srd(TwentyfourxxPack)` once, typed. `Engine.player_of(
   character) -> P` is abstract; each engine's is three lines with one `isinstance` on
   `character.payload`, the one runtime check. `Engine.world_of(state: Game[W]) -> W` is
   `state.payload`, concrete. `AnyEngine` becomes `Engine[Any]`, `AnyGame` stays `Game[Any]`:
   the licensed bound. `TunnelGoonsGame = Game[TunnelGoonsWorld]` and the other two aliases
   stay. `tests/` and `qa/` follow the renamed parameters. No golden moves. The prototype that
   went to zero parameters cost +451 lines and four renamed accessors (`playing()` for
   `player`, `entries()` for `cast`) to dodge `reportIncompatibleVariableOverride`; that is why
   this step keeps one.
6. **A tool is a decorated method.** `core/tools.py`: `TOOL_DESCRIPTIONS: dict[Callable[...,
   None], str]`; `def tool(description: str)` records the function in it and returns it
   unchanged; `def tools_of(engine) -> dict[str, MasterTool]` walks `reversed(type(engine).
   __mro__)` and each class's `vars()` in order, so the base's tools come first and an override
   keeps the base's slot, binds each name with `getattr(engine, name)`, reads the args model
   from the third parameter's annotation, and refuses a parameter the model reads without a
   description (the check `master_tool` did). An undecorated override in a subclass is bound
   too, since binding is by name. `master_tool`, `Engine.master_tools` and its overrides, and
   the `*_TOOL` constants go: each description sits in the decorator at its method, the
   lambdas become two-line methods, `Engine.tool(name)` becomes `Engine.require_tool(name)` so
   the decorator's name is free inside the class body. Definition order is now the published
   order: `Loner3eEngine.spend_luck` moves below `roll`, `TwentyfourxxEngine.take_lead` sits
   between `spend` and `ship_upgrade`, `hire` right after `leave_party`; the three
   `master_tools.json` goldens and the master prompt hold. `tests/core/test_tools.py` tests
   `tools_of` (order, override, missing description); `tests/turn/test_decisions.py` builds its
   ad-hoc tools as a small decorated class. Measured: `src` −56, `tests` +33.
7. **Plain words, and the docs.** `engines/seam.py` → `engines/engine.py`; `Generation` →
   `WorldsmithJob`; `Engine.land` → `Engine.check_and_commit`. Saved field names do not change.
   CLAUDE.md, replacing the `Any` rule: "Do not use `Any`. The one exception: `Game[Any]`,
   `Engine[Any]`, `Scenario[Any]`, `Character[Any]` where the app holds every engine at once."
   CLAUDE.md, replacing the engine tool rule: "A tool is a method decorated with `@tool`; it
   resolves ids and rolls dice, and the world method it calls changes fields and tells the
   facts." README.md and `docs/24XX.md`, `docs/LONER-3E.md`: the sentences naming
   `SceneEngine` and the seam say that each engine is its own package and the two scene engines
   share `engines/scenes/`.

Done when: the full check is green; `grep -rn "master_tool\|-> list\[Fact\]\|-> tuple\[Fact\|Sheeted\|family_dir\|SceneEngine\|RoomEngine\|hireable" src tests qa` finds nothing; `src/aidm/engines/rooms/` and `scenes/engine.py` are gone; every `class` under `src/aidm` names at most one type parameter; the counts and the two rewritten files are in `PROGRESS.md`.
