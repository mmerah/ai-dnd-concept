# PLAN — the party, then the crew

Five phases, in order. **Phase 1** gives every engine the party: an NPC who joins the player,
follows them, and is read as the party by all three roles. **Phase 2** lets a party member speak
or propose a move after a turn, at the cost of one narrator spawn the player never waits on.
**Phase 3** gives 24XX a crew that rolls beside the player, hired through the worldsmith.
**Phase 4** gives 24XX succession and the ship. **Phase 5** gives Tunnel Goons goons who roll
and level. Self-standing: an implementer needs this file, `CLAUDE.md` and the code. Track G of
`NEXT-SPECS.md` (2026-09-02) is folded here and cut from that file.

What stays, everywhere: one turn is one player input on one draft behind the commit gate; only
code changes state or rolls dice; the narrator reads revealed facts only; the three roles, each
a cold spawn; every engine self-contained; scenarios and characters authored and stored on
their own. What is not built: an agent per NPC, a second human player, a crew store beside the
cast, a party cap, a summariser.

Saves have no version field. Phases 1 and 2 add defaulted fields, so saves still load. Phase 3
nests the 24XX sheet and Phase 5 nests the Tunnel Goons sheet, so those engines' saves and
character files from before go stale: the launcher skips a stale save with its warning, and the
shipped character files are rewritten by hand in the same phase. Nothing migrates.

## Decisions

1. **The party is one list in `World`**, `party: list[EntityId]`, moved up from `SceneWorld`;
   the room family gains the same list, and `move` carries it. A member is read under THE PARTY
   and never again under HERE WITH THE PLAYER or the `Here` panel: one entry, one place. Two
   arms, `join_party` and `leave_party`, in every engine, not counted against the tool cap.
2. **An agent per NPC is refused.** A member who "acts on their own" would change state outside
   a turn, which the transaction and the one-turn-in-flight rule forbid, or only talk, which is
   Phase 2. A spawn per member per turn costs what the summariser was refused for. The minimal
   form of the idea is Phase 2's proposal: the member says what they would do, and the player
   accepts it with one press or ignores it.
3. **An interjection is one narrator spawn, in the background, gated by chattiness.** Every
   `Person` carries `chattiness` (`quiet`, `normal`, `chatty`), authored by the worldsmith; after
   an eventful turn each member is rolled against it with the service's `Random`, and the first
   who passes speaks. Nothing spawns when nobody passes. It lands as an `Exchange` under its own
   mark, so every role reads it back through the history that exists, the chat draws it, and
   speech reads it. The model may answer with no lines, which records nothing. On by default;
   `Settings.interjections` turns it off.
4. **The worldsmith writes a hire.** `hire` is a request, as `next_scene`'s complication is: the
   master calls it, the turn ends, the worldsmith writes the sheet on a fresh draft, code checks
   it against the pack and installs it, and the narrator tells the signing-on. Who has dice is
   authored, never improvised by the master. The same in Tunnel Goons. `Generation` gains
   `target`, the entity a request concerns.
5. **The crew closes 24XX's deviations.** Ally rolls (`helped_by`), succession, the android
   case as a breakable item, and the ship with its seven functions all land; only the priced
   gear table stays untranscribed, and it is not a crew rule.
6. **Succession keeps ids.** The member who takes the lead keeps their own id as
   `world.player.id`; the dead lead goes into the cast under `player`. `PLAYER_ID` then names a
   character file's sheet and nothing in play; `Thing.label` and `Counter.change` say "the
   player" only for that id, which after succession reads as the name, and YOU PLAY FOR names
   the lead. Nothing in history or the icon cache is rewritten.
7. **Multiplayer is not in this plan** and is not designed against: the last section lists what
   each phase leaves in place for it.
8. **The tool cap.** Fifteen engine tools, counted as tools plus `change_world` arms, the two
   party arms not counted; twenty for 24XX and Tunnel Goons, whose SRDs play a crew, as
   `docs/24XX.md` and `docs/TUNNEL-GOONS.md` say. After this plan: 24XX 20 counted, at its
   cap; Tunnel Goons 10; Loner 10; Breathless 13.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action on the files it names. Finish it before the next.
2. **Change a shape and its tests in the same step.** One test per new behaviour; no test of prose
   or wiring. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them at the end of each phase:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line against the phase's "Fixtures" list; anything else is a bug.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file. `src` is 8,223 lines at the start of Phase 1.
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs half again past its target, stop and say so.** Never pad.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** The full check is green before the commit. Never leave two
   versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **The standing limits hold.** The cap of decision 8; every `engines/<id>/` under 2,000
   lines; imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond the `Game[P]`
   bound; every `__init__.py` empty; tests never start a process (`ScriptedSpawner`);
   `Refusal` stays the one message-bearing exception; a bad model answer is re-prompted once.
10. **Delete, do not preserve.** No compatibility path reads an old save or character file; no
    constant, helper or prompt line stays for a caller that is gone.
11. **Tests that open a game with a party** set `interjections=False` on the `GameService`
    unless the interjection is what they test, so the scripted narrator's answers are not eaten.

---

## Phase 1 — the party, everywhere

Target: about +160 lines. Loner's party arms exist; this phase gives the other three engines
the same, and every role one way to read it.

### Steps

1. **`core/views.py` — the narrator knows the party.** `NarratorView.party: tuple[
   CheckedEntityId, ...] = Field(min_length=1)`: the player first, then who travels with them.
   The validator, `_speakers_are_subjects` renamed `_everyone_is_a_subject`: every party id is a
   subject and none repeats. `NarratorView.others(self) -> tuple[Subject, ...]`: the subjects
   not in the party. Nothing else in `core` changes.
2. **`turn/context.py` — YOUR PARTY.** `render_narrator` prints WHO IS HERE from
   `view.others()` (`(nobody else)` when empty) and adds `("YOUR PARTY", ...)` after it: `you
   are Kael — <brief>` then one `with you: Mira — <brief>` line per member, or `nobody travels
   with you`. Delete the `Travelling with` sheet row in
   `SceneEngine.narrator_view`. `app/runtime.py` `OPENING` says "YOUR PARTY names them first"
   where it says WHO IS HERE does.
3. **`engines/base.py` — the party is the world's.** `World.party: list[EntityId] =
   Field(default_factory=list)` moves up from `SceneWorld`; abstract `World.members(self) ->
   Sequence[Person]`. Two free functions replace `SceneWorld.party_rows` and
   `SceneWorld.party_panel`: `party_section(members: Sequence[Thing]) -> Sections` (empty when
   nobody; else `("THE PARTY (led by the player)", one line() per member)`) and
   `party_panel(members) -> tuple[Panel, ...]` (a `Party` panel: per member an entity row, then
   one `PanelRow(label, detail)` per `rows()` entry). `here_panel` takes the others only.
   `JoinParty` and `LeaveParty` move from `scenes/tools.py` to `engines/base.py`, after
   `World`, unchanged; both families import them.
4. **`engines/scenes/` — members leave HERE.** `SceneWorld.here_lines()` skips the party;
   `SceneEngine.player_view` passes `here_panel` the present who are not members and adds
   `*party_panel(world.members())` before it; `narrator_view` passes `party=(player.id,
   *world.party)`; `master_sections` calls `party_section`.
5. **`engines/rooms/` — the room family gets the party.** `rooms/tools.py`: `SharedChange` gains
   `JoinParty | LeaveParty` from `engines/base.py`. `rooms/world.py`: `RoomWorld._playable` also
   checks each party id names a living, known npc at the player's place, none repeated; `members()`;
   `join_party(entity_id)` and `leave_party(entity_id)` with the refusals and facts `SceneWorld`
   gives (`party_joined`, `party_left`; join reveals); `kill` removes the dead from the party;
   `move` sets every member's `place` to the destination, names them in the arrival trace, and
   refuses a `with_ids` entry who travels with the player; `place_lines(known=True)` and `things_at`
   for the current place skip members and what they carry, which THE PARTY prints instead;
   `map_so_far` adds one line, `travelling with the player: <tags>`, so the worldsmith still sees
   them. `rooms/engine.py`: `shared_change` matches the two arms; `master_sections` adds
   `*party_section(world.members())` after HERE WITH THE PLAYER; `player_view` adds
   `*party_panel(...)` before the `Here` panel, which lists the others; `narrator_view` passes
   `party=(world.player.id, *world.party)`.
6. **24XX and Breathless register the pair.** `twentyfourxx/tools.py` and
   `breathless/tools.py`: `WorldChange` gains `JoinParty | LeaveParty` from
   `engines/scenes/tools.py`. `SceneEngine.shared_change` already applies them.
7. **One paragraph in every `rules.md`, under `## The party`:** a party member travels with the
   player from scene to scene and is theirs to command in the fiction and yours to voice; when
   one plainly helps, that is the engine's own help — 24XX `helped`, Loner `position`/`edge`,
   Tunnel Goons a lower `difficulty` or a named item, Breathless nothing (the fiction carries
   it); a member cannot act on their own dice unless the rules give them some; never volunteer
   a member's action to soften a scene; `join_party` when someone here decides to come along,
   `leave_party` when they stop. Tunnel Goons' `rules.md:15` loses "nobody follows on their own":
   the party comes along without `with_ids`, which stays for an NPC who follows once.
8. **Docs.** `docs/BREATHLESS.md` deviation 5 (no companions) closes. `docs/TUNNEL-GOONS.md`,
   "What the AI game master adds": the party follows the player; only the player rolls until
   Phase 5. `docs/24XX.md` tool list names the pair.

### Fixtures

`prompts/<engine>/narrator.txt` (all four): WHO IS HERE without members, YOUR PARTY, no
`Travelling with` row. `prompts/<engine>/master.txt` (all four): the paragraph, and THE PARTY
where the fixture game has one. `schemas/{twentyfourxx,breathless,tunnelgoons}/master_tools.json`:
the two arms. Nothing else.

### Done when

In every engine a named NPC joins, walks into the next scene or room, appears once in every
prompt and panel, and the narrator prompt says who travels with the player. Full check green;
one test per new behaviour; fixtures as listed.

---

## Phase 2 — interjections

Target: about +220 lines. A party member speaks or proposes a move after a turn: one narrator
spawn, gated by chattiness, dialogue and a proposal only, no state, dropped if the player acts
first; the player accepts a proposal with one press.

### Steps

1. **`engines/base.py` — chattiness.** `type Chattiness = Literal["quiet", "normal",
   "chatty"]`; `Person.chattiness: Chattiness = Field(default="normal", description="How readily
   they speak unprompted when travelling with the player.")`; the worldsmith reads the
   description in the cast draft schema. Nothing on `Subject`: only the runtime reads
   chattiness, through `engine.world(state).members()`. `config.py`:
   `Settings.interjections: bool = True`, comment "A party member may speak after a turn: one
   narrator spawn the player never waits on." `Runtime._open` passes it to
   `GameService(interjections=...)`, a field defaulting to `True`.
2. **`core/play.py` — the answer and the record.** `Interjection(Frozen)`: `lines:
   tuple[Line, ...]` ("What they say, as dialogue; empty when they would keep quiet.") and
   `proposal: str = ""` ("What they propose the party do now, as the player would type it in
   their own words; empty when they only talk."). `Exchange.proposal: str = ""`: a member's
   proposed action, standing until the next exchange. `NarratorView.interjection_refusal(self,
   member_id: EntityId, answer: Interjection) -> str | None`: `None` when every line's
   `speaker_id` is `member_id` and a proposal comes with at least one line; else the reason.
3. **`turn/prompts/interjection.md` and `turn/context.py`.** The prompt: you are `{name}`,
   `{brief}`, travelling with the player; say what you would say now, unprompted, in one to
   three lines of dialogue that add something (a worry, a suggestion, a memory, a joke), or
   answer with no lines when you would keep quiet; when you would push the party to act, set
   `proposal` to the move in the player's own words; every `speaker_id` is `{id}`; you know only
   what the player has read; never settle what the player has not done; answer with one JSON
   object. `render_interjection(view: NarratorView, member: Subject, scenes:
   Sequence[SceneRecord]) -> str`: YOUR ROLE (the prompt formatted), WHAT THE PLAYER HAS READ
   (`told_history`), SCENE, WHO IS HERE, YOUR PARTY, ANSWER WITH `Interjection`. No sheet, no
   focus: the member is not the player.
4. **`app/runtime.py` — the background spawn.** `INTERJECTION_MARK = "(the party speaks)"`, added to
   `MARKS`; `INTERJECTION_ODDS: dict[Chattiness, int] = {"quiet": 1, "normal": 2, "chatty": 3}`, the
   faces of a d6 on which a member speaks. `GameService.interject(self) -> None` is started with
   `_retain` at the end of `_turn`, after `_generate`, when `interjections` is on, `state.pending`
   and `state.generation` are `None`, `over` is `None`, and the newest exchange carries a told fact.
   The candidates are `self.engine.world(self.state).members()`, in party order; for each,
   `self.rng.randint(1, 6) <= INTERJECTION_ODDS[chattiness]` decides, and the first who passes
   speaks; nobody passing, nothing spawns. It spawns the narrator through `ask` with
   `render_interjection(view, member.subject(), scenes)` and `partial(view.interjection_refusal,
   member.id)`. On landing, in one synchronous stretch: if `self.turn is not None`, `self.phase is
   not None`, or `len(self.engine.history(self.state))` is not the count taken at spawn, drop it
   with one INFO line; if the answer has no lines, do nothing; else commit `self.engine.close(...)`
   under the mark with the lines, no facts, and the proposal, and `self.speak()`. `Engine.close`
   gains `proposal: str = ""`. `(OSError, Refusal)` logs a warning and nothing else. No `phase` is
   set: the composer stays open throughout.
5. **`ui/game.py` — the accept button.** Under the newest exchange, when it carries a proposal,
   `can_type` holds and no decision is open: a `game-card` reading `<name> proposes: <proposal>`
   with an `Accept` button that runs `session.play(Answer(text=proposal))` through `_run`, and
   the refusal path `refuse_play` takes. `Observed.exchanges` already refreshes the chat when an
   interjection lands.
6. **Docs.** `README.md`, one sentence under the roles: a party member may speak or propose a
   move after a turn. `worldsmith.md` (scenes) and `rooms/worldsmith.md`: one line on
   `chattiness`.

### Fixtures

`prompts/twentyfourxx/interjection.txt`: 24XX's golden turn script (`tests/twentyfourxx/
golden_turn.py`) gains a `join_party` on `vessa-rune` before the turn, the golden test awaits
`service._background`, and the fixture is the second narrator prompt the spawner recorded. Cast
draft schemas under `schemas/`: `chattiness`. Nothing else.

### Done when

Playing 24XX with Vessa in the party, a turn ends, the composer stays open, and a few seconds
later Vessa says something the player did not ask for, sometimes with an `Accept` under it that
plays her move; typing before she does loses nothing but her line; a quiet member speaks
rarely. Full check green; one test per new behaviour.

---

## Phase 3 — the 24XX crew rolls

Target: about +300 lines; `engines/twentyfourxx/` at most 1,050 lines. A hired member carries a
sheet the worldsmith wrote, rolls their own die to help, can act, and is raised after a job.

### Steps

1. **`core/model.py` — a request names its subject.** `Generation.target: CheckedEntityId | None =
   None`, the entity the operation concerns, when one does. `Engine.operations: tuple[Slug, ...]`,
   the requests an engine writes: `SceneEngine` sets `(DEPARTURE, COMPLICATION)`, `RoomEngine`
   `(MORE_MAP.id,)`, and both `validate`s refuse an operation outside it; 24XX and Tunnel Goons
   extend theirs with `HIRE`. An engine that uses `target` checks it in its own `validate`.
2. **`twentyfourxx/world.py` — the sheet nests.** `Sheet(Mutable)`: `specialty`, `origin: str
   = ""`, `traits`, `skills`, `credits`, `items`, `hindrances` (what `Operator` carries today), with
   `die(skill)` and `rows()`. `Crewmate(Person)` replaces `Operator` for the player and the cast
   alike, as Loner plays one type: `sheet: Sheet | None = None`, `dice(self) -> Sheet` (refuses
   "<name> carries no dice"), the state methods moved from `Operator` (`require_item`, `pay`,
   `change_hindrances`, `gain_item`, `drop_item`, `repair_item`, `spend`), each reading
   `self.dice()`; `rows()` is the sheet's or `()`; `line()` adds `gear: ...` for a sheeted member;
   `unwritten()` returns "a sheet" when one is set, so no scene draft writes dice.
   `TwentyfourxxWorld(SceneWorld[Crewmate, Crewmate])`: a validator "the player carries a sheet";
   `sheeted_members() -> list[Crewmate]` (living, with a sheet); `require_actor(actor_id: EntityId
   | None) -> Crewmate`: the player when `None`, else a living sheeted party member (refused:
   "<name> is not the player or a hired crew member"); `validate` refuses a `hire` request whose
   `target` is not a living unsheeted cast member here. `TwentyfourxxScenario =
   Scenario[SceneCanon[Crewmate]]`, `TwentyfourxxCharacter = Character[Crewmate]`; the engine's
   `cast = Crewmate`. `characters/kael/twentyfourxx.json` is rewritten to the nested shape;
   `scenarios/silent-relay` is untouched.
3. **`twentyfourxx/tools.py`.** `Hire(Frozen)`: `entity_id: CheckedEntityId` ("Exact id of who
   here signs on; they must not already carry a sheet."), `terms: str` ("What they are hired
   for and on what terms, as agreed, for the worldsmith."), the arguments of a `hire` tool.
   `Roll.actor_id: CheckedEntityId | None = None` ("null for the player; else a hired crew
   member here who acts") and `Roll.helped_by: CheckedEntityId | None = None` ("a hired crew
   member who helps: they roll their own die for the skill and the highest counts; `helped`
   stays the d6 of circumstance"). `actor_id` likewise on `ChangeHindrances`, `GainItem`,
   `DropItem`, `RepairItem`, `Spend`, `Defend`. `FinishJob.skill` becomes `FinishJob.raises:
   tuple[Raise, ...]`, `Raise(Frozen)`: `actor_id: CheckedEntityId | None`, `skill: str`; "one
   per operator: the player and every living hired member".
4. **`twentyfourxx/worldsmith.py` — the sheet draft.** `SheetDraft(Frozen)`: `specialty: str`,
   `skills: dict[str, SkillDie]` ("one to three, from the seventeen"), `items: tuple[str, ...]`
   ("what they carry, three at most"), `hindrances: tuple[str, ...] = ()`; described for the
   worldsmith. `HIRING`, the intent: the player has hired `{name}` (`{brief}`) on these terms:
   `{terms}`; write their sheet from the specialties and skills in ENGINE GUIDANCE, as someone
   who could plausibly be hired for this. `hire_guidance(pack) -> str`: each specialty's label and
   the skills it grants, then the seventeen skill labels; it is the ENGINE GUIDANCE of the hire
   prompt, since `guidance()` returns `AUTHORING` alone. `sheet_refusal(draft, pack) -> str |
   None`: the specialty is one of the pack's; every skill is one of the seventeen or one a
   specialty or its choice grants (Reading People, Medicine, Telepathy and Telekinesis are
   granted, not listed); no duplicates.
5. **`twentyfourxx/engine.py`.** `hire` tool (description: "The player hires someone here to
   work: the worldsmith writes their sheet once this turn ends, and they join the party. Refused
   for the party's unsheeted followers only when the story has not hired them."): refuses a
   stranger, the dead, an unmet one, or a sheeted member, then sets `draft.generation =
   Generation(operation=HIRE, brief=args.terms, target=args.entity_id)` and returns the wait
   fact, as `next_scene`'s complication does. `advance` handles `HIRE`: the prompt through
   `worldsmith_prompt` with `HIRING` as the intent and `SheetDraft` as the answer; install:
   `member.sheet = Sheet(...)` from the draft with `starting_items`, ₡0; `join_party` when not
   in it; facts `party_joined` (when joined) and `hired` (card "<name> signs on — <specialty>");
   the telling: `SIGNED_ON`, "<name> has signed on with the player: tell it in a line or two, and
   settle nothing else". `attempt`: `actor = world.require_actor(args.actor_id)`; `helper =
   world.require_actor(args.helped_by)` when given, not the actor; the pool is the actor's die,
   `HELP_DIE` when `helped`, the helper's `dice().die(label)` when helping, `keep_highest` over
   all of it, the label naming each die; the trace and card name the actor and the helper;
   `risking_death` kills or maims the actor. `defend`, `change_hindrances`, the item arms and
   `spend` act on `require_actor`. `finish_job`: `raises` must name the player and every living
   sheeted member once each, no stranger; each raises the named skill and rolls its own d6 of
   credits, one fact per raise and per roll. `sheet_sections` GEAR lists the player's; THE PARTY
   prints a member's `line()`.
6. **The android case** (deviation 3). `worldsmith.py`: `Body(DecisionOption)` with `kit: Kit |
   None = None`; `Origin.choice: tuple[Body, ...]`; `packs/srd.json`'s android `case` carries
   `{"kit": {"name": "Case"}}`, verified against the SRD at phase start. `create_character` adds
   the chosen body's kit to the items; `defend` then breaks it as any item.
7. **Prompts and docs.** The `attempt` description loses "an NPC carries no dice"; `AUTHORING`:
   "a cast member carries no dice until the player hires them in play"; `rules.md`: `## Hiring`
   (who gets a sheet: someone hired to work, never someone who merely comes along; the turn
   ends on `hire`), `helped_by` beside `helped`, `actor_id` on the arms, `finish_job` for the
   whole crew. `docs/24XX.md`: deviations 1 and 3 close; the tool count reads eighteen counted
   plus the pair.

### Fixtures

`schemas/twentyfourxx/master_tools.json`, `prompts/twentyfourxx/master.txt`. The solo
`attempt` line keeps its wording, so `turn/twentyfourxx.json` does not move. Nothing else.

### Done when

Kael hires Harl on a turn, the worldsmith writes Harl's sheet, Harl rolls his own die beside
Kael's and the higher counts, Harl gets his own d6 of credits when the job closes, and an
android's case breaks to defend. Full check green; one test per new behaviour; 24XX at most
1,050 lines.

---

## Phase 4 — succession and the ship

Target: about +170 lines. When the player dies with a hired member alive, the page asks who
leads; the crew has a ship whose functions break, mend and upgrade as the SRD prints.

### Steps

1. **`twentyfourxx/tools.py`.** `TakeLead` (`verb: Literal["take_lead"]`, `entity_id`) and
   `ShipUpgrade` (`verb: Literal["ship_upgrade"]`, `function: CheckedEntityId`, "Exact id of a
   ship function; ₡10 from the player.") join `WorldChange`. `Defend.item_id` and
   `RepairItem.item_id` read "an item the actor carries, or a ship function".
2. **`twentyfourxx/world.py` — the ship.** `SHIP_FUNCTIONS: tuple[str, ...] = ("Comms",
   "Crafts", "Drive", "Equipment", "Hull armor", "Sensors", "Weapons")`, verified against the
   SRD at phase start. `Item.upgraded: bool = False`, shown in `detail()`. `TwentyfourxxWorld.
   ship: dict[EntityId, Item] = Field(default_factory=basic_ship)`, `basic_ship()` one plain
   `Item` per function keyed by its slug, so a Phase 3 save still loads;
   `require_gear(actor, item_id) -> Item`: the actor's item or a ship function.
3. **`twentyfourxx/engine.py` — succession.** After any kill of `world.player` (`Kill` in
   `apply_change`, the disaster in `attempt`), `_succession(draft)`: with living sheeted members it
   sets `draft.pending = PendingDecision(kind="succession", prompt="Who leads now?", options=one
   PendingOption(id=member.id, label=member.name, detail=member.brief, name="change_world",
   args={"change": {"verb": "take_lead", "entity_id": member.id}}) per member, allows_text=False)`;
   with none, nothing, and `over` says "You died." `take_lead`: refused while the player lives or
   when the id is not a living sheeted member; `del world.cast[member.id]`, the member leaves the
   party and the scene's `here` and becomes `world.player`; the dead lead goes into `cast` under
   their id and into `here`. No reparse: one type plays both. `over`: "You died." only when the
   player is dead and no sheeted member lives. `NarratorView.party` names the new "you" with no
   further change.
4. **`twentyfourxx/engine.py` — the ship in play.** `defend` and `repair_item` resolve through
   `require_gear`; `ship_upgrade` pays ₡10 from the player and sets `upgraded` (refused when
   already upgraded); a `Ship` panel and a THE SHIP master section list the functions with
   their detail.
5. **Docs.** `rules.md`: `## Death and succession`, `## The ship`. `docs/24XX.md`: deviations 2
   and 4's ship half close; deviation 4 keeps the gear table alone; a settled reading: the new
   lead keeps their own id, and traces name them by name rather than "the player"; the tool
   count reads twenty counted plus the pair, at the cap.

### Fixtures

`schemas/twentyfourxx/master_tools.json`, `prompts/twentyfourxx/master.txt`. Nothing else.

### Done when

Kael dies on a `risking_death` disaster, the page asks who leads, Harl plays on and finishes
the job; the hull breaks to defend and is repaired. Full check green; one test per new
behaviour.

---

## Phase 5 — Tunnel Goons goons

Target: about +220 lines; `engines/tunnelgoons/` at most 650 lines. A hired goon, written by
the worldsmith, rolls, is healed by rest, and levels in turn.

### Steps

1. **`tunnelgoons/world.py` — the sheet nests.** `Abilities(Mutable)`: `abilities`, `inventory`,
   `level` (what `Goon` carries beside `hp` and `kit`), with `rows()`. `Npc(Dweller)`: `hp`,
   `sheet: Abilities | None = None`. `Goon(Person)`: `hp`, `sheet: Abilities`, `kit`.
   `TunnelGoonsWorld.require_actor(actor_id: EntityId | None) -> Goon | Npc` as 24XX's;
   `sheet_rows()` stays the player's, and `Npc.rows()` adds the sheet's rows
   after Health; `validate` refuses a `hire` request whose `target` is not a
   living unsheeted npc here. `characters/kael/tunnelgoons.json` is rewritten.
2. **`tunnelgoons/tools.py`.** `Hire(Frozen)`: `entity_id`, `terms`, as 24XX's.
   `ActionRoll.actor_id` and `LevelUp.actor_id`, `CheckedEntityId | None = None`.
   `LEVEL_OPTIONS` becomes `level_options(actor_id)`, the args carrying it.
3. **`tunnelgoons/worldsmith.py` — the sheet draft.** `AbilitiesDraft(Frozen)`: `brute`,
   `skulker`, `erudite`, each `ge=0`, summing to `ABILITY_POINTS` by validator; `HIRING` as
   24XX's, from the npc's brief and the SRD's three abilities in the guidance.
   `RoomEngine.render_extension` gains `answer: type[BaseModel]`, its callers passing
   `self.map_draft()`.
4. **`tunnelgoons/engine.py`.** `hire` tool as 24XX's, setting the request;
   `TunnelGoonsEngine.advance` dispatches on `request.operation` before `super().advance`: for
   `HIRE`, the prompt through `render_extension` with `HIRING` and `AbilitiesDraft`; install
   `Abilities(abilities=..., inventory=INVENTORY_START, level=1)` on the npc, `join_party` when not
   in it, the facts and the telling as 24XX's. `action_roll` uses the actor's abilities, carried
   items and inventory penalty; the damage lands on the actor, and a member at 0 dies through
   `world.kill`, which drops their items and leaves the party. `rest` heals the player and every
   member. `level_up` with no choice opens the decision for the player; answering it applies and
   opens the next for the first living hired member after the actor in party order; the last answer
   opens nothing. `rules.md`: `## Hiring`, the actor on the roll, levelling in turn.
   `docs/TUNNEL-GOONS.md`: the "only the player has abilities" paragraph is rewritten; the tool
   count reads ten counted plus the pair.

### Fixtures

`schemas/tunnelgoons/master_tools.json`, `prompts/tunnelgoons/master.txt`. Nothing else.

### Done when

A hired goon rolls, takes a hit, rests, and levels after the player. Full check green; one test
per new behaviour; Tunnel Goons at most 650 lines. `IDEAS.md` 16 leaves.

---

## Refused in this plan, with the reason

- **An agent per NPC**, acting between turns: decision 2. The turn transaction is the game; the
  "twelve parallel models" lesson in `COMPETITOR-RESEARCH.md` is the same lesson.
- **An interjection as a master tool** (`say_as`): the master writes no prose the player reads.
- **The narrator choosing who interjects**: "you are Mira" plays better than "somebody speaks";
  the dice give the surprise, chattiness the frequency, the model the silence.
- **Per-member knowledge** (`knownBy`): a member reads what the player has read. One gate.
- **A sheet built by code from a specialty the master names**: the maintainer's call; the
  worldsmith writes who has dice, and a worldsmith spawn at hiring is rare.
- **A round-based turn for several players**: not this plan.
- **The priced gear table**: not a crew rule; stays in `docs/24XX.md` deviation 4.
- **A `Crew` store, `PARTY_MAX`, a `Regular` class, `Offer.follows`**: refused before, stand.
- **Rewriting ids on succession**: decision 6.

## What each phase leaves in place for multiplayer

Not designed here; only what must not be closed. Two people can already open one game URL from
two devices on the LAN and take turns: sessions are one per save, pages poll, and a turn in
flight refuses the second composer.

- Phase 1: the party is the crew, and a member is a full entity with a sheet slot; a second
  human would drive one.
- Phase 2: an interjection lands as an `Exchange` under a mark and a proposal is a typed
  action a press sends; a second human's line and move would take the same two shapes.
- Phase 3: `actor_id` on every acting tool; PLAYER ACTION would only need to say who acts.
- Phase 4: `take_lead` is the one path that moves `world.player`; a human-driven member is a
  valid successor.
- What would be new, and nothing here forecloses: a second character file per game
  (`Game.characters`), `Answer.actor_id`, and the page choosing who you are.
