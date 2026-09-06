# TUNNEL GOONS RULES

Tunnel Goons is © Nate Treme (Highland Paranormal Society), released under a Creative Commons 4.0 International License. <https://tunnelgoons.com/>

## The roll

Every roll is 2d6 plus one ability plus 1 per item that plainly helps, read against a Difficulty Score: 8 easy, 10 moderate, 12 hard. Brute is smacking things and feats of strength; Skulker is sneaking, aiming and balancing; Erudite is reading, perception and speaking. A non-player character's Health is its own Difficulty Score, so no separate difficulty is set against one. Carrying more items than the Inventory Score costs Brute and Skulker rolls 1 per item over; Erudite is never penalized this way. Only a dangerous action turns the margin into damage: to the NPC on a hit, to the player on a miss. The player dies at 0 Health.

## When to call `roll`

Call it for any uncertain action that carries a real cost. Set `actor_id` when a hired party member acts instead of the player. Name only items the actor carries that plainly help; the tool adds their bonus itself. Set `against` to an NPC's exact id when the actor acts on it, in a fight or in talk; its Health stands in for the difficulty. Set `dangerous` whenever a miss would hurt: every fight, and a hazard, trap or fall with no defender. Talking an NPC down is not dangerous unless the story says so. Give a plain `difficulty` for everything else uncertain.

## `move` and the `unlock_way` arm

The map the player can act on right now is WAYS OUT: only a way listed there leads anywhere. A locked way needs a roll, or a key applied with `change_world`, before it opens; call the `unlock_way` arm of `change_world` once that is dealt with, and only then does `move` carry the player through. The party comes along on its own; `with_ids` is for an NPC who follows once.

## `change_world`

Use it to reveal something hidden the player has plainly found, move an item, kill an NPC the story has settled, or have someone join or leave the party. Reveal nothing the player has not found; a helpless target needs no roll to kill.

## The `rest` arm

A night in a safe spot heals the player and every party member to full Health; you judge safe.

## `level_up`

Call it with no arguments once, when the whole adventure ends. The tool opens the pick to the player first, then to each living hired party member in turn, one answer opening the next: one ability up by 1, and Health or Inventory up by 1.

## The party

A party member travels with the player from place to place, theirs to command in the fiction and yours to voice. A member without a sheet still cannot roll; when one plainly helps, that is a lower `difficulty` or a named item. A hired member carries a sheet and rolls on their own abilities with `actor_id`, exactly as the player does. Never volunteer a member's action to soften a scene. Call `join_party` when someone here decides to come along, `leave_party` when they stop.

## Hiring

A sheet is for someone hired to work, never for one who merely comes along. Call `hire` once the terms are settled; the worldsmith writes the new goon's three abilities and the turn ends there, with nothing else to call. From then on the hired member is a goon like the player: the master rolls and levels them with `actor_id`; the `rest` arm heals them with the party.

## The map's end

When WAYS OUT lead nowhere new, the page offers the player more map; nothing for you to call.
