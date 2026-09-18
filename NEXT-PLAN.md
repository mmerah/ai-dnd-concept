# NEXT-PLAN: human code

Done after `PLAN.md`. The target: `src/aidm/engines` reads like code one person wrote. One class
per thing, its fields written out. One place per tool. A world that writes its own facts. A type
parameter only on a container that holds the engine's own kind of thing. A family is shared
functions and a world shape, not a base class with hooks: every engine has the same files and
reads top to bottom.

This plan adds lines. Every step was prototyped on `3ebf53f` with the four checks green; the sum
is about **+250 `src`, +250 `tests`**. Prompts, goldens and saves do not change.

Symbol names are as of `PLAN.md` phase 3 done. One phase, seven steps, in this order, each one
green on the full check before the next (`uv run pytest`, `uv run ruff check`, `uv run ruff
format --check`, `uv run basedpyright`, `UV_CACHE_DIR` unset). Two rules beyond CLAUDE.md:

- No `# type: ignore`, no `cast`. A step that cannot type without one stops and says so in
  `PROGRESS.md`.
- A copy is fine. Two engines each carrying ten plain lines beat one base carrying a hook, a
  flag or a renamed accessor to share them.

1. **A family is shared code, not a base class.** `engines/rooms/` and `engines/scenes/` each
   keep `world.py`, `worldsmith.py`, `tools.py`, `rules.md`, `worldsmith.md` and gain `views.py`;
   each loses `engine.py`. `rooms/views.py`: `room_sections(world)`, `room_panels(world)`,
   `room_narrator_view(world)`; `scenes/views.py`: `scene_sections(world)`, `here_sections(
   world, rules)`, `scene_panels(world)`, `scene_narrator_view(world)`; pieces each engine's
   `master_sections`, `player_view` and `narrator_view` place in its own tuple, in the golden's
   order (24XX puts GEAR, THE JOB, THE SHIP between YOU PLAY FOR and HERE WITH THE PLAYER);
   `SceneEngine.sheet_sections` and `panels` go. What `RoomEngine` held becomes methods on
   `TunnelGoonsEngine`: the tool methods (`master_tools` returns `(*super().master_tools(),
   hire, move_item, unlock_way, move, meanwhile, rest, roll, level_up)` once step 3 lands
   `hire`), `new_game`, `author`, `act`, `extend`, `write_next`, `install`, `family_sections`,
   and the three views. What `SceneEngine` held becomes methods on `Loner3eEngine` and
   `TwentyfourxxEngine`, a copy each: `next_scene`, `enter`, `leave`, `meanwhile`, `new_game`,
   `author`, `act`, `write_next`, `install`, `family_sections`, `narrator_view`, `over`. A
   next room engine copies Tunnel Goons' methods the way 24XX copied Loner's. `Engine.family_dir`
   stays: the family's `rules.md` and `worldsmith.md` are read as today; the prompt goldens hold.
   Tests: `tests/support/fifth.py` and `sixth.py` go. `tests/support/tunnelgoons.py` gains
   `keep()` building the sixth keep's map (the locked yard→well way, the lantern in the yard)
   with `Npc(hp=...)` directly and no `begin`, so `tests/engines/test_rooms.py` (19 tests) keeps
   its ids and counts; its three construction tests subclass `TunnelGoonsEngine` with
   `directory = tmp_path` over `install_engine_dir`. `test_seam.py` (7 tests) and
   `test_packs.py` (1) run on the shipped engines through `support/table.py`;
   `test_a_fifth_scene_engine_begins_a_playable_game` goes; `test_a_game_with_no_chapter_open_
   is_refused` uses `game(LONER3E)`; `test_scene_bar.py`'s `AnySceneEngine` alias becomes
   `Loner3eEngine | TwentyfourxxEngine`.
2. **A world writes its own facts.** `engines/base.py`: `World.facts: list[Fact] = Field(
   default_factory=list, exclude=True)` and `World.tell(fact: Fact) -> None`. `Thing.fact` stays
   the one builder of a fact about a thing (`told=self.known` lives there and nowhere else).
   Every method under `src/aidm/engines` that returned `list[Fact]` or `tuple[Fact, ...]`
   (about 70) tells and returns `None`. A method that wrote facts from an entity becomes a
   world method taking the entity: `Thing.change` → `World.change(thing, gauge, amount, label,
   why)`, `Thing.reveal` → `World.reveal(thing, *, card="")`, `Loner3eCast.change_tags`,
   `drive`, `refill`, `spend_luck`, `lose`, `recover` → `Loner3eWorld.*(actor, ...)`,
   `Crewmate.change_hindrances`, `gain_item`, `repair_item`, `spend`, `hinder`, `raise_skill`,
   `earn`, `CrewSheet.drop_item` → `TwentyfourxxWorld.*(actor, ...)`, `Adventurer.level` →
   `TunnelGoonsWorld.gain_level(actor, ability, boost)`. `core/facts.py`: `Rolled.trace: str`
   replaces `Rolled.fact` (`tests/core/test_dice.py` follows). `WAY_OFFERED`, `SCENE_LEFT`,
   `MOVES_OFFSCREEN` become strings told with `told=True`. `Loner3eWorld.strike` tells its
   facts cardless and returns the loser's name and the card lines; the oracle fact is told
   after them, so the master's tool result lists the exchange before the oracle line, which is
   accepted (`tests/loner3e/test_tools.py` pins the lines inside the card, not the order).
   `turn/run.py` `Turn.apply`: `world = self.engine.world_of(candidate); world.facts.clear();
   play(candidate, dice); facts = tuple(world.facts); self.draft = self.engine.land(candidate)`.
   `Engine.land` clears the list after `validate` (a save round-trips to `[]`, so the live
   state must too). `Engine.answer` returns `None`; `Written` keeps only `telling`; `app/
   runtime.py` `_grow` clears before `advance` and snapshots `engine.world_of(draft).facts`
   before `close`. Traces do not change: the turn goldens hold. Tests that read a return value
   read `world.facts`; `tests/support/table.py` `change` clears the list before its call (some
   tests call it twice on one draft).
3. **The hire flow belongs to the engines that hire.** `Engine.hires`, `Engine.hire`,
   `Engine.write_hire`, `Engine.write_sheet`, `Engine.worldsmith_requests`, `Request`,
   `Written`, `Engine.requests` go. `Engine.unwritten: dict[Slug, Fact]` names the fact filed
   when a request fails (`EXTEND`, `DEPARTURE`, `COMPLICATION`, `HIRE`, each engine its own);
   `Engine.validate` checks `request.operation in self.unwritten`; `Engine.advance(draft,
   request, worldsmith) -> str | None` is abstract and each engine's is one `match
   request.operation` returning the telling. `TunnelGoonsEngine` and `TwentyfourxxEngine` each
   carry `hire`, `write_hire` and their own `HIRE_TOOL`, `Hire`, `SIGNED_ON`, `HIRE_UNWRITTEN`
   in their `tools.py`; Loner has none, and `tests/engines/test_scenes.py`'s refusal of a `hire`
   generation on Loner holds through `unwritten`. `World.require_hireable` and the `hired`
   branch of `World.require_actor` move to those two worlds. `app/runtime.py` `_grow` reads
   `engine.unwritten[request.operation]` on a refusal. `tests/core/test_golden_turn.py` iterates
   `engine.unwritten`; `tests/app/test_game_service.py` overrides `advance -> str | None`;
   `tests/engines/test_hire_tool.py` takes `SIGNED_ON` from each case's engine.
4. **One class per thing.** `engines/base.py` keeps `Gauge`, `Thing` (`id`, `name`, `brief`,
   `known`, `tag`, `mention`, `headline`, `subject`, `fact`, `card_line`, `rows`, `line`) and
   `Person` (`alive`, `chattiness`, `changed_tags`, `required` returning `"alive"` or `""`, which
   `required_unmet` reads for every engine). `Sheet`, `Sheeted`, `Person.hired`, `hireable`,
   `carried`, the `_player_carries_a_sheet` validator go. Tunnel Goons: `Goon(Person)` with
   `hp`, `sheet: GoonSheet`, `kit`; `Npc(Dweller)` with `hp`, `sheet: GoonSheet | None`
   (description "Leave empty."); `GoonSheet` (`abilities`, `inventory`, `level`) stays as it is;
   `hired` is `self.sheet is not None` on `Npc`; `Npc.required` adds "no sheet" over
   `super().required()`, so the worldsmith writes no hired npc; `require_sheet`,
   `level_decision`, `rows`, `sign_on` are their own methods, a copy each where both need one.
   The saved shape does not change: no character file or golden moves. 24XX: `Crewmate(Person)` with `sheet: CrewSheet | None`
   written out (`CrewSheet` is a real thing: gear, skills, credits, hindrances), `require_sheet`,
   `hired`, `carried`, `required` its own; its file and golden do not move. Loner:
   `Loner3eCast(Person)` keeps `required` over `super()`. Inherited fields are not redeclared.
5. **Type parameters on containers only.** `Engine[W: World[Any, Any]]`, `Game[W]`,
   `World[P: Person, M: Person]` stays as it is (the `player` and member types have no other
   spelling under `reportIncompatibleVariableOverride`), `SceneWorld[C]`, `SceneProposal[C]`,
   `NextProposal[C]`, `Dungeon[N]`, `RoomWorld[P, N]`, `MapProposal[N]`, `RegionProposal[N]`,
   `Scenario[P]`, `Character[P]` stay. `M` and `K` leave `Engine`;
   `Engine.member` and `Engine.game` go, `restore` and `begin` parse `Game[self.world]`;
   `MasterTool`, `PackSet`, `check_map`, `check_extension`, `check_scene` lose their parameters.
   `PackSet.srd(model)` and `chosen(selection, model)` carry one `isinstance` between them;
   each engine's `__init__` keeps `self.srd = self.packs.srd(TwentyfourxxPack)` once, typed.
   `Engine.player_of(character) -> Person` is abstract; each engine narrows the return with one
   `isinstance` on `character.payload`, the one runtime check. `Engine.world_of(state: Game[W])
   -> W` is `state.payload`, concrete. `AnyEngine` becomes `Engine[Any]`; `AnyGame` stays. The
   `TunnelGoonsGame = Game[TunnelGoonsWorld]` aliases stay. `tests/` and `qa/` follow. No golden
   moves.
6. **A tool is a decorated method.** `core/tools.py`: `TOOL_DESCRIPTIONS: dict[Callable[...,
   None], str]`; `def tool(description: str)` records the function in it and returns it
   unchanged; `def tools_of(engine) -> dict[str, MasterTool]` walks `reversed(type(engine).
   __mro__)` and each class's `vars()` in order, so the base's tools come first and an override
   keeps the base's slot, binds each name with `getattr(engine, name)` (an undecorated override
   such as `TwentyfourxxEngine.kill` is bound too), reads the args model from the third
   parameter of `inspect.signature` (`isinstance(annotation, type) and issubclass(annotation,
   BaseModel)`), and refuses a parameter the model reads without a description. `master_tool`,
   `Engine.master_tools` and its overrides, and the `*_TOOL` constants go: each description
   sits in the decorator at its method, the lambdas become two-line methods, `Engine.tool(name)`
   becomes `Engine.require_tool(name)` so the decorator's name is free inside the class body.
   Definition order is now the published order: `Loner3eEngine.spend_luck` moves below `roll`,
   `TwentyfourxxEngine.take_lead` sits between `spend` and `ship_upgrade`, `hire` right after
   `leave_party`; the three `master_tools.json` goldens and the master prompt hold.
   `tests/core/test_tools.py` tests `tools_of` (order, override, missing description);
   `tests/turn/test_decisions.py` builds its ad-hoc tools as a small decorated class.
7. **Plain words, and the docs.** `engines/seam.py` → `engines/engine.py`; `Generation` →
   `WorldsmithJob`; `Engine.land` → `Engine.check_and_commit`. Saved field names do not change. CLAUDE.md, replacing the
   `Any` rule: "Do not use `Any`. The one exception: `Game[Any]`, `Engine[Any]`, `World[Any,
   Any]`, `Scenario[Any]`, `Character[Any]` where the app holds every engine at once or a class
   is generic on the game state." CLAUDE.md, replacing the engine tool rule: "A tool is a
   method decorated with `@tool`; it resolves ids and rolls dice, and the world method it calls
   changes fields and tells the facts." README.md, `docs/24XX.md`, `docs/LONER-3E.md`: the
   sentences naming `SceneEngine` and the seam say that each engine is its own package and
   each family under `engines/` is
   shared functions and a world shape with no engine class of its own.

Accepted and left as is: `RoomWorld`'s two validators and its `entity()`/`require()` unions over
`Person | Prop | Place`; the `rows(carried=...)` keyword; the pack `head`/`body`
authoring split and `opening_sections`.

Done when: the full check is green; `grep -rn "master_tool\|-> list\[Fact\]\|-> tuple\[Fact\|Sheeted\|SceneEngine\|RoomEngine\|hireable\|Written\|Request\b" src tests qa` finds nothing; `engines/rooms/engine.py` and `engines/scenes/engine.py` are gone and the two family
directories hold the same five files and a `views.py`; the counts are in `PROGRESS.md`.
