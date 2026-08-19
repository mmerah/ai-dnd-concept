# Opinion 2 — accepted structural refactors

Four breaking refactors, in dependency order. Preserve the focused Worldkeeper role: combining
roles is out of scope because each agent should keep one job. Every step ends green on the full
verification suite. Save-shape changes bump `SAVE_VERSION`; stale saves are refused, not migrated.

## 1. Separate runtime game state from saved JSON — 1–2 days

`GameState` currently serves as runtime aggregate, persistence schema, transaction mechanism, and
container for both opaque `mechanics: JsonValue` and cached parsed `_live_mechanics`. Replace it
with a runtime `Game` holding the engine's validated mechanics model and a strict `SavedGame` DTO
holding serialized mechanics. The engine decodes once on load and encodes on save.

Make the transaction lifecycle explicit at the same time: create one draft for a turn, mutate only
that draft, validate the whole result once, and replace committed state only after every role
succeeds. Preview/model-retry checks continue to use disposable copies. Remove `mechanics_as`,
`set_mechanics`, `_flush_mechanics`, and intermediate commit-then-draft cycles.

## 2. Use one collection shape for worlds — 4–8 h

Authored worlds use tuples while runtime state and authoring drafts use keyed dictionaries, causing
parallel conversion and key/id consistency code. Use ordered lists throughout `ScenarioWorld`,
`WorldState`, saves, and `WorldDraft`; validate unique ids at boundaries and centralize linear
`find`/`require` helpers. Current worlds have fewer than ten entities, so lookup cost is negligible.

This should remove `ScenarioWorld.world`, dictionary reconstruction, key-versus-id validation, and
five parallel collection paths without introducing an index/cache abstraction.

## 3. Reorganize around responsibilities — 4–6 h, after 1–2

Use the resulting seams rather than enforcing a fixed directory tree. Split authored-content I/O
from save/trace persistence; move scenario authoring out of `app`; split session behavior from the
composition root; and move runtime game state away from the module holding world records.

Keep engine schemas beside their resolvers, keep NiceGUI confined to `ui`, and do not create a
generic `models/` directory or new repository/service/protocol layers merely for symmetry.

## 4. Simplify Director schemas without changing rules — 2–4 h plus live probes

Flatten each engine's nested `WorldOp` effect union so its discriminator maps directly to concrete
operations. This changes only JSON Schema structure; effect models and resolver behavior remain
the same.

Further engine-specific changes are conditional on exact SRD parity. Removing Loner 3e's redundant
`Question.op` is acceptable only if its closed-question, Chance/Risk, position, conflict, and twist
behavior is unchanged. Reshaping 24XX `Attempt` assistance is acceptable only if hindrance, one
help die, helper skill, pool construction, and highest-die resolution remain unchanged. Verify both
against `docs/LONER-3E.md` and `docs/24XX.md`, update golden schemas, then live-probe each role.
