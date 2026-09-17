## Ideas (in no particular order)

- [] 3: RAG? Scenario ingestion. .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Leaning skip: there is no embedding provider in the stack.
- [] 4: Re-implement a builtin mode and Re-implement an eval (see history)
- [x] 5: Multiple refactors: ponytail-audit, no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [x] 6: Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, Ideas completed/deleted
- [x] 7: De-aify the codebase
- [x] 8: lots of testing to identify gaps of MVP0
- [] 9: a new agent, state keeper, that adds/removes traits/tags, reveals, cleans up after the game master. Observed with small/cheap models: sometimes trait modifications are forgotten, sometimes a reveal is not done when it should have been done, ... Limited set of tools but could improve builtin-harness mode performance
- [x] 10: Rewrite: Skills, instructions, prompts. Easier english (ASD STE100). And content should be verified, not confusing, easy to understand. Particularly for instructions(prompts) since they describe how to actually play to the director (or whole session for codemode). Skills also need to be clearer, tell of everything, maybe indicate where (web link) to find SRD to reconciliate when needed? (but then harness need to authorize web fetch tool in some form, depend on the harness)
- [] 11: Demo path. One command and one GIF of a full Loner turn. The popular repos win on install friction and demos, not on play quality. This is the only thing they have that we do not.
- [] 13: Pack authoring: write a pack (skills, gear, tables) through the authoring loop, then a scenario or character that plays with it.
- [x] 14: The docs for each engine: have a template/format for each? Engines that are not implemented have the sections content as "unimplemented"?
- [x] 17: Real 3D dice. Done differently: the chips on the card tumble, click and wear the engine's colours; the physics canvas was tried and removed.
- [] 18: Maze Rats returns, self-contained on the same seam: the audited rules live in git at 2c3e8a5 and its docs/MAZE-RATS.md at 62f95c6; the return rewrites the world on its own strict actor/item/place model and fits 2,000 lines by dropping nothing the SRD prints.
- [] 19: A Pokémon-style engine with battles delegated to Pokémon Showdown. The point is the boundary: AIDM runs the RPG, Showdown runs the fight, neither reads the other's internals.
- [] 20: A meanwhile for the party. Both families have `party` and `leave_party`, and neither remembers where a member went or brings them back changed. It reuses the interjection code and the player understands it at once. Cut from the Meanwhile plan, which took the turn clock instead; the notes rated this the best value for the work.
- [] 21: The game page rebuilds the whole transcript on every turn, `chat()` and `journal()` both rendering from turn 1, measured at 1,603 NiceGUI elements and ~172 ms per refresh at turn 160; refused, being ~30–50 lines of new UI for a cost invisible below ~150 turns.
- [] 22: Speech-to-text for the composer, done right: a server-side transcription with its own provider key, the same shape as speech and illustration. The browser's own `SpeechRecognition` only works in Chrome over a secure context, which is why the mic button that used it is gone.
