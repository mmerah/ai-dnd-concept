LONER 3E RULES

Loner 3e rules CC BY-SA Roberto Bisceglie, Zotiquest Games — lonersrd.zotiquestgames.com

WHAT AN ACTOR HAS

Every actor carries a one-line `concept`, `skills` (what they are good at), `frailties` (what
works against them), `gear` (their signature kit), and a `luck` pool of 6. Luck is not health: it
is how long someone can keep evading the worst before a conflict turns against them. These are
plain words, not numbers. Traits count as tags too: those on the actor, on what they carry, on the place
they stand, and on whoever stands there with them.

THIS ENGINE'S OWN EFFECT

Beside the world effects, this engine takes one more: `counter-change`, which moves an actor's
`luck` pool. `mode: adjust` shifts it by `amount`, clamped to the pool's bounds; `mode: spend`
pays a positive `amount` and refuses when the pool cannot cover it. Use it for two things only:
to put luck back to full once a conflict is behind them and they have had a breath, and to charge
a hazard that no conflict covers — a fall, a bad draught, a night out in the cold.

```json
{"op": "counter-change", "mode": "adjust", "entity_id": "player", "counter": "luck", "amount": 6, "why": "the fight is over and he has got his breath back"}
```

The sheet's `skills`, `frailties`, and `gear` change only through advancement. A lasting change to
what someone is — a condition taking hold, an injury, a fear — is a `trait-change`, and it counts
as a tag from the moment it lands.

THE PLAN

Your plan resolves at most one `action`, and this engine has one: a `question`. Leave `action`
null when nothing the player does is uncertain — a conversation, a look around, a walk to a room
they know; then the plan is whatever `effects` the turn plainly causes, and often none at all.

A QUESTION

Ask a `question` when the answer is uncertain AND both a yes and a no would change the fiction.
When in doubt, ask: if you can name a real cost a no would inflict, the attempt qualifies.
Reserve the null action for pure conversation and movement through safe, known ground. Fill it
from the acting actor:

- `actor_id` — the player, or an actor here with them.
- `question` — the closed question the dice answer, phrased so that yes is what the actor wants:
  "Does he get the seal open before the whispering finds him?"
- `leverage` — the tags that make this easier, each copied exactly as it is written on the sheet
  or on a trait in the scene. Write none unless a tag really applies; you cannot invent one.
- `trouble` — the tags that make this harder, copied the same way.
- `opponent_id` — set only when this question is one exchange of a conflict, naming the actor on
  the other side of it. Null for everything else.

Leverage and trouble cancel out: what is left decides whether the actor rolls an extra die, the
opposition does, or neither. More tags on a side never buys more than one die.

WHAT THE DICE DECIDE

The six outcomes are the labels your `branches` may use:

- `yes-and` — they get more than they asked for.
- `yes` — they get what they wanted.
- `yes-but` — they get it, and it costs or complicates something.
- `no-but` — they do not get it, but they keep something: a chance, a position, a warning.
- `no` — they do not get it, and the situation holds against them.
- `no-and` — they do not get it, and it gets worse.

Put in a branch only what the fiction adds at that outcome, and only for outcomes that need it:

- a lasting injury, status, or constraint — a `trait-change` with `mode: add` on that actor, with
  a concrete text saying what it stops them doing. `mode: remove` when the fiction ends it.
- something learned, opened, taken, or moved — the world effect that records it.

A CONFLICT

A conflict is any two sides set against each other: a fight, a chase, a hunt, an argument that has
to be won. Run one as a run of questions, one exchange each, with `opponent_id` naming who is
opposed. The engine then takes the luck itself — 3, 2 or 1 off the opponent as the answer runs
from `yes-and` down to `yes-but`, and 1, 2 or 3 off the asking actor as it runs from `no-but`
down to `no-and`. Never write a `counter-change` for a blow landed; it would be counted twice.

When an actor's luck reaches 0 they have lost that conflict, and the engine says so in SCENARIO
NOTES. Ask nothing more of it. Say how it ends for them — taken, broken, driven off, conceding —
which is a turn in the story rather than a death, and only then put their luck back to full.

Not every clash is a conflict. A single question settles a short scuffle, and no luck moves.

A TWIST DUE

When the dice tie often enough the engine rolls the twist itself — a subject and an action —
and the narration already showed it arriving. SCENARIO NOTES hands you the pairing the turn
after: spend that turn developing what arrived — what it set in motion, what it costs, what it
changes. It is a complication in the fiction, not a rule, and the pairing is yours to
interpret, never to reroll or replace.
