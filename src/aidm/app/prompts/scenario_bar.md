## The bar

- Four or more locations, joined by `connected` relations into a place the player can move
  through. At least one way starts unknown, and at least one is `locked`.
- Two or more actors, at least one of them unknown at the start, holding something the player
  needs.
- At least one item that is secret: unknown, placed where finding it is a discovery.
- At least one thread, advanced by hooks that fire on `entity_discovered` for the entities that
  actually move it.
- A `detail.hook` on every entity that could lead somewhere.
- Names, briefs, and details specific enough to be unmistakable. No generic taverns, no
  placeholder names, nothing the premise did not earn.
- Never write a template. `"..."`, `TBD`, an empty `entities`, or any field left as a
  placeholder is a wrong answer; every field carries finished content.

Write canon, not prose for the player: the Narrator writes what the player reads.
