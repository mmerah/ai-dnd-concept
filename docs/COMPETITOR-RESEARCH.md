# Competitor research

Date: 2026-08-28. Ten AI game master projects checked. Sources at the end.

## Where this project stands

| | claude-dnd-skill (148 stars) | ai-dnd-demo (ours, 2025) | aidm (ours, now) |
|---|---|---|---|
| Rules | 5e SRD, model adjudicates | 5e SRD, code | Loner / 24XX SRDs, code |
| Dice | script, prompt-enforced only | code | code, seeded, tested |
| State | markdown the model rewrites | JSON + event bus | one strict `Game` model |
| Hidden info | none, same transcript | prompt fence, leaks | type boundary in builtin mode |
| Model target | Claude only, ~170 KB prompt | gpt-oss-120b | weak, cheap, local; eval-gated |
| Size | ~30 scripts + 170 KB prompt | 42k LOC | 9.5k LOC, 252 tests |
| Why it wins | one-command install, TV display, GIFs, 5e brand | - | integrity |

The popular repo's open issues are the failures we designed against: the DM drifts from `state.md` after compaction, level-up ignores XP, crit damage is wrong.

Two risks stay open for us:

1. Play quality is unmeasured beyond the eval. Nobody outside the maintainer has played it.
2. Loner and 24XX have no brand pull. Maze Rats is closer to what people recognise.

## Landscape

- Commercial (AI Dungeon / Voyage, Hidden Door, Friends & Fables, StoryRoll): prompt-first. The model decides outcomes. Dice are decorative or app-tracked. No hidden world state. Hidden Door says so in its design: "the story is written only as far as it's been presented".
- Foundry VTT modules (Familiar, Loremaster): the VTT rolls, the model narrates and calls tools. Familiar admits it "cannot keep secrets it reads".
- Open repos closest to us: Daicer (seeded engine, model only summarises, stalled), NarrativeEngine-P (MIT, 90 stars, `knownBy` fact scoping), ai_rpg (149 stars, small models "vary").
- Nobody targets light SRDs. Nobody targets weak models seriously. Nobody enforces hidden info by type.

Stars measure install friction and demos, not play quality. See I7 in `IDEAS.md`.

## Features worth folding in

### Do now

1. **Re-read, do not trust the summary** (claude-dnd-skill). After context compaction the model must re-read state before it states a fact. For code mode this is one line in `.agents/skills/playing-aidm/SKILL.md`: "Before you state a trait, item, or thread note, call the state tool. Do not recall it." Fixes the drift their issue #7 reports.
2. **Session recap on resume** (claude-dnd-skill, NarrativeEngine-P). One Narrator call at game open: "Previously..." from the last N turns. This is the cheapest first step of L8 (long-game memory).

### Later

3. **`knownBy` on facts** (NarrativeEngine-P). Each fact records which NPCs and factions know it, so an NPC cannot use what it never learned. We have reveal-to-player; this is reveal-per-NPC. Only when NPC dialogue is a real feature.
4. **Run a published adventure at the table** (Familiar, claude-dnd-skill). We already author from PDF. Their edge is lazy lookup during play. That is L9, which leans skip.
5. **Second screen, TTS, display** (claude-dnd-skill). Marketing surface. That is L7 and I7. Do I7 first.

### Skip

- Player rolls their own dice (`roll_mode: players`). Breaks "code rolls everything" and only matters at a physical table.
- Many parallel specialised models per action (Friends & Fables claims ~12). We deleted the Interpreter for a 0% gain. Same lesson.
- Multiplayer. `ROADMAP.md` says no.

## Sources

- https://github.com/neuralinitiative/claude-dnd-skill
- https://github.com/Sagesheep/NarrativeEngine-P
- https://github.com/envy-ai/ai_rpg
- https://github.com/lguibr/daicer
- https://github.com/SergeyKhval/claude-dnd
- https://familiarvtt.com, https://loremastervtt.com
- https://fables.gg, https://hiddendoor.co, https://storyroll.app, https://aidungeon.com
- https://ianbicking.org/blog/2025/08/hidden-door-design-review-llm-driven-game
- `~/repos/ai-dnd-demo` (local, branch `feat/mvp2`, last commit 2026-07-22)
