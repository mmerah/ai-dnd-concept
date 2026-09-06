# PLAN — the party, then the crew

Five phases, in order. **Phase 1** gives every engine the party: an NPC who joins the player,
follows them, and is read as the party by all three roles. **Phase 2** lets a party member speak
unprompted after a turn, at the cost of one narrator spawn the player never waits on. **Phase 3**
gives 24XX a crew that rolls beside the player. **Phase 4** lets a crew member take the lead when
the player dies. **Phase 5** gives Tunnel Goons goons who roll and level. Self-standing: an
implementer needs this file, `CLAUDE.md` and the code. Track G of `NEXT-SPECS.md` (2026-09-02)
is folded here and cut from that file, with two of its shapes replaced (below, "Decisions").

What stays, everywhere: one turn is one player input on one draft behind the commit gate; only
code changes state or rolls dice; the narrator reads revealed facts only; the three roles, each
a cold spawn; every engine self-contained; scenarios and characters authored and stored on
their own. What is not built: an agent per NPC, a second human player, the 24XX ship, a crew
store beside the cast, a party cap, a summariser.

Saves have no version field. Phase 1 changes `World` by a defaulted field, so saves still load.
Phase 3 nests the 24XX sheet and Phase 5 nests the Tunnel Goons sheet, so those engines' saves
and character files from before go stale: the launcher skips a stale save with its warning, and
the shipped character files are rewritten by hand in the same phase. Nothing migrates.

## Decisions

1. **The party is one shape in `World`**, `party: list[EntityId]`, moved up from `SceneWorld`;
   the room family gains the same list, and `move` carries it. Two arms, `join_party` and
   `leave_party`, in every engine; the pair is not counted against the tool cap.
2. **An NPC agent is refused.** A member who "acts on their own" would either change state
   outside a turn, which the transaction and the one-turn-in-flight rule forbid, or only talk,
   which is Phase 2. A spawn per member per turn multiplies wall-clock and cost for the same
   reason the summariser was refused; the master already voices the party in the fiction.
3. **An interjection is one narrator spawn, in the background, dropped if the player acts
   first.** It lands as an `Exchange` under its own mark, so every role reads it back through
   the history that exists, the chat draws it, and speech reads it. The member is chosen by the
   turn's `Random`; the model may answer with no lines, which records nothing.
4. **A crew member's dice come from a `hire` arm, not from the worldsmith.** Track G.2 had the
   worldsmith write a sheet into the cast. Here the master names a specialty when someone is
   hired, and code builds the sheet from the pack, as `create_character` builds the player's.
   The cast draft does not change; "the cast carries no dice" stays true for authoring; no
   extra spawn. A member without a sheet follows and helps as Phase 1 says; a hired one rolls.
5. **Succession keeps ids.** The member who takes the lead keeps their own id as
   `world.player.id`; the dead lead goes into the cast under `player`. `PLAYER_ID` then names
   a character file's sheet and nothing in play; `Thing.label` and `Counter.change` say "the
   player" only for that id, which after succession reads as the name, and YOU PLAY FOR names
   the lead. No id is rewritten in history or in the icon cache.
6. **Multiplayer is not in this plan.** `COMPETITOR-RESEARCH.md` records the earlier "no"; the
   maintainer's "maybe" is answered by the design the crew leaves room for (last section) and by
   playing the crew first. Two browsers on one game URL already share one game today.
7. **The tool cap.** Fifteen engine tools, counted as tools plus `change_world` arms, the two
   party arms not counted; twenty for 24XX and Tunnel Goons, whose SRDs play a crew, as
   `docs/24XX.md` and `docs/TUNNEL-GOONS.md` say. After this plan: 24XX 18 counted, Tunnel
   Goons 10, Loner 12, Breathless 13.

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
9. **The standing limits hold.** The cap of decision 7; every `engines/<id>/` under 2,000
   lines; imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond the `Game[P]`
   bound; every `__init__.py` empty; tests never start a process (`ScriptedSpawner`);
   `Refusal` stays the one message-bearing exception; a bad model answer is re-prompted once.
10. **Delete, do not preserve.** No compatibility path reads an old save or character file; no
    constant, helper or prompt line stays for a caller that is gone.
11. **Tests that open a game with a party** set `interjections=False` on the `GameService`
    unless the interjection is what they test, so the scripted narrator's answers are not eaten.

---

## Phase 1 — the party, everywhere

Target: about +150 lines. Loner's party arms exist; this phase gives the other three engines
the same, and every role one way to read it.

### Steps

1. **`core/views.py` — the narrator knows the party.** `NarratorView.party: tuple[
   CheckedEntityId, ...] = Field(min_length=1)`: the player first, then who travels with them.
   The validator, in `_speakers_are_subjects` renamed `_everyone_is_a_subject`: every party id
   is a subject and none repeats. Nothing else in `core` changes.
2. **`turn/context.py` — YOUR PARTY.** `render_narrator` adds `("YOUR PARTY", ...)` after WHO IS
   HERE: `you are Kael; with you: Mira, Dax`, or `you are Kael; nobody travels with you`, names
   looked up in `view.subjects`. Delete the `Travelling with` sheet row in
   `SceneEngine.narrator_view`.
3. **`engines/base.py` — the party is the world's.** `World.party: list[EntityId] =
   Field(default_factory=list)` moves up from `SceneWorld`; abstract `World.members(self) ->
   Sequence[Person]`. Two free functions replace `SceneWorld.party_rows` and
   `SceneWorld.party_panel`: `party_section(members: Sequence[Thing]) -> Sections` (empty
   when nobody; else `("THE PARTY (led by the player)", one "- <line()>" per member)`) and
   `party_panel(members) -> tuple[Panel, ...]` (a `Party` panel: for each member an entity
   row, then one `PanelRow(label, detail)` per `rows()` entry). `SceneWorld` keeps its
   validator, `members()`, `join_party`, `leave_party` and the party in `apply_scene`;
   `SceneEngine` calls the two functions.
4. **`engines/rooms/` — the room family gets the party.** `rooms/tools.py`: `JoinParty`
   (`verb: Literal["join_party"]`, `entity_id`, description "Exact id of a living npc here who
   starts travelling with the player.") and `LeaveParty` (`verb: Literal["leave_party"]`,
   `entity_id`), added to `SharedChange`. `rooms/world.py`: `RoomWorld._playable` also checks
   each party id names a living, known npc at the player's place, none repeated;
   `members()`; `join_party(entity_id)` and `leave_party(entity_id)` with the refusals and facts
   `SceneWorld` gives (`party_joined`, `party_left`; join reveals); `kill` removes the dead
   from the party; `move` sets every member's `place` to the destination and names them in the
   arrival trace before `with_ids`, and refuses a `with_ids` entry who travels with the player
   ("X already travels with the player"). `rooms/engine.py`: `shared_change` matches the two
   arms; `master_sections` adds `*party_section(world.members())` after HERE WITH THE
   PLAYER; `player_view` adds `*party_panel(...)` before the `Here` panel; `narrator_view`
   passes `party=(world.player.id, *world.party)`.
5. **24XX and Breathless register the pair.** `twentyfourxx/tools.py` and
   `breathless/tools.py`: `WorldChange` gains `JoinParty | LeaveParty` from
   `engines/scenes/tools.py`. `SceneEngine.shared_change` already applies them.
6. **One paragraph in every `rules.md`, under `## The party`:** a party member travels with the
   player from scene to scene and is theirs to command in the fiction and yours to voice; when
   one plainly helps, that is the engine's own help — 24XX `helped`, Loner `position`/`edge`,
   Tunnel Goons a lower `difficulty` or a named item, Breathless nothing (the fiction carries
   it); a member cannot act on their own dice unless the rules give them some; never volunteer
   a member's action to soften a scene; `join_party` when someone here decides to come along,
   `leave_party` when they stop. Tunnel Goons' `rules.md:15` loses "nobody follows on their own":
   the party comes along without `with_ids`, which stays for an NPC who follows once.
7. **Docs.** `docs/BREATHLESS.md` deviation 5 (no companions) closes. `docs/TUNNEL-GOONS.md`,
   "What the AI game master adds": the party follows the player; only the player rolls until
   Phase 5. `docs/24XX.md` tool list names the pair.

### Fixtures

`prompts/<engine>/narrator.txt` (all four): YOUR PARTY, and 24XX/Loner lose the `Travelling
with` row where the fixture game has a party. `prompts/<engine>/master.txt` (all four): the
paragraph. `schemas/{twentyfourxx,breathless,tunnelgoons}/master_tools.json`: the two arms.
Nothing else.

### Tests

`tests/core/test_views.py`: a party id that is not a subject is refused. `tests/core/
test_rooms.py`: `join_party` files the npc and `move` carries them; `with_ids` naming a member
is refused; a dead or elsewhere member fails the validator. `tests/core/test_context_boundary.py`
(or the golden alone): YOUR PARTY names nobody unmet.

### Done when

In every engine a named NPC joins, walks into the next scene or room, and the narrator prompt
says who travels with the player. Full check green; fixtures as listed.

---

## Phase 2 — interjections

Target: about +180 lines. A party member speaks unprompted after a turn: one narrator spawn,
dialogue only, no state, dropped if the player acts first.

### Steps

1. **`config.py` — one switch.** `Settings.interjections: bool = True`, comment "A party member
   may speak after a turn: one narrator spawn the player never waits on." The settings page
   renders it as it renders every top-level field. `Runtime._open` passes it to
   `GameService(interjections=settings.interjections)`; `GameService.interjections: bool =
   True` is a field.
2. **`core/views.py` — the leak rule for one voice.** `NarratorView.interjection_refusal(self,
   member_id: EntityId, narration: Narration) -> str | None`: `None` when every line's
   `speaker_id == member_id`, empty lines included (silence); otherwise "only <name> speaks
   here; leave no line to narration or to anyone else". `narration_refusal` stays for turns.
3. **`turn/prompts/interjection.md` and `turn/context.py`.** The prompt: you are `{name}`,
   `{brief}`, travelling with the player; say what you would say now, unprompted, in one to
   three lines of dialogue that add something (a worry, a suggestion, a memory, a joke), or
   answer with no lines when you would keep quiet; every `speaker_id` is `{id}`; you know only
   what the player has read; never settle what the player has not done; answer with one JSON
   object. `render_interjection(view: NarratorView, member: Subject, scenes:
   Sequence[SceneRecord]) -> str`: YOUR ROLE (the prompt formatted), WHAT THE PLAYER HAS READ
   (`told_history`), SCENE, WHO IS HERE, YOUR PARTY, ANSWER WITH `Narration`. No sheet, no
   focus: the member is not the player.
4. **`app/runtime.py` — the background spawn.** `INTERJECTION_MARK = "(the party speaks)"`,
   added to `MARKS`. `GameService.interject(self) -> None` is started with `_retain` at the end
   of `_turn`, after `_generate`, when: `interjections` is on, `state.pending` and
   `state.generation` are `None`, `over` is `None`, the newest exchange carries a told fact, and
   `view.party[1:]` has an id in `view.speakers`. The member is `self.rng.choice` of those.
   It spawns the narrator through `ask` with `render_interjection` and
   `partial(view.interjection_refusal, member.id)`. On landing, in one synchronous stretch:
   if `self.turn is not None`, `self.phase is not None`, or `self._newest()` is not the
   exchange it answered, drop it with one INFO line; if the answer has no lines, do nothing;
   else `self.commit(self.engine.close(self.state.draft(), INTERJECTION_MARK, lines, ()))` and
   `self.speak()`. `(OSError, Refusal)` logs a warning and nothing else. No `phase` is set: the
   composer stays open throughout.
5. **`ui/game.py`.** Nothing: `Observed.exchanges` moves when it lands, the chat draws the mark
   as it draws the other marks and the member's bubble under it.
6. **Docs.** `README.md`, one sentence under the roles: a party member may speak after a turn.

### Fixtures

`prompts/<engine>/interjection.txt` for the one engine whose golden turn travels with someone
(add a member to that fixture's scenario if none does). Nothing else moves.

### Tests

`tests/core/test_game_service.py`: an interjection lands as an exchange under the mark with the
member's lines alone; an answer with no lines records nothing; a turn begun before it lands
drops it and the save holds no trace of it; `interjections=False` spawns no narrator; no party,
no spawn. `tests/core/test_views.py`: a line by anyone else, or narration, is refused.
`tests/core/test_context_boundary.py`: the interjection prompt holds no hidden name.

### Done when

Playing 24XX with Vessa in the party, a turn ends, the composer stays open, and a few seconds
later Vessa says something the player did not ask for; typing before she does loses nothing but
her line. Full check green.

---

## Phase 3 — the 24XX crew rolls

Target: about +250 lines; `engines/twentyfourxx/` at most 1,000 lines. A hired member carries a
sheet, rolls their own die to help, can act, and is raised after a job.

### Steps

1. **`twentyfourxx/world.py` — the sheet nests.** `Sheet(Mutable)`: `specialty`, `origin: str =
   ""`, `traits`, `skills`, `credits`, `items`, `hindrances` (what `Operator` carries today),
   with `die(skill)` and `rows()`. `Crewmate(Person)`: `sheet: Sheet | None = None`, `dice(self)
   -> Sheet` (refuses "<name> carries no dice"), and the state methods moved from `Operator`
   (`require_item`, `pay`, `change_hindrances`, `gain_item`, `drop_item`, `repair_item`,
   `spend`), each reading `self.dice()`; `rows()` is the sheet's or `()`. `Operator(Crewmate)`:
   `sheet: Sheet`. `TwentyfourxxWorld(SceneWorld[Crewmate, Operator])` gains
   `sheeted_members() -> list[Crewmate]` (living, with a sheet) and `require_actor(actor_id:
   EntityId | None) -> Crewmate | Operator`: the player when `None`, else a living sheeted
   party member (refused: "<name> is not the player or a hired crew member"). `TwentyfourxxScenario
   = Scenario[SceneCanon[Crewmate]]`; the engine's `cast = Crewmate`. `characters/kael/
   twentyfourxx.json` is rewritten to the nested shape; `scenarios/silent-relay` is untouched.
2. **`twentyfourxx/tools.py`.** `Hire` (`verb: Literal["hire"]`, `entity_id`, `specialty: str`,
   description "A specialty from the packs; the sheet is built from it") joins `WorldChange`.
   `Roll.actor_id: CheckedEntityId | None = None` ("null for the player; else a hired crew
   member here who acts") and `Roll.helped_by: CheckedEntityId | None = None` ("a hired crew
   member who helps: they roll their own die for the skill and the highest counts; `helped`
   stays the d6 of circumstance"). `actor_id` likewise on `ChangeHindrances`, `GainItem`,
   `DropItem`, `RepairItem`, `Spend`, `Defend`. `FinishJob.skill` becomes `FinishJob.raises:
   tuple[Raise, ...]` with `Raise(Frozen)`: `actor_id: CheckedEntityId | None`, `skill: str`;
   description "one per operator: the player and every living hired member".
3. **`twentyfourxx/engine.py`.** `hire`: `require_here(alive=True)` must be a `Crewmate` without
   a sheet; the specialty resolves against the packs as `resolve_skill` resolves a skill; the
   sheet is `Sheet(specialty=label, skills=specialty.skills, items=starting_items(specialty.kit))`,
   ₡0, no origin, a printed skill choice not made; joins the party when not in it; facts:
   `party_joined` when joined, then `hired` with card "<name> hired — <specialty>". `attempt`:
   `actor = world.require_actor(args.actor_id)`; `helper = world.require_actor(args.helped_by)`
   when given, not the actor; the pool is the actor's die, `HELP_DIE` when `helped`, the helper's
   `dice().die(label)` when helping, `keep_highest` over all of it, the label naming each die;
   the trace and card name the actor and the helper; `risking_death` kills or maims the actor.
   `defend`, `change_hindrances`, the item arms and `spend` act on `require_actor`. `finish_job`:
   `raises` must name the player and every living sheeted member once each, no stranger;
   each raises the named skill and rolls its own d6 of credits, one fact per raise and per roll.
   `sheet_sections` GEAR lists the player's; THE PARTY prints a member's `line()`, which now
   carries the sheet rows; `Crewmate.line(detail=...)` adds `gear: ...` for a sheeted member.
4. **Prompts and docs.** The `attempt` description loses "an NPC carries no dice"; `AUTHORING`:
   "a cast member carries no dice until the player hires them in play"; `rules.md`: `## Hiring`
   (who gets a sheet: someone hired to work, never someone who merely comes along), `helped_by`
   beside `helped`, `actor_id` on the arms, `finish_job` for the whole crew. `docs/24XX.md`:
   deviation 1 closes; deviation 4 keeps the gear table and the ship; the settled readings gain
   "a hire takes the specialty's fixed skills and kit, no origin, no printed choice"; the tool
   count reads eighteen counted plus the pair.

### Fixtures

`schemas/twentyfourxx/master_tools.json`, `prompts/twentyfourxx/master.txt`,
`turn/twentyfourxx.json` (`finish_job` now `raises`; `tests/twentyfourxx/golden_turn.py` is
rewritten to call it so). Nothing else.

### Tests

`tests/twentyfourxx/`: `hire` builds the sheet from the pack and joins; `attempt` with
`helped_by` keeps the highest of the actor's and the helper's dice; an unsheeted helper or a
stranger actor is refused; `risking_death` on a hired actor kills them and they leave the party;
`finish_job` refuses a missing member and raises each named one; the flat character file is
refused by `read_character`.

### Done when

Kael hires Harl, Harl rolls his own die beside Kael's and the higher counts, Harl gets his own
d6 of credits when the job closes. Full check green; 24XX at most 1,000 lines.

---

## Phase 4 — succession

Target: about +90 lines. When the player dies with a hired member alive, the page asks who
leads; the game ends only when nobody can.

### Steps

1. **`twentyfourxx/tools.py`.** `TakeLead` (`verb: Literal["take_lead"]`, `entity_id`) joins
   `WorldChange`. Description: "A living hired member takes the lead after the player's death;
   answered from the page, never called while the player lives."
2. **`twentyfourxx/engine.py`.** After any kill of `world.player` (`Kill` in `apply_change`, the
   disaster in `attempt`), `_succession(draft)`: with living sheeted members it sets
   `draft.pending = PendingDecision(kind="succession", prompt="Who leads now?", options=one
   PendingOption(id=member.id, label=member.name, detail=member.brief, name="change_world",
   args={"change": {"verb": "take_lead", "entity_id": member.id}}) per member,
   allows_text=False)`; with none, nothing, and `over` says "You died." `take_lead`: refused
   while the player lives or when the id is not a living sheeted member; the member becomes
   `world.player` as an `Operator` (`parse(Operator, member.model_dump())`), leaves the party
   and the scene's `here`; the dead lead goes into `cast` under their id and into `here`.
   `TwentyfourxxEngine.over`: "You died." only when the player is dead and no sheeted member
   lives. `NarratorView.party` names the new "you" with no further change.
3. **Docs.** `rules.md`: `## Death and succession`. `docs/24XX.md`: deviation 2 closes; a settled
   reading: the new lead keeps their own id, and traces name them by name rather than "the
   player".

### Fixtures

`schemas/twentyfourxx/master_tools.json`, `prompts/twentyfourxx/master.txt`. Nothing else.

### Tests

`tests/twentyfourxx/`: a player's death with a hired member opens the decision and `over` is
`None`; answering it swaps the lead and the next `attempt` rolls the new lead's die; a death
with nobody hired ends the game; `take_lead` while the player lives is refused.

### Done when

Kael dies on a `risking_death` disaster, the page asks who leads, Harl plays on and finishes
the job. Full check green.

---

## Phase 5 — Tunnel Goons goons

Target: about +170 lines; `engines/tunnelgoons/` at most 600 lines. A hired goon rolls, is
healed by rest, and levels in turn.

### Steps

1. **`tunnelgoons/world.py` — the sheet nests.** `Abilities(Mutable)`: `abilities`, `inventory`,
   `level` (what `Goon` carries beside `hp` and `kit`), with `rows()`. `Npc(Dweller)`: `hp`,
   `sheet: Abilities | None = None`. `Goon(Person)`: `hp`, `sheet: Abilities`, `kit`.
   `TunnelGoonsWorld.require_actor(actor_id: EntityId | None) -> Goon | Npc` as 24XX's;
   `sheet_rows()` for the actor; `hire(entity_id, abilities)` refuses a sum other than
   `ABILITY_POINTS` and a sheeted member. `characters/kael/tunnelgoons.json` is rewritten.
2. **`tunnelgoons/tools.py`.** `Hire` (`verb: Literal["hire"]`, `entity_id`, `brute`, `skulker`,
   `erudite`, each `ge=0`) joins `ChangeWorld`'s union. `ActionRoll.actor_id` and
   `LevelUp.actor_id`, `CheckedEntityId | None = None`. `LEVEL_OPTIONS` becomes
   `level_options(actor_id)`, the args carrying it.
3. **`tunnelgoons/engine.py`.** `action_roll` uses the actor's abilities, carried items and
   inventory penalty; the damage lands on the actor, and a member at 0 dies through
   `world.kill`, which drops their items and leaves the party. `rest` heals the player and every
   member. `level_up` with no choice opens the decision for the player; answering it applies and
   opens the next for the first living hired member after the actor in party order; the last
   answer opens nothing. `rules.md`: `## Hiring`, the actor on the roll, levelling in turn.
   `docs/TUNNEL-GOONS.md`: the "only the player has abilities" paragraph is rewritten; the
   tool count reads ten counted plus the pair.

### Fixtures

`schemas/tunnelgoons/master_tools.json`, `prompts/tunnelgoons/master.txt`. Nothing else.

### Tests

`tests/tunnelgoons/`: `hire` builds the sheet and refuses a wrong sum; a member's `action_roll`
uses their abilities and damage lands on them; `rest` heals the party; `level_up` chains one
decision per goon and ends; the flat character file is refused.

### Done when

A hired goon rolls, takes a hit, rests, and levels after the player. Full check green; Tunnel
Goons at most 600 lines. `IDEAS.md` 16 leaves.

---

## Refused in this plan, with the reason

- **An agent per NPC**, acting between turns: decision 2. The turn transaction is the game; the
  "twelve parallel models" lesson in `COMPETITOR-RESEARCH.md` is the same lesson.
- **An interjection as a master tool** (`say_as`): the master writes no prose the player reads.
- **The narrator choosing who interjects**: "you are Mira" plays better than "somebody speaks";
  the rng gives the surprise, the model gives the silence.
- **Per-member knowledge** (`knownBy`): a member reads what the player has read. One gate.
- **The worldsmith writing sheets** (G.2): decision 4.
- **A round-based turn for several players**: not this plan; the sketch below keeps hot seat.
- **The ship**: stays with the gear table in `docs/24XX.md` deviation 4 and `IDEAS.md`.
- **A `Crew` store, `PARTY_MAX`, a `Regular` class, `Offer.follows`**: refused before, stand.
- **Rewriting ids on succession**: decision 5.

## After this plan — what multiplayer would be

Not built here; written so the crew does not foreclose it. Two people can already open one game
URL from two devices on the LAN and take turns: sessions are one per save, pages poll, and a
turn in flight refuses the second composer. What is missing is a second character.

- **A second human drives a party member.** The party is the crew; a member is driven by a
  human or voiced by the roles. Phase 2's interjection is what an AI-driven member does between
  turns; a human-driven one types. Both land as the same `Exchange` shape.
- **Identity.** `Game.characters: dict[EntityId, Slug]` (member id to character file), the
  second character file relaxing `check_character`'s `id == PLAYER_ID`; the page picks who you
  are (`?as=<character>`), the composer sends `Answer.actor_id`; PLAYER ACTION says who acts.
- **The turn stays one input.** Hot seat: any human's message opens a turn; the master resolves
  it for that actor through Phase 3's `actor_id`; the others read. No rounds, no merging.
- **The lead.** `world.player` stays the first human's character; Phase 4's `take_lead` is the
  only path that moves it, and a human-driven member is a valid successor.
- **Cost.** Nothing new spawns: the same three roles per turn, whoever typed.

About +250 lines across `core/model.py`, `engines/seam.py`, `turn/run.py`, `app/runtime.py`,
`ui/game.py`, once the crew has played through and the maintainer says yes.
