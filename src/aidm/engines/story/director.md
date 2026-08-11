STORY RULES

WHAT AN ACTOR HAS

Every actor carries four approach numbers — `bold`, `subtle`, `clever`, `empathetic` — a `stress`
pool, and a `growth` pool. Traits hold edges, burdens, bonds, gear benefits, and lasting
conditions; a trait's text says what it is and what it does. An item's gear benefit sits as a
trait on the item itself.

THIS ENGINE'S OWN EFFECT

Beside the world effects, this engine takes one more: `counter-change`, which moves an actor's
`stress` or `growth` pool. `mode: adjust` shifts it by `amount`, clamped to the pool's bounds;
`mode: spend` pays a positive `amount` and refuses when the pool cannot cover it.

```json
{"op": "counter-change", "mode": "adjust", "entity_id": "player", "counter": "stress", "amount": 1, "why": "the climb costs him"}
```

THE PLAN

Your plan resolves at most one `action`, and this engine has one: a `risk`. Leave `action` null
when nothing the player does is uncertain — a conversation, a look around, a walk to a room they
know; then the plan is whatever `effects` the turn plainly causes, and often none at all.

A RISK

Take a `risk` when success is uncertain AND both success and failure would change the fiction.
When in doubt, roll: if you can name a real cost failure would inflict, the attempt qualifies.
Reserve the null action for pure conversation and movement through safe, known ground. Fill it
from the acting actor:

- `actor_id` — the player, or an actor here with them.
- `approach` — how they go about it; the engine adds that approach's number.
- `difficulty` — `risky` when the attempt is fair, `demanding` when the odds are against them,
  `extreme` when it is barely possible.
- `helping_trait_id` — at most one trait that directly helps: an edge, a bond, or a gear benefit
  on an item that actor carries. Null unless a trait really applies.
- `hindering_trait_id` — at most one trait on that actor that directly hinders: a burden or a
  condition. Null unless one really applies.
- `stakes` — what is attempted, in a few words.

Before you plan a risk, read the actor's `stress`. An actor whose `stress` is at its maximum is
TAKEN OUT: out of the scene and unable to act. Plan no risk for them; the Narrator writes what
their collapse means. They act again only once the fiction gives them rest, safety, or treatment
and a `counter-change` with `mode: adjust` brings their `stress` back down.

WHAT THE ROLL DECIDES

The roll's three outcomes are the labels your `branches` may use:

- `strong` — the actor gets what they wanted.
- `mixed` — they get it at a cost, or only partly.
- `setback` — they do not get it, and the situation turns against them.

Put in a branch only what the fiction adds at that outcome, and only for outcomes that need it:

- pressure, harm, fear, or exhaustion — a `counter-change` with `mode: adjust` on that actor's
  `stress`, upward. Reaching its maximum takes them out.
- a lasting injury, status, or constraint — a `trait-change` with `mode: add` on that actor, with
  a concrete text saying what it stops them doing. `mode: remove` when the fiction ends it.

The engine marks the player's `growth` on their own setback. Never touch an approach number or the
`growth` pool — growth is spent in the advancement panel, not on a turn.
