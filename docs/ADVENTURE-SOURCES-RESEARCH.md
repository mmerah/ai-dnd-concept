# Adventure sources and progressive world expansion

Research note for a possible near-term redesign. This is direction, not an implementation plan.

## Conclusion

A full authored scenario should be optional, not the unit required to start a game. The runtime can
instead play any valid adventure state, whether it came from a complete scenario, part of a PDF,
or a premise with only an opening scene and a small truth kernel.

The simplest model is:

```text
Adventure = current GameState + CanonSource + ExpansionPolicy
```

- `GameState` holds everything already materialized in play.
- `CanonSource` supplies what may exist beyond that state: a premise, normalized PDF, curated
  package, or no external source.
- `ExpansionPolicy` is `closed`, `grounded`, or `generative`.

Existing `ScenarioWorld` content remains useful as a curated source, deterministic fixture, and
export format. It stops being mandatory product ceremony.

## Why the current Worldkeeper is insufficient

The current Worldkeeper runs after narration and can add only known entities and memories. It
cannot connect a new location, prepare hidden canon, create a thread or hook, or let the Director
move into a location that did not exist when the turn was planned. Meanwhile, the Director is
told not to invent named canon and the Narrator is told not to invent unsupported events.

Progressive expansion therefore belongs before the Director finishes its plan, while maintenance
and memory still belong after narration.

## Proposed roster and pipeline

```text
turn draft
    -> DIRECTOR
         -> optional expand_world(...) tool
              -> EXPANDER proposes a typed canon patch
              -> resolver validates and applies it to the turn draft
              -> tool returns stable ids to the Director
         -> Director completes its ordinary beat
    -> resolve effects and fire hooks
    -> NARRATOR
    -> narration-against-facts validation
    -> WORLDKEEPER
    -> commit
```

The Expander is a conditional authoring agent behind a Director tool, not a permanent top-level
stage. The tool may change only the disposable turn draft through deterministic resolver code. It
never writes committed state, saves, sources, or files. A later failure still discards the whole
turn.

The Director requests a narrative need rather than authoring its answer:

```text
kind: location
anchor_id: cloister
need: the place reached by the concealed descending stair
```

The Expander may return entities, placements, connections, threads, and hooks. The complete patch
is validated against the projected world and selected engine before it is applied. Newly added
actors receive valid engine mechanics through the existing seeding boundary.

Materializing private canon is not a fictional event. Internal `canon_materialized` trace facts
must not reach the Narrator. The Director still writes the `reveal`, `relation-change`, and `move`
effects that establish what the player actually experiences.

## Role boundaries

### Director

Plans the turn and optionally asks for missing canon. After expansion it uses the returned ids in
the same typed effects it uses today.

### Expander

Authors coherent canon tied to existing state. It owns new named entities and the topology,
threads, and hooks needed to make them playable. Hooks remain optional rather than boilerplate on
every expansion.

### Narrator

Writes only from resolved player-facing facts. A validator retries unsupported narration; later
roles do not silently repair it.

### Worldkeeper

Becomes a chronicler: it keeps durable memories and records lasting developments or genuinely new
storylines established by the turn. Structural consistency belongs to deterministic validation,
not to this role's judgment.

## Movement

Movement should always follow explicit topology. Remove the rule that a location with no exits can
reach any location. When travel crosses an unmaterialized frontier, the Director calls the
Expander, which atomically adds the destination and its connection before the Director reveals the
route or moves the player.

`connected` relations should be consistently undirected. Visibility and traversability should
remain separate: an unknown route may be revealed, while a known route may still be blocked.

## Source continuum

| Source | Initial state | Expansion |
| --- | --- | --- |
| Curated scenario | Dense authored world | Disabled or used only beyond its boundary |
| Partial adventure | Selected locations and truths | Fills intentional gaps |
| Ingested PDF | Opening slice plus normalized source records | Retrieves and materializes grounded canon |
| Premise | Opening scene, active situation, and truth kernel | Generates consistent canon progressively |
| Existing save | Whatever play has already established | Continues under its persisted source and policy |

A PDF ingestor should produce an immutable, normalized source with page provenance and
player-facing versus private visibility. It should not eagerly turn an entire book into one large
scenario or pass raw source text to the Narrator.

## First vertical slice

Prove one transaction before planning the full redesign:

1. The player attempts to travel somewhere not yet materialized.
2. The Director calls `expand_world` once.
3. The Expander creates one location and one valid connection to the current world.
4. The Director reveals the route and moves the player using the returned ids.
5. The Narrator receives only the resulting player-facing facts, and the final commit remains
   atomic.

If this works for a premise-backed source and a curated source, PDF ingestion becomes another
source implementation rather than another scenario-creation system.

## Open decisions

- Whether the post-turn role keeps the name Worldkeeper or becomes Chronicler.
- Whether an expansion may update existing private canon or only add new records.
- How source identity and revision are persisted so restart never regenerates an opening.
- Whether fully authored sources default to `closed` or allow optional generative continuation.
