# PROGRESS

One entry per phase of `PLAN.md`: the `src` line counts before and after, decisions made off the
plan, review findings refuted and why, and what is known and accepted.

## Phase 1 — the party, everywhere

- `src`: 8,223 → 8,324 lines (+101; target about +110). Tests: 452 → 459.
- Off-plan decisions:
  - `here_panel(player, others)` keeps its signature; "takes the others only" is read as the
    callers passing the present who are not members, so the player still heads the `Here` panel
    when nobody travels with them.
  - `World.join(member)` and `World.part(member)` on `engines/base.py` hold the refusal, the list
    change and the `party_joined` / `party_left` facts; each family's `join_party` / `leave_party`
    resolves its own entity and delegates. Two worlds needed one body (review finding).
  - Both world validators refuse a party member the player has not met (`known`), since the
    narrator view builds its subjects from the known only and would otherwise raise a pydantic
    error instead of a refusal at the save boundary (review finding).
  - `SceneWorld.others()` names the present who are not members; `here_lines` and the `Here`
    panel read it.
  - `tests/breathless/test_tools.py` lost its test that `join_party` is refused in Breathless: a
    test of a deleted behaviour goes with it (PLAN "How to work" 2).
- Refuted findings:
  - "`RoomWorld.leave_party` may resolve through `self.require`": `require` returns
    `Person | Item | Place` and `World.part` takes a `Person`; the three-line `npcs.get` lookup
    stays.
  - "Abstract `World.members` has no caller typed as `World`; defer to Phase 2": PLAN step 3
    prescribes it; kept.
- Known and accepted: the two-line "remove the dead from the party" sits in both `kill`s; two
  lines do not earn a helper.
- Reviews: Fable and Opus (no `codex` on the machine).

## Phase 2 — interjections

- `src`: 8,324 → 8,507 lines (+183; target about +140). Tests: 459 → 469.
- Off-plan decisions:
  - The golden `SEED` moves from 11 to 19: on 11 Vessa rolls a 9 after the turn even as `chatty`;
    on 19 she rolls a 1 at the default `normal`, so no script sets her chattiness. Every engine's
    `turn/*.json` and the breathless and tunnelgoons narrator prompts move in dice values and
    their outcomes only (PLAN offered "or the seed is chosen so"; its "Nothing else" assumed the
    chatty route).
  - `GameService.hush()` cancels the interjection in flight; `_turn` and `restart` call it, and
    `Runtime.reload_settings` calls it on every session it evicts. Cancelling kills the narrator
    spawn, so quick turns do not stack spawns whose answers are all dropped, and an evicted
    session cannot land a line on a rival's save (both review findings). The landing checks of
    PLAN step 4 stay for the write path (`act`), which sets no turn.
  - `Interjection.proposal` is stripped by a validator: Accept plays it as typed text, which the
    composer would have stripped (review finding).
  - The interjection prompt's YOUR PARTY reads `the player is Kael` / `with them: ...`, since the
    member is the reader; `_party_lines` takes `lead` and `beside` (review finding).
  - The member reads the narrator's whole picture, against PLAN step 3's "no sheet, no focus":
    `NarratorView` is the revealed-only gate, so nothing in it can leak, and a companion who
    cannot see the sheet or the scene's focus has nothing to worry about or push toward. One
    `_picture` in `turn/context.py` serves both renderers; WHAT HAPPENED is the ended turn's
    told facts (maintainer's call after the commit).
  - The spawn gate drops `state.generation is None`: `_generate` clears it on every path.
  - `play_turn` gains `then=`, further narrator answers queued behind the turn's, and
    `ScriptedSpawner.prompt` gains `nth`; the interjection golden is gated on the game having a
    party, so a member who stops speaking fails the test rather than skipping it.
- Refuted findings:
  - "Drop `player.prompt is None` from `standing_proposal`, an unreachable state": PLAN step 5
    names the condition; one clause, kept.
- Known and accepted: the `uv run aidm` smoke here reaches the launcher only; a turn needs a CLI
  model spawn the container cannot make.
- Reviews: Fable and Opus (no `codex` on the machine).

## Phase 3 — the 24XX crew rolls

- `src`: 8,507 → 8,828 lines (+321; target about +280). `engines/twentyfourxx/`: 740 → 1,034
  (cap 1,050). Tests: 469 → 494.
- Off-plan decisions:
  - `HIRE` lives in `engines/base.py` beside `SRD_PACK`: PLAN names no home.
  - Tunnel Goons does not extend `operations` with `HIRE` yet: nothing writes the request, and
    `RoomEngine.advance` would play one as a map extension. Phase 5 adds it with the tool
    (both reviews; PLAN step 1 and Phase 5 step 4 amended).
  - Gear is a row of `Crewmate.rows()` (`Gear: Comm, Vest (broken)`), not a `line()` extra: one
    place feeds the Character and Party panels, YOU PLAY FOR, THE PARTY, the cast lines, the
    interjection's YOUR SHEET and the narrator's THE PLAYER'S SHEET. The `Gear` panel and 24XX's
    `preview_character` override go; GEAR in the master prompt stays for the ids and the break
    state the arms need. The narrator prompt fixture moves by that one line (review finding;
    PLAN step 2 had put gear in `line()`, against step 8's stated purpose).
  - `Subject.rows` is not added: every subject rides in `NarratorView`, whose promise is to hold
    nothing hidden, and a Loner cast member's rows (goal, motive, nemesis) would have. The
    interjection's sheet is passed to `render_interjection` as its own argument; the runtime
    reads `member.rows()`.
  - The `hire` description says a follower may be hired too, instead of PLAN step 5's "refused
    ... only when the story has not hired them", a refusal the code never makes (review finding).
  - The hire's pack is the game's first pack (`draft.packs[0]`); PLAN says `pack`, singular.
  - `sheeted_members()` reads the party, not the cast: `require_actor` needs party membership,
    so a hired member who had left the party would otherwise make `finish_job` impossible.
  - `require_actor` also takes the player's own id, which the master sees as `Kael[player]`
    (review finding).
  - `TwentyfourxxWorld.require_hireable` serves `hire`, `validate` and `advance`; three callers
    had spelled "here, alive, unsheeted" three ways (review finding).
  - `SceneEngine.render_request` is the one worldsmith prompt builder; `render_next` and the hire
    prompt both call it (review finding).
  - `finish_job`'s refusal counts the raises (`Counter`) and names the missing, extra and
    repeated actors by name (review finding).
  - PLAN.md Phase 4 step 5 now names deviations 1 and 2, since this phase deleted 1 and 3 and
    renumbered (review finding).
  - Refusals in the sheet methods moved onto `Crewmate` name the crewmate, not "the player".
- Refuted findings: none; the three first refuted on PLAN wording were taken on the maintainer's
  word that the plan can be wrong.
- Known and accepted: the `uv run aidm` smoke reaches the launcher only; a turn needs a CLI
  model spawn.
- Reviews: Fable and Opus (no `codex` on the machine).

## Phase 4 — succession and the ship

- `src`: 8,828 → 8,957 lines (+129; target about +120). `engines/twentyfourxx/`: 1,034 → 1,163.
  Tests: 494 → 504.
- SRD verified at phase start: the seven functions in the SRD's order; "upgrades cost ₡10 each";
  "Hull armor: Break harmlessly for defense"; "If killed, make a new character to introduce ASAP".
- Off-plan decisions:
  - `ShipUpgrade.function` is `function_id`: every other id field in the union is `*_id`, and the
    master reads the field name before its description (review finding; PLAN step 1 said
    `function`).
  - The ship's `default_factory` is justified by "every crew has one from the start" alone; the
    "so a Phase 3 save still loads" reason (PLAN step 2) is dropped from the comment and the test
    that pinned it, since CLAUDE.md and PLAN rule 10 say no compatibility path reads an old save.
    The default still lets such a save load; nothing is written to keep it so (both reviews).
  - `take_lead` resolves the successor through `require_actor` and refuses only the dead lead's
    own id, instead of a third spelling of "living, sheeted, in the party" (both reviews).
  - `TwentyfourxxEngine.over` defers to `Engine.over` when no sheeted member lives, so "You died."
    is spelled once (review finding).
  - The ship has no per-function rule: hull armor breaks through `defend` like any item, hindrance
    and all, and every function may be named on `defend` and `repair_item`. `rules.md` no longer
    says "harmlessly"; `docs/24XX.md` records it as deviation 2 (review finding; PLAN step 2
    gives `require_gear` one shape for items and functions).
  - `take_lead` and `ship_upgrade` are documented under the `change_world` bullet, not `hire`'s.
  - `_item_lines` renders GEAR and THE SHIP; `_gear_lines` misnamed the second (review finding).
- Refuted findings:
  - The cut folding `panels`' `job_panel`/`ship_panel` locals into one return: two named locals
    read better than a nested splat; a cut offered, not a defect.
- Known and accepted: `Thing.label` still says "the player" for `PLAYER_ID` only (decision 6), so
  a trace about the dead lead after succession reads "the player Kael[player]"; HERE lines use
  `tag`, so the master prompt is unaffected. The `uv run aidm` smoke reaches the launcher only;
  a turn needs a CLI model spawn.
- Reviews: Fable and Opus (no `codex` on the machine).

## Phase 5 — Tunnel Goons goons

- `src`: 8,957 → 9,135 lines (+178; target about +150). `engines/tunnelgoons/`: 367 → 521
  (cap 600). Tests: 504 → 515.
- Off-plan decisions:
  - `Abilities.rows(hp)` prints one order (Brute, Skulker, Erudite, Health, Inventory, Level)
    for the player and a hired npc alike; PLAN step 1's "`Npc.rows()` adds the sheet's rows after
    Health" would have given the two a different order, and the narrator prompt fixture stays
    where it was.
  - `Hire`, `SIGNED_ON`, `hire_request(member, terms) -> (Generation, Fact)` and
    `hire_target(request) -> EntityId` live in `engines/base.py`: 24XX and Tunnel Goons carried
    the same lines, CLAUDE.md's threshold for one body (both reviews). 24XX's `hire`, `validate`
    and `advance` call them; nothing else in 24XX moves.
  - `RoomEngine.render_extension` gains `guidance` beside PLAN step 3's `answer`: the hire
    prompt's ENGINE GUIDANCE is `HIRE_GUIDANCE` (the three abilities and the point total), not
    `AUTHORING`'s "every npc needs hp", which contradicted the `AbilitiesDraft` answer (both
    reviews). `HIRING` is the intent alone.
  - `RoomWorld.carried_items(holder, item_ids)` takes the holder: a member's roll counts the
    items in the member's hands.
  - `level_options(actor.id)` for everyone, the player's own id included, since `require_actor`
    takes it (standing decision); the option args never say null.
  - `action_roll` refuses `actor_id == against`: a member is now both a legal actor and a legal
    target (review finding).
  - `rest` heals every party member, sheeted or not (PLAN step 4: "every member").
  - `_level_decision` is a free function: it reads only its `actor`.
- Refuted findings:
  - "`next_to_level` raises a bare `ValueError` for a sheeted actor outside the party": the
    actor comes from `require_actor`, which admits only the player or a living sheeted party
    member, so an absent actor is a bug, and CLAUDE.md says a bug is not caught. The one-chain
    rewrite offered as a cut was taken.
- Known and accepted: the `uv run aidm` smoke reaches the launcher (NiceGUI up), and the
  rewritten character file opens a Buried Keep game; a turn needs a CLI model spawn.
- Reviews: Fable and Opus (no `codex` on the machine).
