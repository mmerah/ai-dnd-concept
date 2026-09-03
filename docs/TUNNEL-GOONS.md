# Tunnel Goons

A one-page 2d6 game by Nate Treme (Highland Paranormal Society): roll 2d6, add one ability and one
point per relevant item, meet a Difficulty Score. On a dangerous action the margin is the damage.

## Official sources

- The SRD, the author's own reference text: <https://tunnelgoons.com/srd>. It carries the 1.1
  rules. Read 2026-09-01.
- Official downloads on itch.io: <https://natetreme.itch.io/tunnelgoons>. Files: `Tunnel Goons
  1.2.pdf` (2019-10-03), `Tunnel Goons 1.1.pdf` (2019-08-06), a print layout, two character
  sheets, and Portuguese, Italian and Spanish translations. Both rules PDFs were read 2026-09-01.
  Where the 1.1 PDF and the SRD page differ: the PDF says "Level up at the end of a game
  session" (SRD page and 1.2: "every 2 game sessions"), and "the endangered participant takes"
  the damage (SRD page and 1.2: "damage inflicted"); the SRD page otherwise prints 1.1's
  creation (3 points, choose 3 items) with 1.2's rules text.
- Devlog for 1.2: <https://natetreme.itch.io/tunnelgoons/devlog/102800/tunnel-goons-12>. The only
  change from 1.1 is character creation: random tables with an implied setting, and 2 ability
  points instead of 3. The author confirms in the comments that 2 is deliberate, "to make players
  rely more on equipment". 1.1 stays available as "the original version".
- Site index and hacks list: <https://tunnelgoons.com/>.
- The game was first printed inside the zine *The Eternal Caverns of Urk*.

This file holds no rules text. Build from the SRD page above, not from a summary of it.

## Licence and attribution

Every page says "released under a Creative Commons 4.0 International License" and nothing more.
The itch.io page quotes the deed's "Share" and "Adapt ... for any purpose, even commercially"
lines, which match CC BY 4.0, but no page links the deed or names the variant. Neither rules PDF
carries a licence line at all (1.1: "Created by Nate Treme. Find more RPG stuff at NATETREME.COM";
1.2: "by Nate Treme"), so the itch.io statement is the licence of record and the attribution
below is final. One email to the author would settle the variant.

Attribution, as `rules.md` carries it:

> Tunnel Goons is © Nate Treme (Highland Paranormal Society), released under a Creative Commons
> 4.0 International License. <https://tunnelgoons.com/>

## Pack sources

None. The starting item list is in the SRD's character creation.

## The tools

- `change_world` — reveal something found, move an item, or kill an npc.
- `move` — carry the player, and any NPCs named in `with_ids`, through an unlocked way listed in WAYS OUT.
- `unlock_way` — open a locked way once the story has dealt with it.
- `action_roll` — 2d6 plus an ability and helpful items, against a Difficulty Score or an npc.
- `rest` — heal the player to full Health in a safe spot.
- `level_up` — raise one ability and either Health or Inventory by 1, once per adventure in a one-shot, once per job in a campaign.

The three `change_world` arms are `engines/rooms/tools.py`'s, shared by every room engine, and count here as before.

## Deviations in this repo

1. Levelling up is an end-of-adventure step the master calls once per adventure in a one-shot and once per job in a campaign. The SRD page says "every 2 game sessions", the 1.1 PDF "at the end of a game session"; an adventure is the closest thing this app has to a session.

## What the AI game master adds

Every entity has `known`, and a `Way` is known once the player has walked it: what the player has found stays legible turn to turn without the master having to restate it. Every non-player character — friend or foe — is one shape, exactly as the SRD prints: an id, a name, a Health that is also its Difficulty Score, and whether it is still alive. Only the player has abilities, and only the player rolls; the map's extension bar lets the worldsmith write a new region once the authored map is fully walked. `kill` ends a helpless npc outright, no roll needed.

## Where the rules live

`src/aidm/engines/tunnelgoons/`, instructions in `rules.md`.
