STORY GROWTH

Three growth marks buy one change, and one only. Choose the single change the player's stated
intent asks for, and include the `growth` counter reset in the same proposal.

Every change names `entity_id: player` and carries a short `why`. The legal changes are:

- Raise one approach: `set-number` on `bold`, `subtle`, `clever`, or `empathetic`, one point
  higher than the sheet shows. No approach may pass +3.
- Gain an edge or a bond: a `tag-change` with `mode: add`, a stable hyphenated `tag_id`, and a
  `text` that begins `(edge)` or `(bond)` and says concretely what it lets the character do.
- Leave a burden behind: a `tag-change` with `mode: remove` on a tag whose text begins `(burden)`.
- Rewrite a burden: a `tag-change` with `mode: remove` on it and `mode: add` a changed one, keeping
  the `(burden)` mark.
- Become more resilient: a `counter-change` with `mode: adjust` on `stress` with a `maximum` one
  higher than the sheet shows and an `amount` of 0, moving the ceiling without moving the pool.
  The stress maximum may not pass 7.

Always end with a `counter-change` with `mode: adjust` on `growth` with `amount: -3`, which
spends the marks.

Propose nothing else: no new counters, no notes, no numbers the sheet does not already carry.
