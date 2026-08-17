# AI Dungeon Master UI concept

This is a throwaway, presentation-only prototype. It does not import or mutate the real game state and it does not call a model. Everything is mock data and browser-side interaction.

## Run it

Open `index.html` in a browser. If a browser policy blocks local `file:` pages, serve the folder with any static server, for example:

```bash
python -m http.server 8088
```

Then open `http://localhost:8088`.

## Suggested team walkthrough

1. Start on **Play**. The scene image and narration are the primary surface; character mechanics, people present, thread, exit and inventory are contextual rails rather than debug panels.
2. Click the **engine badge** in the top bar. This is deliberately marked as mock-only. It shows how the same fiction can render Loner 3e or 24XX mechanics without forcing both engines into one stat schema.
3. Submit an action such as **Inspect the loose flagstone**. The prototype inserts an engine-specific resolution card and a mock narration result.
4. Open **Hero**. The shared portrait, traits and inventory stay stable while the mechanical sheet changes with the engine. The advancement card also adapts.
5. Open **Journal** and **World**. These are player-facing replacements for trying to understand the game through raw state.
6. Open **Home**. It demonstrates scenario + engine + compatible-character selection, saves, and a redesigned engine-specific character creator.
7. Open **Create**. Walk through Source -> World draft -> Engines -> Media -> Review. Source can be a premise or an ingested PDF; output remains shared authored world data plus validated per-engine overlays.
8. Open **Dev** in the left rail. Trace, raw state, the role pipeline, and engine-private mechanics still exist, but they are intentionally outside the normal player experience.

## What the prototype is trying to test

- Is the game more compelling when the current scene, people and story are visually dominant?
- Does an engine-neutral shell with engine-specific mechanic components feel coherent?
- Is it clear which information is player-known versus private canon?
- Do portraits, scene art and icons feel like part of the fiction rather than decorative attachments?
- Should advancement live on the character sheet instead of being a generic engine tab?
- Is a journal + known-world view a better mental model than a raw state panel?
- Does the scenario-creator flow make premise/PDF ingestion feel like authoring rather than runtime magic?

## Current features represented

- Scenario / engine / compatible character selection
- Saved games
- Engine badge
- Engine-specific character creation
- Turn input and narration history
- Loner 3e: concept, skills, frailty, gear, Luck, Chance/Risk resolution, advancement
- 24XX: specialty, origin, skill dice, Credits, help/hindrance-shaped resolution, advancement
- Shared traits and inventory
- Current location, entities here, known exits
- Threads and durable memories
- Trace, role pipeline and raw state inspection

## Future features represented

- Stable actor portraits
- Location / scene images
- Compact entity icons
- Media generation / regeneration affordances
- Known-world map/catalogue
- Player journal / recap
- Scenario creation from a premise
- Scenario creation from an ingested PDF
- Shared-world review with private-canon separation
- Engine compatibility / overlay review
- Media planning with hidden-content safeguards

## Deliberate mock-only behavior

- Switching engines in an active game is a presentation control, not a proposed save feature.
- Dice and narration are deterministic canned examples.
- Media is drawn with local CSS/SVG placeholders; no image service is called.
- The scenario creator does not parse PDFs or write authored JSON.
- The developer inspector shows illustrative trace/state, not live data.

## Implementation direction if the concept is accepted

Keep the UI as a renderer of typed session state. Add player-facing view models at the app/UI boundary rather than moving domain logic into NiceGUI. Treat each engine as the owner of its mechanic widgets/sheet presentation, while shared fiction surfaces consume engine-agnostic scene/world data. Keep Trace/State as developer tooling, not as the information architecture for play.
