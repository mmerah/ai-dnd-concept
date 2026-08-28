# Loner 3e

A solo oracle-driven system: Chance d6 against Risk d6, six outcomes, a Twist Counter, Harm
resolved against Luck.

## Official sources

- Core rules SRD: <https://lonersrd.zotiquestgames.com/core/loner-3e.html>
- Site index: <https://lonersrd.zotiquestgames.com/>
- Document source (`content/core/loner-3e.md`): <https://github.com/zotiquestgames/lonersrd>
- The deleted extraction was taken from the v.3.0 page as it stood at commit `2946f2f` (2026-08-13);
  the site carries no version pin of its own, so re-read the live page rather than trusting that.
- Explanatory guide, covering Loner **2e** rather than 3e — the mechanics differ, e.g. it prints
  the equal result as *Yes, and...*, where 3e prints *Yes, but... +1 Twist*:
  <https://keeper.farirpgs.com/resources/zotiquest-games/loner/introduction/>

This file used to hold a near-verbatim extraction of the 3e core rules. It was deleted so that no
pack is ever transcribed out of a copy: build from the official page above. The old text is in git
history.

## Licence and attribution

Loner v.3.0 © 2025 Roberto Bisceglie, licensed under Creative Commons Attribution-ShareAlike 4.0
International (<http://creativecommons.org/licenses/by-sa/4.0/>). Site footer: © 2021-2026 Roberto
Bisceglie, Zotiquest Games. ShareAlike binds the adaptations — this repo's packs and `director.md`,
which carry it. The required attribution:

> Loner v.3.0 © 2025 Roberto Bisceglie. This work is licensed under the Creative Commons
> Attribution-ShareAlike 4.0 International License.

The SRD credits, as printed: [Recluse Engine](https://gravenutterance.itch.io/recluse) (CC BY 4.0)
by Graven Utterance and Tiny Solitary Soldier Oracle for the main resolution and scene mechanics;
[Freeform Universal](https://www.perilplanet.com/freeform-universal/) (CC BY 4.0) by Nathan Russell
for the character traits; harm mechanics from [6Q System](https://chaosmeister.itch.io/6-q-system)
(CC BY 4.0) by Marcus Burggraf; Tana Pigeon for [Mythic](https://www.wordmillgames.com/mythic.html);
S. John Ross for [Risus](https://www.risusrpg.com/); the Adventure Maker setup is inspired by
*The Instant Game* by Animalball Partners (2007).

## Pack sources

- `packs/srd.json` — written for this repo; only its twist columns come from the core rules
  page above (deviation 6).
- `packs/ap01-fantasy.json` — <https://lonersrd.zotiquestgames.com/adventure_packs/AP01_fantasy.html>.
- Eleven more adventure packs at
  `https://lonersrd.zotiquestgames.com/adventure_packs/APnn_<name>.html`, `AP01_fantasy` through
  `AP12_cyberpunk`; 2e copies live under `adventure_packs/legacy/`.

**Open question, carried from `README.md`:** the AP01 page carries no CC declaration at all — only
the site-wide footer "© 2021-2026 Roberto Bisceglie" — while the site index declares CC BY-SA 4.0.
It is treated as covered by the site's licence. One email to the publisher would settle it.

## Deviations in this repo

Every divergence between `src/aidm/engines/loner3e/` and the official rules, with the reason it
stands. Nothing diverges silently: a rule not listed here is implemented as printed. The SRD's
optional tools are not deviations by their own text: the Adventure Maker, the 5W+H frame and the
open-ended inspiration tables are offered "if you need inspiration" and stay authoring-time —
scenarios here are authored ahead of play; the next-scene mood roll is for when "you're unsure",
and deciding when to ask the Oracle is the player-seat judgment — the Director holds that seat.
Appendix A is by its own words a *version* of Loner that removes dice — an alternative game, not
a rule of this one.

1. **Goal, Motive and Nemesis are not sheet fields.** They map to the shared world: threads carry
   what the character is working toward, and entities carry who stands in the way. The
   SRD asks for them to emerge from play, and in this app play writes them to the world.
2. **Only the played character's sheet is built from the tables.** The SRD gives every character a
   Concept, Skills, Frailties and Luck — people, objects, vehicles and curses alike. A scenario may
   author those tables for any entity via `rules`; anything unauthored — an actor as much as an
   object, a vehicle or a curse — instead plays with a blank sheet at full Luck, and the traits it
   already carries stand in for the Concept, Skills and Frailties the SRD would have authored.
   A milestone is owed for each adventure a character was there for: `complete_chapter` credits
   the played character and everyone travelling with them whose rules are written, and the count
   lives on that sheet, so somebody who joins later is not owed the adventures they never played.
3. **A twist fires inside the question that rolled it.** The SRD has a twist interrupt the scene
   the moment it fires; here the tie that calls one is inside a resolved question, so the
   narration shows the twist arriving in that same turn rather than cutting the question short.
   The pairing reaches the Director in that call's own answer, and it develops what arrived in the
   same interaction.
4. **One Twist Counter, on the played character's sheet.** The SRD's counter belongs to the solo
   player, who is the only one rolling. Here any actor can be the subject of a question, so a
   single tally covers every roll — a tie anywhere moves the counter on the played character's
   sheet, and a successor picks the story up with their own.
5. **The Twist Counter is hidden from the player.** The SRD's solo player keeps the tally
   themselves; here it stays off every sheet view, paces the Director, and is never recited —
   rising tension shows only in the fiction.
6. **`packs/srd.json`'s starter tables are this repo's, not the SRD's.** The concepts, skills,
   frailties and gear in that pack are written for this repo; Loner 3e publishes no such tables.
   Only the twist subject and action columns are the SRD's, and the pack's `license` line already
   says so.

## Where the rules live

Mechanics are in `src/aidm/engines/loner3e/`. `packs/srd.json`'s twist columns — not this file —
are the transcription of record.
