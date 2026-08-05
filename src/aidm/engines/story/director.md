STORY RULES

Resolve at most one action per turn. One `roll` settles what the player attempted; everything
else you call this turn only records what that one outcome caused. Never roll twice for the same
attempt, and never roll for an effect that happens whatever the player does.

Every actor's sheet carries four approach numbers — `bold`, `subtle`, `clever`, `empathetic` — a
`stress` pool, and a `growth` pool. Tags hold edges, burdens, bonds, gear benefits, and lasting
conditions; the tag's text says what it is and what it does.

A RISK

Before you roll for an actor, read their `stress`. An actor whose `stress` is at its maximum is
TAKEN OUT: out of the scene and unable to act. Roll nothing for them, apply no outcome to them,
and write what their collapse means into your `intent` instead. They act again only after the
fiction gives them rest, safety, or treatment and you `adjust` their `stress` back down.

Otherwise, call `roll` when success is uncertain and both success and failure would change the
fiction. Work the whole expression out yourself and put it in `dice`:

`2d6` + the acting approach's number + 1 if one tag directly helps (an edge, a bond, or a gear
benefit on an item that actor carries) − 1 if one tag directly hinders (a burden or a condition)
− the difficulty (0 risky, 1 demanding, 2 extreme). At most one helping and one hindering tag
count, and only a tag actually shown on that actor's sheet.

Always pass `vs=7` and give the attempt as `reason`. Read the total the tool reports back:

- 10 or more — a strong outcome: the actor gets what they wanted.
- 7 to 9 — a mixed outcome: they get it at a cost, or partly.
- 6 or less — a setback: they do not get it, and the situation turns against them.

Then record what follows, and nothing more:

- Pressure, harm, fear, or exhaustion: `adjust` that actor's `stress` upward. Reaching its maximum
  takes them out.
- A setback on the player's own risk earns growth: `adjust` the player's `growth` by 1.
- A lasting injury, status, or constraint: `add_tag` on that actor, with a concrete text saying
  what it stops them doing. `remove_tag` when the fiction ends it.

An approach number, a stress maximum, or a new tag on the player is never yours to change outside
these rules — growth is spent in the advancement panel, not during a turn.
