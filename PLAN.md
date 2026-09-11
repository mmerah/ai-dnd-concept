# PLAN: one tool per change, then the seven accepted simplifications, in three commits

This plan lands one tool per change (every arm of `change_world` becomes a master tool of its own, and the families and `Hiring` register the tools whose methods they own), then the seven accepted proposals from the second round of reads: one way to refuse a model answer (a bar raises `Refusal`), one request table on the seam, the pure worldsmith renderers hoisted once, the same engine code written once, the scene log on `Game.log` in core, the palettes and dice looks in one `ui/theme.py` table, and the edge and test cuts of bundle 10 as amended: `media.scene_ratio`, `media.icon_ratio` and `media.max_references` become constants, `RoleConfig.api`, `RoleSettings.each()` and `ROLE_NAMES` go, `Roles` loses the engine, the four wiring tests go, the test helpers collapse to one settings builder and one service builder, and the small deletions land.
Not built: proposal 5 (the page's own action stays: `act`, `offered`, `MOVE_ON` and `MORE_MAP` are not touched), proposal 8 (live settings reload stays), proposal 9 (session resume stays), item 10.4 (`Engine.begin` keeps its three validations), `speech.voices` and `speech.sample_rate` stay settings, and nothing from the appendix of feature cuts. Proposal 4.5 is built as phase 1, in the one-tool-per-change shape the maintainer chose; its old reason not to, that the schema goldens would reorder, is waived.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each is one action on the files it names. Every `file.py:line` anchor is as of `d384d69`; where an earlier step moved the code, find the named symbol and ignore the number, and where an earlier phase moved a block to another file, the step names the new file.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
3. Count lines at the start and end of each phase and write both in `PROGRESS.md`, one entry per phase. At the start `src` is 9,994 lines, `tests` 9,321 and `qa` 1,792:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   ```
   If a phase runs half again past its target, stop and say so. Never pad.
4. Golden files live in `tests/core/fixtures/`. Rebuild them only where a phase says so:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed fixture line against the phase's "Done when". Any other change is a bug.
5. One commit per phase, full check green, reviewed adversarially against the staged diff first. Before the commit, run `uv sync --all-groups --locked` once and then the four commands on the staged tree: CI runs exactly that, and `ruff format --check` also formats the Python fences in this file, so `uv run ruff format PLAN.md` after editing it. Leave the game playable at the end of every phase: `uv run aidm`, open each shipped scenario, take a turn.
6. Delete, do not preserve. No compatibility path reads an old save or scenario file. No constant, helper, prompt line or test stays for a caller that is gone.
7. The standing limits hold. Imports flow `core <- engines <- turn <- app <- ui` with no cycles. No `Any` beyond the `Game[P]` bound. Every `__init__.py` stays empty. Tests never start a process and stub roles with `ScriptedSpawner`. `Refusal` stays the one message-bearing exception and any other exception is a bug. A bad model answer is re-prompted once with the error, then raises. Only code changes state or rolls dice. The narrator reads revealed facts only. Data is validated at each boundary with strict Pydantic models. Names must explain themselves and a comment is one line, only where the reason is not visible in the code.

## Phase 1: one tool per change

### Steps

1. `engines/seam.py:166-167`: `master_tools` is concrete and empty, moved beside `pack_options` at `:57`:
   ```python
   def master_tools(self) -> tuple[MasterTool[G], ...]:
       """Each layer adds its own after `super()`'s: the family's, then `hire`, then the engine's."""
       return ()
   ```
   This is the mechanism for the family's tools: one chain through `super()` on `master_tools()` itself. `SceneEngine`, `RoomEngine`, `Hiring` and each engine return `(*super().master_tools(), ...)`, so an engine lists only its own tools after the family's and `hire`. No new hook, no concatenation in `__init__`, and no MRO trap: every link calls `super()` and the root returns nothing, so for `master_tools` `Hiring` may sit anywhere in the bases (Breathless resolves `BreathlessEngine -> Hiring -> SceneEngine -> Engine`, so its tools come out family, `hire`, own); `advance` still wants it first until phase 2 step 7 removes that rule. A `family_tools()` hook would spend the hook and a concatenation line for the same order, and `__init__` registration, the pattern the request table uses in phase 2, would land after the doubled-name check at `seam.py:52-54`, which now has something to catch.
2. `engines/base.py`: delete `CHANGE_WORLD` at `:15-18` and `ChangeWorld` at `:205-206`; `JoinParty` and `LeaveParty` at `:191-202` lose their docstring and `verb`, the sentence moving beside `PLAYER_ID`:
   ```python
   JOIN_PARTY = "A character here starts travelling with the player."
   LEAVE_PARTY = "A party member stops travelling with the player."
   ```
   This is the convention for every change tool: its description is the sentence its arm's docstring carried, as a constant beside the args class (`REVEAL`, `KILL`, `GAIN_ITEM`), and the class loses the docstring so the schema does not say it twice. The guidance `CHANGE_WORLD` gave, call it once the story has settled a change, is already `master.md:19`, so `master.md` does not change. `Thing.reveal`'s docstring at `:73` ends "or the standalone `reveal` tool." `core/tools.py:15`: `NOISE_KEYS` drops `"discriminator"`: nothing emits one once the unions are gone (`Job.verb` is a plain `Literal`). `tests/app/test_master_tools.py:42-66`: `_ArmA`, `_ArmB`, the `change` field, the `'"discriminator"'` assert and the `Literal` import at `:7` go; the probe keeps `actor_id` and `title`.
3. `engines/scenes/tools.py`: `Reveal`, `Enter`, `Leave`, `Kill` at `:15-40` lose docstring and `verb`; delete `SharedChange` at `:54` and the `Literal` import; `:6` keeps `Person` alone; add beside `NEXT_SCENE`:
   ```python
   REVEAL = "A hidden entity here becomes known to the player."
   ENTER = "A cast member comes into the scene."
   LEAVE = "A cast member goes out of the scene."
   KILL = "Someone here dies."
   ```
   `engines/scenes/engine.py`: delete `shared_change` at `:176-190`; after `player_view` add the family's tools and six two-line methods:
   ```python
   def master_tools(self) -> tuple[MasterTool[G], ...]:
       return (
           *super().master_tools(),
           master_tool("reveal", REVEAL, Reveal, self.reveal),
           master_tool("enter", ENTER, Enter, self.enter),
           master_tool("leave", LEAVE, Leave, self.leave),
           master_tool("kill", KILL, Kill, self.kill),
           master_tool("join_party", JOIN_PARTY, JoinParty, self.join_party),
           master_tool("leave_party", LEAVE_PARTY, LeaveParty, self.leave_party),
           master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
       )


   def reveal(self, draft: G, args: Reveal, _rng: Random) -> list[Fact]:
       return self.world(draft).reveal_hidden(args.entity_id)
   ```
   `enter`, `leave`, `kill`, `join_party` and `leave_party` are the same line over `world.enter`, `world.leave`, `world.kill`, `world.join_party`, `world.leave_party`. `next_scene` is the family's method at `:192`, so its registration leaves the three scene engines with it. Delete the comment at `:97` ("last: `master_tools` reads the packs"): nothing in any `master_tools` reads them. Imports: `SharedChange` goes from `:43`; `ENTER, KILL, LEAVE, NEXT_SCENE, REVEAL` join it; `JOIN_PARTY, LEAVE_PARTY` join the `aidm.engines.base` block; `MasterTool, master_tool` from `aidm.core.tools`. `tests/engines/test_seam.py:56-57`: delete `FifthEngine.master_tools` and the `MasterTool` import at `:12`; add `test_a_scene_engine_offers_the_familys_tools_without_naming_them`: `list(_installed(tmp_path).tools) == ["reveal", "enter", "leave", "kill", "join_party", "leave_party", "next_scene"]`.
4. `engines/rooms/tools.py`: `Reveal`, `MoveItem`, `Kill`, `UnlockWay` at `:9-43` lose docstring and `verb`; delete `SharedChange` at `:46`, the `Literal` import and the `aidm.engines.base` import at `:6` whole; add at the top `REVEAL`, `MOVE_ITEM`, `KILL`, `UNLOCK_WAY` from the four docstrings and `MOVE` from `tunnelgoons/engine.py:97` ("Call this to carry the player through an unlocked way out of this place."). `engines/rooms/engine.py`: delete `shared_change` at `:178-191`; after `player_view` add `master_tools` in the shape of step 3 over `reveal`, `move_item`, `kill`, `join_party`, `leave_party`, `unlock_way`, `move`, and the six methods, `kill` being `world.kill(world.require_member_here(args.entity_id))` and `move_item` `world.move_item(args.item_id, args.to)`; `move` at `:193` stays. Imports as in step 3; the `aidm.engines.rooms.tools` line at `:34` explodes to one name per line. `tests/engines/test_rooms.py`: delete `ChangeWorld` at `:45`, `master_tools` and `change_world` at `:60-64`, and `Annotated`, `Discriminator`, `Fact`, `base`, `CHANGE_WORLD`, `MasterTool`, `master_tool`, `SharedChange` from the imports; the docstring at `:49` ends "its state model and its creation; the tools are the family's"; `test_join_party_and_leave_party_land_through_change_world` at `:174` becomes `test_the_familys_tools_are_offered_in_order` and first asserts `list(engine.tools) == ["reveal", "move_item", "kill", "join_party", "leave_party", "unlock_way", "move"]`.
5. `engines/hiring.py`: `Hiring` registers `hire`, after the `hire` method at `:57`:
   ```python
   def master_tools(self) -> tuple[MasterTool[G], ...]:
       return (*super().master_tools(), master_tool("hire", HIRE_TOOL, Hire, self.hire))
   ```
   `from aidm.core.tools import MasterTool, master_tool` joins the imports after `aidm.core.model`. Delete the three `master_tool("hire", HIRE_TOOL, Hire, self.hire)` lines at `breathless/engine.py:116`, `twentyfourxx/engine.py:114`, `tunnelgoons/engine.py:115` and `HIRE_TOOL`, `Hire` from their `aidm.engines.hiring` imports. `DropItem` is written once here, after `Hire`, from `breathless/tools.py:13-18` without docstring and `verb`, both field descriptions byte for byte, with `DROP_ITEM = "The actor loses an item for good."` beside `HIRE_TOOL`; the copy at `twentyfourxx/tools.py:44-49` goes in step 8. `drop_item` is not a `Hiring` tool: Tunnel Goons mixes `Hiring` in and carries no backpack (its items are the room's props, moved by `move_item`), so the two backpack engines register it in steps 7 and 8, and phase 2 step 9 no longer moves the class.
6. `engines/loner3e/tools.py`: `ChangeTags`, `Drive`, `RestoreLuck` at `:27-61` lose docstring and `verb`; delete `WorldChange` and `ChangeWorld` at `:64-69`, `from aidm.engines import base` at `:8`, the `scenes.tools` import at `:11`, `Annotated` and `Discriminator`; `:9` keeps `Attempt` alone; add `CHANGE_TAGS`, `DRIVE`, `RESTORE_LUCK` beside `TOLD`; `defeat_note` at `:133` says "with `change_tags`, as a `condition`". `engines/loner3e/engine.py`: `master_tools` at `:63-74` returns `(*super().master_tools(), change_tags, drive, restore_luck, roll)`; `change_world` at `:172-190` becomes three methods:
   ```python
   def change_tags(self, draft: Loner3eGame, args: ChangeTags, _rng: Random) -> list[Fact]:
       actor = draft.payload.require_here(args.entity_id, alive=True)
       return actor.change_tags(args.kind, args.gained, args.lost)


   def drive(self, draft: Loner3eGame, args: Drive, _rng: Random) -> list[Fact]:
       actor = draft.payload.require_here(args.entity_id, alive=True)
       return actor.drive(goal=args.goal, motive=args.motive, nemesis=args.nemesis)


   def restore_luck(self, draft: Loner3eGame, args: RestoreLuck, _rng: Random) -> list[Fact]:
       actor = draft.payload.require_here(args.entity_id, alive=True)
       facts = actor.reveal()
       # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
       facts.extend(actor.refill("the conflict is behind them"))
       return facts
   ```
   Imports: `CHANGE_WORLD` at `:12`, `ChangeWorld` at `:15` and the `scenes.tools` line at `:36` go; the three constants join `:13`.
7. `engines/breathless/tools.py`: `ChangeStress`, `UseMedKit` at `:21-36` lose docstring and `verb`; delete `WorldChange` and `ChangeWorld` at `:39-44`, `from aidm.engines import base` at `:6`, the `scenes.tools` import at `:10`, `Annotated`, `Literal` and `Discriminator`; `:7` keeps `Attempt` alone; add `CHANGE_STRESS`, `USE_MED_KIT` at the top. `engines/breathless/engine.py`: `master_tools` at `:84-117` returns `(*super().master_tools(), drop_item, change_stress, use_med_kit, roll, catch_breath, loot_check, test_luck)`; `change_world` at `:191-201` becomes three one-line methods, `drop_item` being `return draft.payload.require_actor(args.actor_id).drop_item(args.item_id)`, `change_stress` and `use_med_kit` the same over `.change_stress(args.amount, args.why)` and `.use_med_kit()`; the note at `:298` reads "Death is `kill` on {who.name}." Imports: `CHANGE_WORLD`, `ChangeWorld`, `DropItem` and the `scenes.tools` line at `:48` go; `CHANGE_STRESS, USE_MED_KIT` join the `breathless.tools` block; `DROP_ITEM, DropItem` come from `aidm.engines.hiring`.
8. `engines/twentyfourxx/tools.py`: the seven classes at `:12-94` lose docstring and `verb`; delete `DropItem` at `:44-49`, `WorldChange` and `ChangeWorld` at `:97-115`, `from aidm.engines import base` at `:6`, the `scenes.tools` import at `:9`, `Annotated` and `Discriminator` (`Literal` stays for `Job.verb`); `:7` keeps `Attempt` alone; add `CHANGE_HINDRANCES`, `GAIN_ITEM`, `REPAIR_ITEM`, `SPEND`, `TAKE_LEAD`, `SHIP_UPGRADE`, `DEFEND` at the top. `engines/twentyfourxx/engine.py`: `master_tools` at `:87-115` returns `(*super().master_tools(), change_hindrances, gain_item, drop_item, repair_item, spend, take_lead, ship_upgrade, defend, roll, test_luck, job)`; delete `apply_change` at `:256-280` and `change_world` at `:282-285`; each arm is a method in the shape of step 7 over `require_actor(args.actor_id)` (`repair_item` keeps its `require_gear` line; `take_lead`, `ship_upgrade` and `defend` call the world), and the family's `kill` is overridden for the one death the option must follow:
   ```python
   def kill(self, draft: TwentyfourxxGame, args: Kill, _rng: Random) -> list[Fact]:
       facts = super().kill(draft, args, _rng)
       self._succession(draft)
       return facts
   ```
   This changes behaviour: today `_succession` runs after every `change_world` arm; after this step only `kill` and `roll` run it, which is harmless because they are the two tools that can kill the lead and `Turn.call` blocks further tools once `pending` is set. `_succession` at `:287-306`: the docstring reads "`kill` and `roll` are the two tools that can kill the lead."; the option replays flat, `name="take_lead"` and `args={"entity_id": member.id}`. Imports: `CHANGE_WORLD`, `ChangeWorld`, `DropItem`, `WorldChange` go; the seven constants join `:19`; `Kill` replaces `NEXT_SCENE, NextScene` at `:17`; `DROP_ITEM, DropItem` come from `aidm.engines.hiring`. Tests: `test_answering_the_succession_decision_makes_the_member_the_player` at `tests/twentyfourxx/test_tools.py:409-416` already replays the option through `answer` and stays; add `test_kill_on_the_lead_with_a_hired_member_opens_the_succession` beside `:389`: `draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()`, `change(ENGINE, draft, "kill", entity_id=PLAYER_ID)`, then `draft.pending is not None and draft.pending.kind == "succession"` and `ENGINE.over(draft) is None`.
9. `engines/tunnelgoons/tools.py`: delete `Rest` at `:14-17` (a class with no fields is the schema `Frozen` already is), `WorldChange` and `ChangeWorld` at `:20-23`, `from aidm.engines import base` at `:7`, the `rooms.tools` import at `:10`, `Annotated`, `Literal` and `Discriminator`; `:8` keeps `Attempt` alone; add `REST = "The player and the party spend a night here and heal to full Health."`. `engines/tunnelgoons/engine.py`: `master_tools` at `:92-116` returns `(*super().master_tools(), master_tool("rest", REST, Frozen, self.rest), roll, level_up)`; `change_world` at `:161-167` becomes `rest(self, draft, _args: Frozen, _rng)` returning `draft.payload.rest()`. Imports: `CHANGE_WORLD`, `ChangeWorld`, `Rest`, the `rooms.tools` line at `:15` go; `REST` joins the `tunnelgoons.tools` block; `Frozen` joins `:6`.
10. `engines/seam.py:70-83`: delete `tool()`; `answer` looks the tool up itself:
    ```python
    def answer(self, draft: G, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = self.tools.get(chosen.name)
        if found is None:
            raise Refusal(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)
    ```
    `turn/run.py:109` becomes `found = self.engine.tools.get(name)` followed by `if found is None: raise Refusal(f"{name!r} is not a tool of the {self.engine.id!r} engine.")`; `tests/app/test_builtin.py:37,156` pin that text and stay.
11. `tests/support/table.py:75-91`: delete `change_args` and `changed` (flat, `changed` is `tool_call`); `change` plays a tool by name:
    ```python
    def change(engine: AnyEngine, draft: AnyGame, name: str, **args: JsonValue) -> list[Fact]:
        return list(engine.tools[name].call(draft, args, Random(0)))
    ```
    and `refused` keeps its shape over `name`. Every `changed(` is `tool_call(` and the import follows: `tests/support/golden_turn.py:3,13`, `tests/loner3e/golden_turn.py:2,11`, `tests/breathless/golden_turn.py:1,8,10`, `tests/twentyfourxx/golden_turn.py:1,8-11`, `tests/tunnelgoons/golden_turn.py:1,16`, `tests/turn/test_turn.py:8,21-22,74,129-130,139,151-152,304`, `tests/tunnelgoons/test_play.py:5,74,76,112`, `tests/app/test_game_service.py:12,267`; `tests/loner3e/test_world.py:16-21` keep their two wrappers with the parameter named `name`. `tests/app/test_master_tools.py:13` drops `change_args`; `:138-139` become `table.call("reveal", {"entity_id": VAULT_MAP, "junk": 1})` and `table.call("reveal", {"entity_id": VAULT_MAP})`; `:165,218,409` become `tool_call("reveal", entity_id=VAULT_MAP)` and `tool_call("enter", entity_id="tomas")`; `:127` calls `"reveal"`. `tests/app/test_builtin.py:21` is `CHANGE_TAGS = ENGINES_BUILT[LONER3E].tools["change_tags"]` and every `CHANGE_WORLD` name (`:33,36,38,132,133`) follows; `:104-110` the flat dict is the arguments; `:113-114,126,131,143-144,163,219,222` say `change_tags`. `tests/app/test_mcp.py:18-21`: `REVEAL_VAULT_MAP = {"name": "reveal", "arguments": {"entity_id": "vault-map"}}`; `:101,106` say `reveal`. `tests/twentyfourxx/test_tools.py:184` becomes `test_spend_with_actor_id_pays_from_the_member_credits`. `qa/agents.py:5,119-120`: the `!change` clause and the `case "change":` go, a change is the plain `case _`; `qa/README.md:32` row goes; `qa/s_loner.py:63,105,235,335` spell `!reveal entity_id=vault-map`, `!change_tags entity_id=player ...`, `!drive entity_id=player ...`, `!kill entity_id=player`.
12. Prompts and docs name tools, not arms. `engines/scenes/rules.md:17` "no other tool can bring", `:32` "Call `join_party` when someone here comes along. Call `leave_party`"; `engines/rooms/rules.md:5` "until `unlock_way` opens", `:13` as scenes `:32`; `engines/loner3e/rules.md:16` "Call `change_tags` when ... Call `drive`", `:26` "Call `kill` or the fitting tool instead.", `:27` "and `enter` or `leave` after.", `:58` "now with `change_tags`.", `:61` "Call `restore_luck` after", `:73` "Call `change_tags` for ... Call `drive` for a"; `engines/breathless/rules.md:34` "Call `change_stress` for", `:35` "Call `use_med_kit` to spend", `:36` "no other tool spends it.", `:49` "and on `change_stress`, `use_med_kit` and `drop_item`."; `engines/twentyfourxx/rules.md:29` "Call `gain_item` to add ... Call `drop_item` to lose one", `:30` "Call `repair_item` to mend ... Call `spend` for everything else", `:35` "Call `defend` when", `:40` "Call `change_hindrances` when", `:47` "on `defend` or `repair_item`.", `:48` "Call `ship_upgrade` to upgrade", `:53` "Call `spend` to pay ₡1", `:69` "wherever a tool offers"; `engines/tunnelgoons/rules.md:30` "Call `reveal` only for ... Call `kill` for a death", `:40` "`unlock_way`, which also makes", `:48` "Call `rest` for a night", `:56` "`rest` heals them with the party." Every line only gets shorter, so no wrap moves. `docs/24XX.md:38`, `docs/BREATHLESS.md:28`, `docs/LONER-3E.md:54`, `docs/TUNNEL-GOONS.md:46` become "Every tool makes one change, rolls dice, opens a decision, or ends the turn."; the `- \`change_world\` — arms:` bullet at `24XX.md:40-44`, `BREATHLESS.md:30-32`, `LONER-3E.md:56-58`, `TUNNEL-GOONS.md:48` opens "- `reveal`, `enter`, `leave`, `kill`, `join_party`, `leave_party`," (rooms: "`reveal`, `move_item`, `kill`, `join_party`, `leave_party`, `unlock_way`") with the rest of its text as it is, "The sheet arms take `actor_id`" reading "The sheet tools take `actor_id`".
13. Regenerate the goldens (How to work §4) and read the diff: the four `tests/core/fixtures/schemas/*/master_tools.json` are rewritten whole, one entry per tool in family, `hire`, engine order (loner3e 11 tools, breathless 15, twentyfourxx 19, tunnelgoons 11), each change tool's `parameters` a flat object with no `$defs`, `oneOf`, `verb` or `discriminator`; `tests/core/fixtures/prompts/*/master.txt` differ on exactly the lines step 12's `rules.md` edits land on: `breathless/master.txt:60-62,75,94,109`, `loner3e/master.txt:42,52-53,84,87,99,123,138`, `tunnelgoons/master.txt:56,66,74,82,88,96`, `twentyfourxx/master.txt:55-56,61,66,73-74,79,95,120,135`. `narrator.txt`, `worldsmith.txt`, `interjection.txt` and the four `turn/*.json` are byte-identical: the traces never named the tool.

### Done when

- `grep -rnI "change_world\|ChangeWorld\|WorldChange\|SharedChange\|shared_change\|CHANGE_WORLD\|Discriminator\|discriminator\|verb: Literal\|change_args\|def tool(" src tests qa docs` prints only `Job.verb` at `engines/twentyfourxx/tools.py`; `grep -rn "\barm\b\|arms\b" src/aidm/engines/*/rules.md src/aidm/turn/prompts/master.md docs/*.md` prints nothing.
- `grep -rn "def master_tools" src` prints `seam.py`, `scenes/engine.py`, `rooms/engine.py`, `hiring.py` and the four engines, and every body but the seam's spreads `super().master_tools()` first. `list(engine.tools)` for each built engine is the family's seven, then `hire` where mixed in, then its own; `tests/engines/test_seam.py` and `tests/engines/test_rooms.py` each pin one family's order on an engine that names no tool.
- The `take_lead` succession option replays through `answer` with flat args, and `kill` on the lead with a hired member alive opens the same decision `roll` does (`test_kill_on_the_lead_with_a_hired_member_opens_the_succession`).
- The schema goldens and the `master.txt` goldens regenerate as step 13 says; anything else under `tests/core/fixtures/` is a bug.
- `src` is about 9,920 lines, at most 9,940: 9,994 plus step 1 (+3), step 2 (−12), step 3 (+14: the scene family's constants and flat classes save 12, its tool table, six methods and imports cost 26), step 4 (+24: the same for rooms, and the `rooms.tools` import explodes to twelve lines), step 5 (0: `Hiring.master_tools`, `DropItem` and `DROP_ITEM` cost what the three `hire` lines and the Breathless copy save), step 6 (−18), step 7 (−28), step 8 (−16: the 24XX union, the seven docstrings and `verb` lines, the doubled `DropItem`, `apply_change` and `change_world` were about 80 lines; the constants, the eleven methods, the `kill` override and the larger tool table are about 65), step 9 (−33), step 10 (−5), steps 11-13 (0). `tests` is about 9,300: the three new tests cost what the probe arms, the sixth engine's tool and the three helpers save. `qa` is 1,790.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn in which the master lands one change tool. Saves keep their shape; a save from before this phase restores as before, except a 24XX save holding an open succession decision, whose options name `change_world` and are refused at `answer`.

## Phase 2: one bar, one request table, one renderer, shared engine code

### Steps

1. `core/model.py:22-23`: a bar raises, it does not return.
   ```python
   # What `ask` asks of the value it parsed, beyond its own schema; it raises the reason to re-prompt.
   type Objection[T] = Callable[[T], None]
   ```
   `app/spawn.py:189-206`: `ask` runs the bar inside the one `try`, so a raised refusal is re-prompted like a parse failure:
   ```python
   async def ask[T: BaseModel](
       spawner: Spawner, role: Role, prompt: str, model: type[T], refusal: Objection[T]
   ) -> T:
       asked, refused, session = prompt, "", None
       for _ in range(RETRIES + 1):
           spoken = await spawner.run(role, asked, session)
           session = spoken.session
           try:
               answer = parse(model, decode(spoken.text))
               refusal(answer)
           except Refusal as invalid:
               refused = str(invalid)
           else:
               return answer
           correction = f"Your last answer was refused: {refused}\nAnswer again, fixed."
           # The retry carries on the refused attempt, which has read the prompt already.
           asked = correction if session is not None else f"{prompt}\n\n{correction}"
       raise Refusal(f"the {role} answered nothing usable: {refused}")
   ```
   `tests/app/test_spawn.py:96` passes `lambda _: None` already and stays. `tests/support/table.py:147` (`stub_worldsmith`) ignores the bar and stays.
2. `core/views.py:101-124`: the three narrator bars raise. `speakers_refusal` becomes `check_speakers(self, lines: Sequence[Line]) -> None` and raises `Refusal` with the same text where it returned it; `narration_refusal` becomes `check_narration(self, narration: Narration) -> None`, raising the "write the narration lines" text and then calling `self.check_speakers(narration.lines)`; `interjection_refusal` becomes `check_interjection(self, member_id: Slug, answer: Interjection) -> None` raising the two texts it returned. `app/roles.py:95` passes `view.check_narration`; `:116` passes `partial(view.check_interjection, member.id)`. `tests/engines/test_views.py:145-150`: the accepted call is a bare `view.check_interjection(member_id, accepted)`; the two refusals become `with pytest.raises(Refusal, match=...)` on the same texts.
3. `engines/scenes/worldsmith.py:32-37`: `scene_refusal` becomes `check_scene(draft, world=None) -> None`:
   ```python
   def check_scene[C: Person](draft: SceneDraft[C], world: SceneWorld[C] | None = None) -> None:
       """Free: the drafts may not import the world, and the authoring call has no world."""
       if unmet := scene_unmet(draft, world):
           raise Refusal("the scene needs " + "; ".join(unmet))
   ```
   `engines/rooms/worldsmith.py:23-30`: `map_refusal` becomes `check_map(draft) -> None` and `extension_refusal` becomes `check_extension(draft, world) -> None`, each raising its "the map needs" / "the extension needs" text. Call sites: `engines/scenes/engine.py:115-116` becomes `check_scene(draft)`; `:275` becomes `lambda answer: check_scene(answer, world)`; `engines/rooms/engine.py:67-68` becomes `check_map(draft)`; `:227` becomes `lambda answer: check_extension(answer, world)`; the two `build_scenario` bars at `scenes/engine.py:261-262` and `rooms/engine.py:237-238` call `check_scene(draft)` / `check_map(draft)` until step 8 deletes them. Fix the imports at `scenes/engine.py:46-52`, `rooms/engine.py:36`. Tests: `tests/engines/test_scene_bar.py:62,68-79` type `bar` as `Callable[[Mapping[str, object]], None]` calling `check_scene`, and the five bar tests at `:117-152` become `with pytest.raises(Refusal, match=...)` on `"put there by code"`, `"rewrites the player"`, `"already met"`, `"may write them"`, `"does not name what is hidden"`; `tests/twentyfourxx/test_worldsmith.py:101-148` call `check_scene` bare where they asserted `is None` and `pytest.raises(Refusal, match=...)` where they compared text (`"is filed under"`, the overlap, `"these name nobody"`, `"a sheet"`, the two party texts); `tests/engines/test_scenes.py:136` and `tests/loner3e/test_world.py:111` call `check_scene(...)` bare; `tests/tunnelgoons/test_worldsmith.py:60,75,84` call `check_map` / `check_extension` bare, `:116-118` becomes `pytest.raises(Refusal, match="not already in the world")`.
4. `engines/twentyfourxx/worldsmith.py:84-101`: `SheetDraft.refusal(pack)` becomes `check(self, pack: Pack) -> None`, the last line `if problems: raise Refusal("; ".join(problems))`. `engines/twentyfourxx/engine.py:323-325`: `hire_bar` returns `lambda sheet: sheet.check(pack)`. `engines/hiring.py:82-83`: `hire_bar` keeps its shape, now typed `Objection[A]` that raises. PROPOSALS 4.1 says `hire_bar` folds into `install_sheet` as a raise; that would run the bar after `ask` returned and lose the one re-prompt a sheet off the pack gets, so `hire_bar` stays and only the `hireable` hook goes (step 10). `tests/twentyfourxx/test_worldsmith.py:13-32`: the two accepted drafts call `draft.check(SRD)` bare; the two refused become `pytest.raises(Refusal, match="Wizard")` and `match="Sorcery"`.
5. `engines/seam.py:85-101`: `compose` is one call; `playable` raises:
   ```python
   async def compose[M: BaseModel](
       self,
       worldsmith: WorldsmithAnswer,
       prompt: str,
       model: type[M],
       build: Callable[[M], AnyScenario],
       playable: Callable[[AnyScenario], None],
   ) -> AnyScenario:
       return build(await worldsmith(prompt, model, lambda answer: playable(build(answer))))
   ```
   The abstract `author` at `:189` and both implementations (`scenes/engine.py:293`, `rooms/engine.py:154`) take `playable: Callable[[AnyScenario], None]`. `app/runtime.py:383-387`: the closure loses its `try`:
   ```python
   def playable(built: AnyScenario) -> None:
       engine.begin(name, built, character)
   ```
   `tests/app/test_master_tools.py:283-302`: the `answer` stub types `refusal: Objection[M]`, calls `refusal(answer)` and returns; `playable` becomes `lambda built: table.service.engine.begin("t", built, table.service.character)` since the bar now runs in `begin` alone (step 8); the assertion is `pytest.raises(Refusal, match="the scene needs")`. `tests/tunnelgoons/test_worldsmith.py:160,177,189` may keep `Callable[[M], str | None]` (a bar returning `None` satisfies it) but spell `Objection[M]` for one name.
6. `engines/seam.py`: the request table. Add after `AnyEngine` at `:28`:
   ```python
   @dataclass(frozen=True, slots=True)
   class Request[G: Game[Any]]:
       """What a failed write tells the player, and the write itself."""

       unwritten: Fact
       write: Callable[
           [G, Generation, WorldsmithAnswer], Awaitable[tuple[tuple[Fact, ...], str | None]]
       ]
   ```
   Replace `unwritten: dict[Slug, Fact]` at `:45` with `requests: dict[Slug, Request[G]]`; `__init__` at `:47-55` sets `self.requests = self.worldsmith_requests()` after `self.tools`; `validate` at `:163` reads `self.requests`; the abstract `advance` at `:195-199` becomes concrete:
   ```python
   async def advance(
       self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
   ) -> tuple[tuple[Fact, ...], str | None]:
       """Write and install on `draft`; the facts, and what to tell the narrator, if anything."""
       return await self.requests[request.operation].write(draft, request, worldsmith)


   def worldsmith_requests(self) -> dict[Slug, Request[G]]:
       return {}
   ```
   `app/runtime.py:226` reads `self.engine.requests[request.operation].unwritten`. `tests/core/test_golden_turn.py:66` reads `next(iter(engine.requests))`.
7. Register per family. `engines/scenes/engine.py`: delete `unwritten` at `:92`; split `advance` at `:302-314` into two writes and register them:
   ```python
   def worldsmith_requests(self) -> dict[Slug, Request[G]]:
       return {
           DEPARTURE: Request(WAY_UNWRITTEN, self.depart),
           COMPLICATION: Request(COMPLICATION_UNWRITTEN, self.complicate),
       }


   async def depart(
       self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
   ) -> tuple[tuple[Fact, ...], str | None]:
       left = self.world(draft).run.title
       scene = await self.write_next(draft, request.brief, worldsmith)
       # The engine's own closing reads the scene being left, so it runs before the install.
       facts = (*self.leaving(draft), *self.install(draft, scene))
       return facts, CROSSING.format(left=left, pursuit=request.brief)


   async def complicate(
       self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
   ) -> tuple[tuple[Fact, ...], str | None]:
       scene = await self.write_next(draft, COMPLICATING.format(brief=request.brief), worldsmith)
       return tuple(self.install(draft, scene)), TURNING
   ```
   `engines/rooms/engine.py`: delete `unwritten` at `:55`; `advance` at `:169-176` becomes `extend` without the `ValueError` guard (the seam's table is the guard) and `worldsmith_requests` returns `{EXTEND: Request(MAP_UNWRITTEN, self.extend)}`. `engines/hiring.py`: delete the docstring sentence "List it first in the bases." at `:53`; `advance` at `:66-80` becomes `write_hire` without the `super()` branch, and `Hiring.__init__` registers it after the family's own:
   ```python
   def __init__(self) -> None:
       super().__init__()
       self.requests[HIRE] = Request(HIRE_UNWRITTEN, self.write_hire)
   ```
   Delete the four `unwritten = {...}` lines at `breathless/engine.py:82`, `twentyfourxx/engine.py:85`, `tunnelgoons/engine.py:90` and the `HIRE` and `HIRE_UNWRITTEN` names from their imports (`breathless:46`, `twentyfourxx:15`, `tunnelgoons:13`): `HIRE` had no other use in those files. Delete `test_advance_raises_on_an_operation_the_engine_does_not_write` at `tests/tunnelgoons/test_worldsmith.py:187-197`: it tested the guard that is gone, and `validate` at `tests/engines/test_scenes.py:166-172` already proves an unknown operation is refused at land.
8. `engines/seam.py`: hoist the pure renderers. Add `worldsmith_prompt: Path` beside `family_prompt` at `:39` and, after `compose`:
   ```python
   def render_request(self, draft: G, *, intent: str, guidance: str, answer: type[BaseModel]) -> str:
       world = self.world(draft)
       return render_worldsmith(
           role=read_prompt(self.worldsmith_prompt),
           source=world.source,
           scope=draft.scenario.scope,
           family=self.family_sections(draft),
           intent=intent,
           guidance=guidance,
           answer=answer,
       )


   def render_opening(
       self, source: str, scope: str, *, intent: str, guidance: str, answer: type[BaseModel]
   ) -> str:
       return render_worldsmith(
           role=read_prompt(self.worldsmith_prompt),
           source=source,
           scope=scope,
           family=self.family_sections(None),
           intent=intent,
           guidance=guidance,
           answer=answer,
       )


   def build_scenario(
       self, meta: ScenarioMeta, packs: tuple[Slug, ...], draft: BaseModel, source: str, premise: str
   ) -> AnyScenario:
       """No bar: `begin` is the one bar an opening meets, and `playable` always runs it."""
       return self.scenario(
           meta=meta.with_premise(premise), engine=self.id, packs=packs, source=source, payload=draft
       )


   @abstractmethod
   def family_sections(self, draft: G | None) -> Pairs: ...
   ```
   `engines/scenes/engine.py`: `worldsmith_prompt = WORLDSMITH_PROMPT` beside `family_prompt` at `:93`; delete `render_request` at `:222-234`, `render_opening` at `:247-256`, `build_scenario` at `:258-269`; add `family_sections(self, draft)` returning `scene_sections(None if draft is None else self.world(draft))`; `author` at `:287-300` calls `self.build_scenario(meta, tuple(packs), draft, source, draft.situation)` and `self.render_opening(source, meta.scope, intent=OPENING, guidance=guidance, answer=SceneDraft[self.cast])`. `engines/rooms/engine.py`: `worldsmith_prompt = WORLDSMITH_PROMPT` at `:56`; delete `render_opening` at `:196-205`, `render_request` at `:207-219`, `build_scenario` at `:234-245`; add `family_sections` returning `map_sections(...)` the same way; `author` at `:148-160` reads the premise without the bar:
   ```python
   def built(draft: MapDraft[N]) -> AnyScenario:
       start = draft.places.get(draft.start)
       premise = "" if start is None else start.description
       return self.build_scenario(meta, tuple(packs), draft, source, premise)
   ```
   and calls `self.render_opening(source, meta.scope, intent=MAP_ASK, guidance=self.guidance(), answer=self.map_draft())`. The three `hire_prompt` callers (`breathless:208`, `twentyfourxx:316`, `tunnelgoons:173`) and `render_next` at `scenes:243` already use the keyword form and stay. Imports: `read_prompt`, `render_worldsmith` and `BaseModel` become unused in `scenes/engine.py:7,12,31` and `rooms/engine.py:7,11,31` and go; `seam.py` imports `render_worldsmith` from `aidm.engines.base` beside `PLAYER_ID` and `read_prompt` is already there. Tests: `tests/twentyfourxx/test_worldsmith.py:53-56` passes `draft.situation` as the premise; `tests/tunnelgoons/test_worldsmith.py:62-64` passes `"d"`; `test_the_opening_refuses_a_present_name_that_exists_nowhere` at `tests/twentyfourxx/test_worldsmith.py:119-121` stays on `check_scene(draft)` (the bar, not the builder); `tests/app/test_launcher.py:238-260` still sees `"these name nobody"` in the re-prompt because `playable` runs `begin`.
9. `engines/base.py`: `ItemSheet` moves here from `engines/hiring.py:29-41`, after `Sheeted`, bound on an `Item` that carries the `name` it prints (`BaseModel` has none, and `Supply` at `engines/breathless/world.py:32-34` and `Gear` at `engines/twentyfourxx/world.py:41-42` share no base), and drops an item on behalf of its owner:
   ```python
   class Item(Mutable):
       name: str


   class ItemSheet[I: Item](Mutable):
       items: dict[Slug, I] = Field(default_factory=dict)

       def require(self, item_id: Slug, owner: str) -> I:
           item = self.items.get(item_id)
           if item is None:
               raise Refusal(f"{item_id!r} is not among {owner}'s items")
           return item

       def drop(self, item_id: Slug, owner: str) -> I:
           item = self.require(item_id, owner)
           del self.items[item_id]
           return item

       def drop_item(self, item_id: Slug, owner: Thing) -> list[Fact]:
           item = self.drop(item_id, owner.name)
           return [owner.fact(f"{owner.mention} drops {item.name}", card=f"Dropped {item.name}")]
   ```
   Delete `Survivor.drop_item` at `engines/breathless/world.py:110-113`, `Crewmate.drop_item` at `engines/twentyfourxx/world.py:137-140` and the unused `Crewmate.require_item` at `:98-99`; repoint the `ItemSheet` imports at `breathless/world.py:12` and `twentyfourxx/world.py:11` to `aidm.engines.base` and make `Supply(Item)` at `breathless/world.py:32` and `Gear(Item)` at `twentyfourxx/world.py:41`, importing `Item` beside it. The two `drop_item` tool methods (phase 1 steps 7 and 8, `engines/breathless/engine.py` and `engines/twentyfourxx/engine.py`) become `actor = draft.payload.require_actor(args.actor_id)` then `return actor.dice().drop_item(args.item_id, actor)`. `DropItem` already lives once in `engines/hiring.py` (phase 1 step 5), so nothing moves. `tests/breathless/test_tools.py:160-165,256-259` still pass through `change`.
10. `engines/hiring.py`: delete the abstract `hireable` at `:85-86` and its three bodies at `breathless/engine.py:203-204`, `twentyfourxx/engine.py:312-313`, `tunnelgoons/engine.py:169-170`. `Hiring` gains `member: type[M]` beside `hire_answer` and one narrow that `hire` and `write_hire` both call:
    ```python
    def hireable(self, draft: G, entity_id: Slug) -> M:
        member = self.world(draft).require_hireable(entity_id)
        if not isinstance(member, self.member):
            raise ValueError(f"{member.id!r} is not a {self.member.__name__}")
        return member
    ```
    The `ValueError` is a bug, never a refusal: the world already files only `M`. Each engine sets `member = Survivor` / `Crewmate` / `Npc` beside `hire_answer`. Phase 1 left `hireable` as it was, so this stands.
11. `engines/hiring.py:71`: inline `Generation.require_target` and delete it from `core/model.py:93-96`:
    ```python
    if request.target is None:
        raise Refusal(f"a {request.operation!r} request names no target")
    member = self.hireable(draft, request.target)
    ```
12. `core/facts.py:57-65`: `keep_highest` becomes `roll_pool`, which highlights the kept die only when there was a choice:
    ```python
    def roll_pool(
        faces: Sequence[int], reason: str, rng: Random, *, label: str
    ) -> tuple[int, DiceEvent, Fact]:
        rolled, fact = roll(faces, reason, rng)
        kept = max(rolled)
        highlight = (rolled.index(kept),) if len(faces) > 1 else ()
        event = DiceEvent(label=label, faces=tuple(faces), rolled=rolled, highlight=highlight)
        return kept, event, fact
    ```
    `engines/breathless/engine.py:257-265` becomes `pool = (die,) if helper is None else (die, helper[1])` and `face, event, dice_fact = roll_pool(pool, reason, rng, label="+".join(f"d{f}" for f in pool))`; `engines/twentyfourxx/engine.py:369-375` becomes the same two lines over its `pool`; `engines/loner3e/engine.py:296-299` calls `roll_pool` with its `"Chance"` and `"Risk"` labels. Drop `DiceEvent` from the imports at `breathless:8` and `twentyfourxx:8` where the hand-built event was the only use (Breathless still builds one in `loot_check`, 24XX in `_find` and `_finish`: keep those). `tests/core/test_dice.py:21-26` becomes `test_roll_pool_highlights_the_kept_die_only_in_a_pool`: the three-die case keeps `highlight == (0,)` and a one-die `roll_pool((6,), ...)` has `highlight == ()`. Regenerate the goldens: `tests/core/fixtures/turn/loner3e.json` changes on one event only, the single-die `Risk` event's `highlight` from `[0]` to `[]` (PROPOSALS assumed no drift; Loner's risk die was highlighted alone). The other three `turn/*.json` and every prompt fixture are unchanged.
13. `engines/base.py`: the luck test, after `banded`:
    ```python
    def luck_test(question: str, die: int, bands: tuple[str, str, str], rng: Random) -> list[Fact]:
        """A question about the world when nobody acts: the dice trace, the answer is never told."""
        rolled, dice_fact = roll((die,), question, rng)
        result = banded(rolled[0], *bands)
        return [dice_fact, Fact(trace=f"{question} — d{die} [{rolled[0]}] -> {result}")]
    ```
    `engines/breathless/engine.py:362-366` returns `luck_test(args.question, args.die, ("fail", "success-but", "success"), rng)`; `engines/twentyfourxx/engine.py:402-407` returns `luck_test(args.question, 6, ("trouble now", "signs of it", "nothing"), rng)`. `tests/breathless/test_tools.py:232-239` and `tests/twentyfourxx/test_tools.py:125-130` stay green as they are.
14. `engines/loner3e/world.py:52-60`: `forbidden` builds on `super()` like `Sheeted.forbidden` at `engines/base.py:116-118`:
    ```python
    def forbidden(self) -> str:
        parts = (super().forbidden(), "full luck" if self.luck.current != LUCK_MAX else "")
        return ", ".join(part for part in parts if part)
    ```
15. `core/prompt.py`: `sentence` moves here from `engines/scenes/world.py:276-277`, after `lines_of`. `engines/scenes/world.py:184` imports it from `aidm.core.prompt` beside `lines_of`; `engines/breathless/engine.py:49` and `engines/twentyfourxx/engine.py:18` drop their `from aidm.engines.scenes.world import sentence` and add `sentence` to their `aidm.core.prompt` import.

### Done when

- `grep -rn "str | None" src/aidm/core/views.py src/aidm/engines/*/worldsmith.py` prints nothing; `grep -rn "def [a-z_]*_refusal\|\.refusal(" src tests` prints only `busy_refusal`, `play_refusal` and `_refusal_text`. A refused sheet, scene, map or narration is re-prompted once through `ask` and then raises `Refusal`.
- `grep -rn "unwritten =\|def advance\|require_target\|List it first\|def hireable(self, draft\|keep_highest" src` prints `Engine.advance` once, `Hiring.hireable` once and nothing else; `grep -rn "def drop_item\|def sentence" src` prints `engines/base.py` once and `core/prompt.py` once. `Engine.requests` is the one table; `tests/tunnelgoons/test_worldsmith.py` no longer names `departure`.
- `grep -rn "def render_request\|def render_opening\|def build_scenario" src` prints `engines/seam.py` three times and nothing else. `tests/core/fixtures/prompts/*/worldsmith.txt` do not change.
- `tests/core/fixtures/schemas/*/master_tools.json` do not change: `DropItem` keeps its descriptions and its place in each list. `name` is already the first field of `Supply` and `Gear`, so the `worldsmith.txt` schemas, which embed them through the cast's sheet, do not change either.
- One golden regenerates: `tests/core/fixtures/turn/loner3e.json`, the `Risk` event's `highlight` alone. Anything else in `tests/core/fixtures/` is a bug.
- `src` is about 9,880 lines, at most 9,895: 9,923 plus step 1 (0: the new `ask` has the body lines of the old), steps 2-5 (−17), steps 6-7 (+25: `Request`, three `worldsmith_requests`, `Hiring.__init__` and the split come to about 37 lines; the six `unwritten` lines, the if-chain, the guard and the `super()` branch were 11), step 8 (−25), step 9 (−2: `Item` and `ItemSheet.drop_item` cost seven, the two member methods and `require_item` were eleven, and the two tool methods gain a line each), steps 10-11 (−4), step 12 (−8), step 13 (−4), steps 14-15 (−7). `tests` is about 9,300: the raises cost what the deleted goons test saves.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn. Saves keep their shape and a save from before this phase restores as before.

## Phase 3: the log in core, the theme in ui, edge and test cuts

### Steps

1. `core/play.py:131-137`: `SceneRecord` becomes the chapter the game keeps:
   ```python
   class Chapter(Mutable):
       """One scene or place as the player read it; `recap` is empty until the scene closes."""

       title: str
       focus: str
       recap: str = ""
       exchanges: list[Exchange] = Field(default_factory=list)
   ```
   `core/prompt.py:3,20,27,37,48` type `Chapter`. `core/model.py:99-108`: `Game` gains `log: list[Chapter] = Field(default_factory=list)` after `notes` and the one read every layer above the engines uses:
   ```python
   def exchanges(self) -> tuple[Exchange, ...]:
       return tuple(exchange for chapter in self.log for exchange in chapter.exchanges)
   ```
   `tests/core/test_prompt.py` and `tests/app/test_context_boundary.py:5,158` build `Chapter(...)` where they built `SceneRecord(...)`. `tests/engines/test_seam.py` gains `test_a_game_with_no_chapter_open_is_refused` beside `test_a_fifth_scene_engine_begins_a_playable_game`: `begin` the taproom, `state.log.clear()`, and `engine.validate(state)` raises `Refusal` matching `"no chapter open"`.
2. `engines/base.py:138-141,162-163`: delete the abstract `records`, `record` and `World.exchanges`; drop `SceneRecord` from the import at `:9`. `engines/seam.py`: `close` at `:121` becomes `draft.log[-1].exchanges.append(exchange)`; `begin` at `:150` opens the first chapter before landing: `self.open_chapter(state)` then `return self.land(state)`; `validate` at `:160-164` refuses a game with nothing to write on, before the request check, since `Game.log` defaults to `[]` and `close` or `move` on it would be an `IndexError`: `if not state.log: raise Refusal(f"a {self.id!r} game has no chapter open")`; add the one opener beside `close`:
   ```python
   def open_chapter(self, draft: G) -> None:
       """The title and focus the narrator sees are the ones the history keeps."""
       view = self.narrator_view(draft)
       draft.log.append(Chapter(title=view.title, focus=view.focus))
   ```
3. `engines/scenes/world.py`: delete `exchanges` and `recap` from `SceneRun` at `:45,47`, `record` and `records` at `:97-109`, the recap stamp at `:246-247` and the now unused `NextDraft` import at `:18` and `Exchange, SceneRecord` import at `:14`. `engines/scenes/engine.py:278-285`: `install` stamps the recap on the chapter being left and opens the next:
   ```python
   def install(self, draft: G, scene: SceneDraft[C]) -> list[Fact]:
       world = self.world(draft)
       if isinstance(scene, NextDraft):
           draft.log[-1].recap = scene.recap
       world.apply_scene(scene.model_copy(deep=True))
       self.open_chapter(draft)
       ...
   ```
   `engines/scenes/worldsmith.py:92-103`: `scene_sections(world, log: Sequence[Chapter] = ())` renders `render_history(log)`; `SceneEngine.family_sections` passes `draft.log`.
4. `engines/rooms/world.py`: delete `Visit` at `:34-36`, `visit` at `:160-162`, `record` and `records` at `:380-390`, the `Exchange, SceneRecord` import at `:8`. `visits: list[Slug] = Field(min_length=1)` at `:122`; `_playable` at `:128-129` walks `for place_id in self.visits: self.require_place(place_id)`; `begin` at `:151` files `"visits": [draft.start]`; `current` at `:158` reads `self.places[self.visits[-1]]`; `move` at `:245` appends `destination.id`; `map_so_far` at `:361-362` reads `seen.setdefault(place_id, self.require_place(place_id))`. `engines/rooms/engine.py:141` renders `trail_panel(world.require_place(place_id).name for place_id in world.visits)`; `move` at `:193-194` opens the chapter and keeps the old rule that a place walked through without a word is no scene:
   ```python
   def move(self, draft: G, args: Move, _rng: Random) -> list[Fact]:
       facts = self.world(draft).move(args.to_id, args.with_ids)
       if not draft.log[-1].exchanges:
           draft.log.pop()
       self.open_chapter(draft)
       return facts
   ```
   `engines/rooms/worldsmith.py:9-20`: `map_sections(world, log: Sequence[Chapter] = ())`; `RoomEngine.family_sections` passes `draft.log`.
5. Every reader above the engines reads the game. `app/runtime.py:94-97`: `unopened` is `not self.busy and not self.state.exchanges()`; `:243-244` and `:270-272` read `self.state.exchanges()`. `app/launch.py:111-118`: `turn=len(state.exchanges())`, `where=state.log[-1].title if state.log else ""`, and the `world` local goes. `app/roles.py:92` passes `scenes=draft.log`; `:107` reads `state.exchanges()`; `:113` passes `state.log`; `:125,141,162` type `Sequence[Chapter]` and the `SceneRecord` import at `:14` goes. `turn/run.py:100` passes `self.draft.log`; `:147` types `Sequence[Chapter]`; drop `SceneRecord` from `:15`.
6. Tests follow the log. `tests/breathless/golden_turn.py:18`, `tests/tunnelgoons/golden_turn.py:24`, `tests/twentyfourxx/golden_turn.py:19` append to `draft.log[0].exchanges`; `tests/loner3e/golden_turn.py:28-53` inserts the run without its `exchanges` and `draft.log.insert(0, Chapter(title="The Vault Stair", focus="Is there a way past the vault door from the stair?", exchanges=[...]))`, then sets `draft.log[-1].exchanges = [...]`. `tests/core/test_store.py:19` sets `draft.log[-1].exchanges` and `:39` compares `engine.restore(decode(reloaded)).exchanges() == saved.exchanges()`; `tests/tunnelgoons/test_engine.py:30` asserts `world.visits[0] == world.current.id`. `tests/app/test_master_tools.py:365-367` reads `state.log[-1].exchanges`. Every `engine.world(x).exchanges()` and `x.payload.exchanges()` becomes `x.exchanges()`: `tests/app/test_game_service.py:104,109,118,160,204,221,239,350,364,375,381,386`, `tests/app/test_master_tools.py:152,202,344,383,388,413,431,441,453`, `tests/app/test_mcp.py:107`, `tests/app/test_speech.py:160`, `tests/app/test_launcher.py:259`, `tests/engines/test_seam.py:166`, `tests/turn/test_turn.py:62,63,78,93,199,224,342`, `tests/turn/test_decisions.py:118,130,131,144`, `tests/breathless/test_play.py:46,58`, `tests/twentyfourxx/test_play.py:42,54`, `tests/tunnelgoons/test_play.py:92,101,119,123`; `tests/app/test_context_boundary.py:37` passes `state.log`; `tests/engines/test_scene_bar.py:180,190` count `draft.log`. The hand-built games open on a chapter: `tests/support/breathless.py:44-52`, `tests/support/twentyfourxx.py:35-43` and `tests/support/tunnelgoons.py:110-118` pass `log=[Chapter(title=..., focus=...)]` with their run's or start place's title and focus. Rooms tests drop `Visit`: `tests/support/tunnelgoons.py:4,109` (`visits=[START]`), `tests/tunnelgoons/test_world.py:5,46,57-58`, `tests/tunnelgoons/test_tools.py:23,213,249,258`, `tests/tunnelgoons/test_views.py:4,36` append the id; `tests/engines/test_rooms.py:19,130,251` compare `state.payload.visits == [GATE, YARD]` and pass `visits=[YARD]`. `test_a_visit_nothing_was_played_in_is_no_scene_in_the_records` at `tests/tunnelgoons/test_world.py:55-61` moves to `tests/tunnelgoons/test_tools.py` as `test_a_place_walked_through_without_a_word_is_no_chapter`: two `ENGINE.move` calls on a draft of `small_world()` leave `[chapter.title for chapter in draft.log] == ["Start"]`. `test_apply_scene_with_a_next_draft_stamps_the_recap_on_the_run_left` at `tests/engines/test_scenes.py:79-97` becomes `test_install_stamps_the_recap_on_the_chapter_left` through `ENGINE.install(draft, NextDraft[...](...))` on `initialized()` in `tests/loner3e/test_world.py`, asserting `draft.log[-2].recap == RECAP` and `draft.log[-1].recap == ""`; drop the unused `played` parameter and its `exchanges` line from `_run` at `tests/engines/test_scenes.py:28-37`.
7. Regenerate the goldens and diff: no fixture under `tests/core/fixtures/` changes. `RECENT PLAY`, `SCENES SO FAR` and `WHAT THE PLAYER HAS READ` render from `state.log` exactly as they rendered from `records()`; the turn and schema fixtures are untouched. A one-line drift anywhere is a bug in steps 2-4.
8. `ui/theme.py`: one table keyed by engine id. Move `DiceLook` from `core/views.py:48-53` to the top of `ui/theme.py` unchanged, delete `Palette` at `core/views.py:56` and define it here as `type Palette = Mapping[str, str]`; delete `_PALETTES` at `:28`, `seed` at `:360-361`, `_palette` at `:387-389`, `_palette_css` at `:392-399` and the `cast`, `Sequence` imports; add after `NEUTRAL_PALETTE`:
   ```python
   NEUTRAL_DICE = DiceLook(body="#232c33", ink="#eeeae0", glow="#dbc18b")


   @dataclass(frozen=True, slots=True)
   class Theme:
       palette: Palette
       dice: DiceLook


   # The one place the UI names an engine; an engine not listed here gets the neutral look.
   THEMES: dict[EngineId, Theme] = {
       EngineId("loner3e"): Theme(
           palette={...}, dice=DiceLook(body="#efe4c8", ink="#7a2e2e", glow="#c89b5a")
       ),
       EngineId("tunnelgoons"): Theme(...),
       EngineId("breathless"): Theme(...),
       EngineId("twentyfourxx"): Theme(...),
   }
   ```
   with the four palettes and dice looks copied byte for byte from `engines/loner3e/engine.py:43-56`, `engines/tunnelgoons/engine.py:71-82`, `engines/breathless/engine.py:61-73`, `engines/twentyfourxx/engine.py:64-76`. `set_engine` at `:370-384` writes the variables inline on `body`, no classes:
   ```python
   def set_engine(engine: EngineId | None) -> None:
       theme = THEMES.get(engine) if engine is not None else None
       palette = {**NEUTRAL_PALETTE, **(theme.palette if theme is not None else {})}
       ui.query("body").style("; ".join(f"--{key}: {value}" for key, value in palette.items()))
       ui.colors(
           primary=palette["game-accent"],
           secondary=palette["game-muted"],
           dark=palette["game-surface"],
           dark_page=palette["game-bg"],
           positive=palette["game-success"],
           negative=palette["game-danger"],
       )


   def dice_look(engine: EngineId) -> DiceLook:
       theme = THEMES.get(engine)
       return NEUTRAL_DICE if theme is None else theme.dice
   ```
   `_install` at `:419` adds `f"@layer overrides {{{_STATIC_CSS}}}"` alone, and `_declarations` at `:402-403` goes with the `:root` block it fed. `ui/dice.py:7` imports `DiceLook` from `aidm.ui.theme`; `ui/app.py:175` loses the `theme.seed(...)` line; `ui/game.py:180` builds `DiceTray(theme.dice_look(session.engine_id))` importing `theme` from `aidm.ui`; `tests/ui/test_game.py:134` the same.
9. Engines stop carrying colours. Delete `dice_look` and `palette` at `engines/loner3e/engine.py:43-56`, `engines/tunnelgoons/engine.py:71-82`, `engines/breathless/engine.py:61-73`, `engines/twentyfourxx/engine.py:64-76` and `DiceLook` from their `aidm.core.views` imports (`loner3e:11`, `tunnelgoons:11`, `breathless:13`, `twentyfourxx:13`); delete the two declared attributes at `engines/seam.py:36-37` and `DiceLook, Palette` from `:25`; delete `GameService.dice_look` at `app/runtime.py:90-92` and `DiceLook` from `:22`. `tests/core/test_package_boundary.py:110-119`: `test_no_ui_module_names_a_built_engine_id` asserts `naming == {"ui/theme.py"}` with the docstring "The theme table is the one place the UI names an engine id." Delete `tests/ui/test_theme.py` whole (item 10.5: it tested CSS class names on NiceGUI internals; the two colour asserts are the `ui.colors` wiring). Check by eye: `uv run aidm`, each scenario's drawer, menu and header take that engine's colours, the home page the scenario's, the settings page the neutral.
10. `config.py:49-52`: delete `scene_ratio`, `icon_ratio` and `max_references` from `MediaConfig`. `app/media.py` gains after `SUFFIXES`: `SCENE_RATIO = "16:9"`, `ICON_RATIO = "1:1"`, `MAX_REFERENCES = 4`, read at `:65`, `:70`, `:87`; `qa/art.py:28` compares `ratio == ICON_RATIO` and imports it. Three settings keys go, no line does.
11. `config.py`: delete `ROLE_NAMES` and its comment at `:18-19`, `RoleConfig.api` at `:36-42`, `RoleSettings.each` at `:83-84` and `get_args` from `:3`. `_keys_present` at `:127-138` walks the three roles by name:
    ```python
    for role, config in (
        ("master", self.roles.master),
        ("narrator", self.roles.narrator),
        ("worldsmith", self.roles.worldsmith),
    ):
        match config.provider:
            case "openrouter" | "local" as name:
                posting.append((role, name))
            case "claude" | "codex":
                pass
    ```
    Fix the comment at `:121` to "Not `PORT`, set by too many shells." once step 17 removes the two files it names. `tests/test_config.py:33-34` become `assert local.roles.master.provider == "local"`.
12. `app/roles.py:54-121`: `Roles` holds the spawner alone. Delete `engine: AnyEngine` at `:57` and `worldsmith` at `:120-121`; `narrate` becomes `narrate(self, engine: AnyEngine, draft, facts, prompt, *, fatal)` and `interject` becomes `interject(self, engine: AnyEngine, state, member)`, each reading `engine` where they read `self.engine`. `app/spawn.py` gains beside `ask`:
    ```python
    def worldsmith(spawner: Spawner) -> WorldsmithAnswer:
        return partial(ask, spawner, "worldsmith")
    ```
    `app/runtime.py`: `:106,146,183,218` pass `self.engine` first; `:213` passes `worldsmith(self.spawner)`; `:391` passes `worldsmith(self.spawner)`; `:416` builds `Roles(self.spawner)`. Tests: `tests/app/test_game_service.py:371,402` and `tests/app/test_master_tools.py:380-385` build `Roles(...)` with the spawner alone; `tests/support/game.py:84` goes with step 15.
13. Delete the wiring tests of item 10.5 not yet gone: `tests/app/test_mcp_lifespan.py` whole (`tests/app/test_mcp.py` runs the lifespan end to end), `test_an_aliased_literal_field_is_a_dropdown` at `tests/ui/test_settings.py:98-100`, `test_poll_turn_walks_the_player_view_and_history_once` at `tests/ui/test_game.py:171-198`. Drop the imports each leaves unused (`_widget` at `test_settings.py:16`, `GameService` and `Exchange` at `test_game.py:11,13` if nothing else uses them).
14. One settings builder. `tests/support/table.py:106-111`: `offline_settings(saves: Path | None = None, scenarios: Path = SCENARIOS) -> Settings` builds `EnvFileFreeSettings` with the `openrouter` provider keyed as `tests/support/ui.py:12-15` keys it (a fake key lets a test switch media or speech on), `scenarios_dir=scenarios`, `characters_dir=CHARACTERS`. Delete `tests/support/ui.py`. Every `ui_settings(...)` becomes `offline_settings(...)`, positional: `ui_settings(saves_dir=tmp_path)` at `tests/ui/test_settings.py:26,48,76,85` becomes `offline_settings(tmp_path)`, then `tests/app/test_media.py:126`, `tests/app/test_speech.py:129`, `tests/app/test_launcher.py:70,78,89,95,101,110,112,120,139,152,162,175,185,200,239,279,296`; `tests/app/test_launcher.py:18` imports `REPOSITORY_ROOT, SCENARIOS, offline_settings` from `support.table`. `tests/app/test_builtin.py:44` keeps its `provider="local"` roles and is unaffected by the key.
15. One service builder. `tests/support/game.py:76-87`: `session(directory)` becomes `return open_game(directory, rng=Random(1)).service`, dropping the `Roles`, `FileStore`, `ScriptedSpawner` imports and `TARGET` stays for the tests that name it. The eight callers at `tests/app/test_game_service.py:43,47,49,56,84,88,279` and `tests/app/test_speech.py:146` are unchanged.
16. `ui/settings.py`: no `Box`. Delete the protocol at `:18-20` and `Boxes` at `:13`; `SettingsForm.__init__` at `:24-27` takes `settings` and `apply` alone and holds `self.boxes: dict[tuple[str, ...], Widget] = {}` where `type Widget = ui.input | ui.switch | ui.select | ui.number` replaces `Boxes`; `_widget` at `:130` returns `Widget`. `changes` at `:61-74` becomes a free function `changes(settings: Settings, typed: Mapping[tuple[str, ...], object]) -> Changes` with the same body over `typed.items()`; `save` at `:77` calls `changes(self.settings, {path: box.value for path, box in self.boxes.items()})`; `settings_page` at `:104` builds `SettingsForm(settings, apply)`. `tests/ui/test_settings.py:20-50`: delete `FakeBox`; the two tests call `changes(settings, {("media", "enabled"): True, ...})` with the same expected dict.
17. Small deletions. `app/mcp.py:47-51`: delete `list_tools`; `on_list_tools` at `:73-77` builds the `types.Tool` list inline from `runtime.published_tools()`; `tests/app/test_master_tools.py:25,125` assert `table.runtime.published_tools() == ()`. `app/runtime.py:279-280`: delete `drain`; `tests/support/table.py` gains `async def drain(service: GameService) -> None: await gather(*service._background)  # pyright: ignore[reportPrivateUsage]` and `tests/core/test_golden_turn.py:39` and `tests/app/test_speech.py:162` call it. Delete `src/aidm/ui/__main__.py` (`uv run aidm` is the entry point, `pyproject.toml:17`). Delete `.mcp.json` and `.codex/config.toml` (the spawned CLIs take their MCP config from flags at `app/spawn.py:80,118`); `ui/settings.py:39-40` loses ", and .mcp.json must match it".

### Done when

- `grep -rn "SceneRecord\|\bVisit\b\|def records\|def record\b\|\.records()\|world(.*)\.exchanges()\|payload\.exchanges()" src tests qa` prints nothing. `Game.log` is the one history; `state.exchanges()` is the one read.
- A save written before this phase is skipped on the home screen with a warning (its `SceneRun.exchanges` or `Visit` key is an extra field); a new game saves `log` beside `payload` and restores through `engine.restore`.
- No golden regenerates in steps 1-7: every prompt fixture is byte-identical to the phase 2 commit.
- `grep -rn "dice_look\|palette\|DiceLook\|Palette" src` prints only `ui/theme.py`, `ui/dice.py` and `ui/game.py`; `grep -rn "game-theme-\|_PALETTES\|def seed" src` prints nothing. `THEMES` names the four engine ids and `test_no_ui_module_names_a_built_engine_id` allows `ui/theme.py` alone.
- `grep -rn "scene_ratio\|icon_ratio\|max_references\|ROLE_NAMES\|def each\|def api\|\blist_tools(\|def drain(self\|ui_settings\|FakeBox\|class Box\b" src tests qa` prints nothing; `ls .mcp.json .codex src/aidm/ui/__main__.py tests/support/ui.py tests/ui/test_theme.py tests/app/test_mcp_lifespan.py` finds none of them. `Roles(spawner)` is the only constructor; `worldsmith(spawner)` lives in `app/spawn.py`.
- `src` is about 9,815 lines, at most 9,840: 9,880 minus steps 1-5 (−30: the two `records()` projections, `Visit` and the three abstract methods go, `Chapter`, `Game.exchanges`, `open_chapter` and the two `validate` lines come), steps 8-9 (−18: the four palettes are thirteen lines each wherever they live, so the gain is the registry, `_palette_css`, the class juggling and the two core types), step 10 (0), step 11 (−5), step 12 (+2), step 16 (−4), step 17 (−9). `tests` is about 9,150: 9,300 minus step 13 (−129 with `test_theme.py`), step 14 (−17), step 15 (−10), step 16 (−11), plus step 2 (+5), step 6 (+7) and step 17 (+3). `qa` stays 1,790.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn; each shows its own colours and dice; the settings page saves a key and reloads live as before.
