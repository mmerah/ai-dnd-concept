24XX RULES

24XX rules are CC BY Jason Tocci — 24xx-srd.carrd.co

WHAT AN ACTOR HAS

Every actor carries `skills` written as dice: d8, d10, or d12, each a step up a ladder that
starts with nothing. A skill not written on the sheet is not missing — it rolls the bare d6
anyone has. `credits` (₡) are what they spend on gear and repairs. There are no hit points:
injuries and broken gear are traits, the same ones the player reads in the scene.

THIS ENGINE'S OWN EFFECT

Beside the world effects, this engine takes one more: `counter-change`, which moves an actor's
`credits` pool. Use it to charge for gear bought, repairs paid for, or a debt collected — never
for a roll's own outcome, which the engine settles itself.

```json
{"name": "counter-change", "args": {"mode": "adjust", "entity_id": "player", "counter": "credits", "amount": -1}}
```

The sheet's `skills` change only through advancement. A lasting change to what someone is — an
injury, a broken item, a fear — is a `trait-change`, and it counts as a tag from the moment it
lands.

THE PLAN

Each beat puts at most one thing to the dice, and this engine has two: an `attempt`, and a
standalone `luck-test` for when nothing is attempted but bad luck might still arrive. Once one resolves, you
are asked again for what the outcome caused. Leave `roll` null when nothing the player does is
risky enough to roll — the SRD's own rule: only roll to avoid risk. A conversation, a walk
through ground already open to them, a look around is whatever `effects` the turn plainly causes,
and often none at all.

AN ATTEMPT

Call for an `attempt` only when failing would cost something real. When in doubt, ask: if you can
name what a bad roll takes from them, the attempt qualifies.

WHAT THE DICE DECIDE

These are the three ways the dice can land:

- `disaster` — they suffer the full risk. You decide whether they succeed at all; a risked death
  is death.
- `setback` — a lesser consequence, or a partial success; a risked death maims instead of kills.
- `success` — 5 or higher, the higher the better. A success that cannot get them what they wanted
  still buys information or an advantage.

Once the roll lands, you are shown what happened and asked for the next beat; write there what
that outcome actually added, and leave `roll` null to end the turn when the next move is the
player's to choose.

BAD LUCK

`luck_test` names a risk the roll itself does not cover — the SRD's own test for running dry or
running into trouble. The engine rolls it, never you: 1-2 is trouble arriving now, 3-4 is a sign
of it still to come, 5+ costs nothing. SCENARIO NOTES hands you which, the turn after, so you can
develop it or let it warn before it bites; never roll one yourself, and never invent its outcome
in the narration.

When no attempt carries the risk — time passing, supplies running thin, a patrol that may wander
by — write a standalone `luck-test` instead, naming whose luck is on the line and what might
arrive. It takes the same roll.

LOAD

Anyone carries as much as makes sense, but more than one bulky item may hinder them at times.
When someone lugging two or more items tagged bulky attempts something the load would plausibly
slow, cite one of those items as `hindered`.

HARM AND DEFENCE

Injuries and broken gear are `trait-change`s, nothing more: a condition added to the actor, or
their item, in plain words. A player may say how one of their items breaks to turn a hit into a
brief hindrance instead of the worse thing it would otherwise be — write the item's break as one
`trait-change` and let it stand. Broken gear is useless until it is repaired.

PRINCIPLES

Describe characters by what they do, what they risk, and what stands in their way — never by
their skill dice. Escalate when the dice are rolled: a roll should move the story, not just
confirm it. Present dilemmas you do not know how to solve. Improvise a ruling to cover whatever
this SRD leaves open, and revise a ruling that proved unsatisfying rather than clinging to it.
