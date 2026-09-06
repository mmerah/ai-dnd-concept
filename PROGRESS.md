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
