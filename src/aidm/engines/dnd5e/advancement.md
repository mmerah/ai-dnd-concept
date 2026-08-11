D&D 5E LEVEL-UP

The offer is the player's next class level, and the picks are the features it lists. Take each
granted feature once and exactly one option out of each set of alternatives — one fighting style,
never two — until the proposal makes the number of picks the offer asks for.

Every change names `entity_id: player` and carries a short `why`. A proposal carries:

- `add-ref` for each pick.
- `set-number` on `level`, one higher than the sheet shows.
- `set-number` on `proficiency-bonus` whenever the level's text gives a higher one.
- A `counter-change` with `mode: adjust` on `hp`, with a `maximum` raised by the average of the
  class hit die plus the character's Constitution modifier — d6 4, d8 5, d10 6, d12 7, before the
  modifier, and at least 1 in total — and an `amount` equal to that same total, so the character
  gains the hit points as well as the room for them.
- A `counter-change` with `mode: adjust` on each `slot-N` whose maximum the level raises, with the
  new `maximum` and an `amount` that fills what was added.
- `grant-counter` for a pool a newly picked feature brings with it, with its `recharge` named as
  `short-rest` or `long-rest`.
- A `tag-change` with `mode: remove` on `advancement-ready`, which is what spends the level-up.

An ability score improvement is `set-number` raising two ability scores by 1 each or one by 2, never
above 20.

Propose nothing else: no number the sheet does not already carry, no notes, and no tag beyond
removing `advancement-ready`.
