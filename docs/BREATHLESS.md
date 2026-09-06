# Breathless

A rules-light survival system: risky actions roll a skill or item die that steps down one size
after every roll, until Catch Your Breath resets them and adds a complication.

## Official sources

- SRD (v2.1, 2026-05-08 — the text this repo's engine is built from):
  <https://keeper.farirpgs.com/resources/fari-rpgs/breathless/breathless-srd/>
- Official itch.io page: <https://farirpgs.itch.io/breathless-srd>

## Licence and attribution

ORC License. The required credit, verbatim, wherever a copyright appears:

> This work is based on Breathless, product of Fari RPGs (https://farirpgs.com/), developed and
> authored by René-Pier Deshaies-Gélinas. This product is licensed under the ORC License available
> online at various locations including www.azoralaw.com/orclicense.

## Pack sources

No separate pack sources. The six skills and the rolling tables (jobs, weapons, long-range weapons,
locations, complications, missions) are all in the SRD at the page above, transcribed into
`packs/srd.json`.

## The tools

- `change_world` — reveal someone found, bring a cast member in or out of the scene, have someone
  join or leave the party, record a death, or drop an item from the backpack for good.
- `next_scene` — offer the player the way on at a stopping point; or say that they left this
  place, and the worldsmith writes where they land; or hand the worldsmith a complication to
  bring down on this place. The last two end the turn, and the player reads what arrives.
- `check` — roll a skill, a carried item, or the once-per-breath stunt on the 1–2 / 3–4 / 5+
  ladder; the die rolled wears one step, and an item reduced to d4 is gone. `actor_id` when a
  hired survivor acts instead of the player; `helped_by` names a hired survivor who rolls beside
  them, keeping the highest die.
- `catch_breath` — reset skills, the loot die and the stunt; stress stays; one d12 on the SRD's
  complication table goes to the master as a note.
- `change_stress` — what a complication costs, or what laying low somewhere secure clears.
- `use_med_kit` — spend the held med kit to clear 2 stress.
- `loot_check` — roll the loot die and step it down; a find opens the player's decision: take it,
  swap it for something carried, or take a med kit instead.
- `test_luck` — one die of the master's choosing, read on the check ladder, for a question about
  the world where nobody acts.
- `hire` — the player hires someone here to work; the worldsmith writes their sheet once the turn
  ends, and they join the party.

## Deviations in this repo

Every divergence between `src/aidm/engines/breathless/` and the official rules, with the reason it
stands. Nothing diverges silently: a rule not listed here is implemented as printed.

1. **Before We Start is not modelled.** The SRD opens with a content warning and a lines-and-veils
   step before play. This is a table procedure with no rule inside it; the app has no seat for it.
2. **An item reduced to d4 leaves for good.** The SRD's "breaks, gets lost, or fades away ... until
   it's made relevant again" has no procedure for the way back, so the engine models none.
3. **A med kit is a mark on the sheet, not an item.** The SRD counts it apart from the three
   carried items; here it is a flag, spent by `use_med_kit`, never dropped or swapped.

Four readings the SRD leaves open are settled without diverging from it: stress is a counter that
stops at 4 (the SRD names 4 as the threshold for vulnerable and nothing above it); the catch-breath
complication is one d12 on the SRD's own table, offered to the game master as a note rather than
forced into the story; a luck test is read on the check ladder, the SRD's "interpret the result as
you see fit"; and the SRD's "if an ally helps you, they also make a check" is played on the same
skill as the actor's, and an item or stunt check takes no helper, since the SRD names no die for one.

## Tool count

Fourteen counted: `change_world` and its five arms — `reveal`, `enter`, `leave`, `kill`,
`drop_item` — plus the eight named tools: `next_scene`, `check`, `catch_breath`, `change_stress`,
`use_med_kit`, `loot_check`, `test_luck`, `hire`; plus the pair, the two party arms of
`engines/base.py`, shared by every engine and not counted (PLAN decision 8).

## What the AI game master adds

Fields and tools that exist for the app around the rules, not the rules themselves.

- `known` and `hidden` — the told-fact gate: no unknown name reaches the narrator.
- `alive` and `kill` — the SRD leaves being taken out or dying to the table; the gate needs a flag,
  and a vulnerable participant's failed dangerous check hands the master that ruling as a note,
  naming whoever failed.
- `next_scene` and the scene's `offered` flag — a stopping point the player may stay at.
- The loot decision is the player's, asked through the app; the master leaves `granted` and
  `choice` null.
- A sheet on a cast member marks who has dice; the worldsmith writes it on `hire`.

## Where the rules live

Mechanics are in `src/aidm/engines/breathless/`; the scene machinery shared with the other
scene engines is `SceneEngine` in `src/aidm/engines/scenes/`. `packs/srd.json` — not this file —
is the transcription of record.
