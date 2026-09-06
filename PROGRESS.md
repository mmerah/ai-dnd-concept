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

- `src`: 8,507 → 8,831 lines (+324; target about +280). `engines/twentyfourxx/`: 740 → 1,044
  (cap 1,050). Tests: 469 → 494.
- Off-plan decisions:
  - `HIRE` lives in `engines/base.py` beside `SRD_PACK`: PLAN names no home, and 24XX and
    Tunnel Goons both read it.
  - `Crewmate.line()` adds a `gear:` row for any sheeted crewmate, the player included, so YOU
    PLAY FOR gains one line beside GEAR; GEAR keeps the ids and break state the arms need.
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
- Refuted findings, awaiting the maintainer's call:
  - "Tunnel Goons' `operations` admits a `hire` request nothing writes and `RoomEngine.advance`
    would play as a map extension; delete until Phase 5" (both reviews): PLAN step 1 says Tunnel
    Goons extends its operations with `HIRE` in this phase; kept as written.
  - "Gear belongs in `Crewmate.rows()`, so an interjecting member's YOUR SHEET names it" (Fable):
    PLAN step 2 puts gear in `line()`, and PLAN's fixture list keeps the narrator prompt still;
    gear in `rows()` would print the player's gear under THE PLAYER'S SHEET and twice in the
    panels. Kept in `line()`.
  - "`hire`'s description promises a refusal ('only when the story has not hired them') the code
    never makes" (Fable): the sentence is PLAN step 5's text, read as guidance to the master, not
    a code check; kept verbatim.
- Known and accepted: `Subject.rows` rides in every subject of `NarratorView`, so a Loner cast
  member's rows reach the view's data, though no narrator section prints them (PLAN step 8). The
  `uv run aidm` smoke reaches the launcher only; a turn needs a CLI model spawn.
- Reviews: Fable and Opus (no `codex` on the machine).
