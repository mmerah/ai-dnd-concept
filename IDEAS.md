## Ideas (in no particular order)

- [] 1: Sounds/Voices. app/media.py is the template.
- [] 3: RAG? Scenario ingestion. .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Leaning skip: the source cap already swallows a 76-page adventure whole, and there is no embedding provider in the stack.
- [] 4: Re-implement a builtin mode and Re-implement an eval (see history)
- [] 5: Multiple refactors: ponytail-audit, no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] 6: Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, Ideas completed/deleted
- [] 7: De-aify the codebase
- [] 8: lots of testing to identify gaps of MVP0
- [] 9: a new agent, state keeper, that adds/removes traits/tags, reveals, cleans up after the game master. Observed with small/cheap models: sometimes trait modifications are forgotten, sometimes a reveal is not done when it should have been done, ... Limited set of tools but could improve builtin-harness mode performance
- [] 10: Rewrite: Skills, instructions, prompts. Easier english (ASD STE100). And content should be verified, not confusing, easy to understand. Particularly for instructions(prompts) since they describe how to actually play to the director (or whole session for codemode). Skills also need to be clearer, tell of everything, maybe indicate where (web link) to find SRD to reconciliate when needed? (but then harness need to authorize web fetch tool in some form, depend on the harness)
- [] 11: Demo path. One command and one GIF of a full Loner turn. The popular repos win on install friction and demos, not on play quality. This is the only thing they have that we do not.
- [] 13: Pack authoring: write a pack (skills, gear, tables) through the authoring loop, then a scenario or character that plays with it.
- [] 14: The docs for each engine: have a template/format for each? Engines that are not implemented have the sections content as "unimplemented"?
- [] 16: Non-solo play, with NPCs first. The player leads a small crew: crew members can roll, get hurt, and share things like the 24XX ship. Today only the player rolls and no companion is gained, so it needs its own plan. It would also close most 24XX deviations in `docs/24XX.md`: an ally who helps rolls their own die, the crew's shared ship and its systems come in, and a dead operator can be replaced by a crew member instead of ending the game.
- [] 17: Real 3D dice: a physics canvas; the CSS tumble is the cheap version.