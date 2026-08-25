# L2: Death is a reserved trait plus one `kill` command

Nothing can remove or retire an entity: `world.entities` is only ever appended (`state/model.py:228`)
and the nine core commands (`engines/world.py:107-145`) plus both engines' own add no counterpart.
Death is prose only — Loner's `defeat_note` tells the Director to "say how it ends" and mark it with
`add_trait` (`engines/loner3e/rules.py:172-178`), 24XX says "a risked death may mean death"
(`engines/twentyfourxx/director.md:33`) — so a killed rat keeps its sheet, its full luck pool, its
authored brief, and its slot in HERE WITH THE PLAYER forever.

## Decision

**Death is a reserved core trait id `dead`, written by one core command `kill`, with resolver teeth.**
`Trait` is already the engine-agnostic channel for lasting conditions, 24XX already models "out of
play" this way with its reserved `broken` trait (`twentyfourxx/rules.py:214,319,335`), and a trait
keeps the entity referenceable — which deletion cannot.

- Rejected, full deletion: `check_sheets` refuses mechanics naming a missing actor (`engines/core.py:299`) and the journal resolves every past speaker id (`app/runtime.py:80`, `ui/game.py:122`).
- Rejected, an `Entity.status`/`alive` field: a core field meaningless for items and locations that breaks every save and buys nothing a trait does not.
- Rejected, a prompt line telling the Director to `add_trait("dead")`: writable today but inert — nothing reads it, so the corpse stays a legal opponent and party member.
- Rejected, engine-owned auto-death at 0 luck: Loner rules that losing a conflict is not death (`loner3e/director.md:46`); death crosses both engines, so it belongs in core.

## Approach

`kill(actor_id)` is one resolver doing the whole cleanup in one call: set the `dead` trait, drop what
the body carried at its location so `move` can loot it, drop it from the party, one fact, one card.
Teeth: `require_actor_here` refuses a dead actor — one choke point covering both engines' rolls, help,
credits, traits and party joins — and `_check_party` rejects a dead companion at commit.

PC death reuses what exists. There is no end-state today: `SavedGame` has no ending, `Game` has no
flag, the only exit is `GameSession.restart` (`app/runtime.py:264`). `kill("player")` sets the trait;
`consume_answer`, the one function both turn entry points share (`turn/run.py:208`,
`harness/codemode.py:219`), refuses another segment; the composer greys out and the existing header
"restart" button (`ui/game.py:413`) is the way out. No new decision kind, no engine buy-in.

**Skipped: the state-keeper agent.** No evidence justifies it — the eval never reaches a death (no
`conflict_lost` or `dead` in any run of `evals/results/after-commands.json`), so "the Director forgets"
is unmeasured, and the repo already owns a zero-token cleanup channel: `world.pending_notes`, which
resolvers push and the Director is told to obey (`turn/prompts/director.md:17`) — see `defeat_note`.
Revive it only if, once `kill` ships and is named in the prompt, the new eval case in step 10 still
scores under ~70% over 9 repeats — and then try the cheaper rungs first: a `pending_notes` nudge from
the engine at 0 luck, then L4 few-shot. An extra LLM role costs latency, money and a new failure mode.

## Steps

Core state:

1. `state/entities.py` — add `DEAD: Slug = "dead"` beside `Trait`. One constant, not a table.
2. `state/actions.py` — add `kill(draft, actor_id) -> list[Fact]`: `require_kind(actor_id, "actor")`;
   refuse if already `DEAD`; refuse if not `PLAYER_ID` and not `draft.is_here(actor)`;
   `facts = draft.reveal(actor)`; `actor.traits.append(Trait(id=DEAD, name="Dead"))`; reparent each
   `world.children(actor_id, "item")` to `actor.parent_id` by direct field write with one summarising
   fact (not `Game.move`, whose trace says "the player left X"); `world.party.remove(actor_id)` if
   present; return `entity_fact(actor, "actor_killed", …, event=MechanicEvent(title=f"{actor.name} is
   dead", icon="skull"))`. Do not route through `require_actor_here` — step 3 would refuse it.
3. `state/actions.py:45` `require_actor_here` — refuse a `DEAD` actor **before** the `PLAYER_ID` early
   return (`actions.py:46-47`), not after the kind check: the player is returned unchecked today, so a
   dead PC would stay fully rollable for the rest of the turn its own `kill` landed in — step 5 only
   gates the *next* turn. Message: "…is dead; they take no further part." Ceiling: a corpse then takes no further `add_trait`/`remove_trait`, so
   there is no resurrection path and restart is the exit. One `ponytail:` comment names it.
4. `state/model.py:104` `_check_party` — reject a member carrying `DEAD`, so only `kill` can leave one.
5. `turn/run.py:286` `consume_answer` — first lines refuse when `draft.player.trait(DEAD)` is set.
   Covers the UI and the MCP harness from one place.

Engine: none. Sheets stay valid because the corpse is still an actor (`engines/core.py:293-300`) and
neither engine reads traits. Optional, only if the eval asks: name `kill` in `loner3e/rules.py:172`
`defeat_note` and `twentyfourxx/director.md:33`.

Prompt:

6. `engines/world.py` — `class Kill(Frozen)` with `actor_id: CheckedEntityId`, `_kill` via
   `apply_action`, and a `_world_command("kill", "Record that an actor has died. Their body and what
   they carried stay in the world.", …)` entry in `CORE_COMMANDS`.
7. `turn/prompts/director.md:33` — extend the post-roll consequence list to "…a death, a condition, an
   opened way…". One line, in a line the model already reads after every roll.

UI — a dead entity keeps its authored `brief`, since nothing may rewrite scenario canon; the marker is
added at render time:

8. `turn/context.py:302` `_headline` — render `(npc — dead)`. One edit reaching both the Director and
   the Narrator, which share `_scene_sections`; the Narrator already sees the trait via `entity_state`
   (`context.py:321-326`), so `VisibleScene` needs no change.
9. `ui/game.py:46` `scene_header` — prefix "Dead." to the brief in the "Here now" row. `ui/game.py:262`
   `_can_type` — false when the player is dead, with a "You died." line by the composer.
   `ui/panels.py:26-32` already badges player traits, so the sheet shows "Dead" for free.
10. `evals/turn_eval.py` — one Loner case `loner3e/finish-the-rat`: rat known and staged in the
    cloister, prompt "I bring the stone down and finish it", expectation `rat-dead`. Proof and trigger.

## Risk / size

~60 lines added across 8 files, nothing deleted; no new type, agent or dependency. Saves survive:
`dead` is an ordinary `Trait`, the schema is unchanged, and no existing save can hold a dead party
member. Stale saves are intentionally invalid anyway — no version field, no conversion path — so any
state that does trip step 4 fails loudly at load, which is correct. What breaks: the byte-identical
goldens. Steps 6 and 7 move the Director tool schema and instructions, so
`tests/core/fixtures/{schemas,instructions,prompts}` need `AIDM_GOLDEN_REGEN=1`, and the unit test for
`kill` belongs in `tests/core/test_actions.py`. One check that proves it: `kill` the rat, then
`roll_question` with it as `opponent_id` — the refusal must name it as dead, its dagger must be loose
at the cloister, and the same call must succeed before the kill. Offline, deterministic, one test.
