STORY RULES

THE SHEET

Every actor's sheet carries four approach numbers — `bold`, `subtle`, `clever`, `empathetic` — a
`stress` pool, and a `growth` pool. Tags hold edges, burdens, bonds, gear benefits, and lasting
conditions; a tag's text says what it is and what it does. Items an actor carries have sheets of
their own, and a gear benefit sits as a tag there.

THE PLAN

Your plan resolves at most one `action`, and this engine has one: a `risk`. Leave `action` null
when nothing the player does is uncertain — a conversation, a look around, a walk to a room they
know. Then the plan is whatever `effects` the turn plainly causes, and often none at all.

A RISK

Take a `risk` when success is uncertain AND both success and failure would change the fiction.
When in doubt, roll: if you can name a real cost failure would inflict, the attempt qualifies.
Reserve the null action for pure conversation and movement through safe, known ground.
Fill it from the acting actor's sheet:

- `actor_id` — the player, or an actor here with them.
- `approach` — how they go about it; the engine adds that approach's number.
- `difficulty` — `risky` when the attempt is fair, `demanding` when the odds are against them,
  `extreme` when it is barely possible.
- `helping_tag_id` — at most one tag that directly helps: an edge, a bond, or a gear benefit on an
  item that actor carries. Null unless a tag really applies.
- `hindering_tag_id` — at most one tag on that actor's own sheet that directly hinders: a burden or
  a condition. Null unless one really applies.
- `stakes` — what is attempted, in a few words.

Before you plan a risk, read the actor's `stress`. An actor whose `stress` is at its maximum is
TAKEN OUT: out of the scene and unable to act. Plan no risk for them; the Narrator writes what
their collapse means. They act again only once the fiction gives them rest, safety, or
treatment and an `adjust-counter` brings their `stress` back down.

WHAT THE ROLL DECIDES

The engine rolls the dice, compares them, and applies the outcome. You never state a result. Its
three outcomes are the labels your `branches` may use:

- `strong` — the actor gets what they wanted.
- `mixed` — they get it at a cost, or only partly.
- `setback` — they do not get it, and the situation turns against them.

Put in a branch only what the fiction adds at that outcome, and only for outcomes that need it:

- pressure, harm, fear, or exhaustion — `adjust-counter` on that actor's `stress`, upward. Reaching
  its maximum takes them out.
- a lasting injury, status, or constraint — `add-tag` on that actor, with a concrete text saying
  what it stops them doing. `remove-tag` when the fiction ends it.

The engine keeps the bookkeeping you must never write: it rolls, it decides which outcome happened,
and it marks the player's `growth` on their own setback. An approach number, a `stress` maximum, and
the `growth` pool are never yours to touch — growth is spent in the advancement panel, not on a turn.
