# TUNNEL GOONS RULES

Tunnel Goons is © Nate Treme (Highland Paranormal Society), released under a Creative Commons 4.0 International License. <https://tunnelgoons.com/>

## The sheet

A goon has three abilities. Brute is smacking things and feats of strength. Skulker is sneaking,
aiming and balancing. Erudite is reading, perception and speaking. A goon also has Health and an
Inventory Score. A character dies at 0 Health.

An npc has Health alone, and that Health is also its Difficulty Score.

## When to roll

Call `roll` for an uncertain action that carries a real cost. Name only the items the actor
carries that plainly help.

## Reading a roll

The engine rolls 2d6, adds the ability, and adds 1 for each named item. It subtracts 1 for each
item the actor carries above their Inventory Score, on a Brute or Skulker roll only. Erudite is
never penalised this way. The total meets or beats the Difficulty Score for a success.

A dangerous action turns the margin into damage. The npc takes it on a hit. The actor takes it
on a miss. Every fight is dangerous. So is a trap, a fall or a hazard with no defender. Set
`dangerous` on each of those rolls.

## Changing the world

Call `reveal` only for what the player has plainly found. Call `kill` for a death
the story has settled. A helpless target needs no roll.

## Moving

WAYS OUT is the map the player can act on now. Only a way listed there leads anywhere. An
`unknown` way is one the player has not found, and their page does not show it. Walking it
with `move` makes it known. Do that only once the story has found it.

A locked way opens after a roll, or after the story uses a key the player carries. Then call
`unlock_way`, which also makes the way known to the player. Only then does `move` carry the
player through.

When WAYS OUT lead nowhere new, the page offers the player more map. There is nothing for you to
call.

## Resting

Call `rest` for a night in a safe spot. You judge what is safe.

## A member's help

A member without a sheet rolls nothing. Their help is a lower `difficulty` or a named item.

## Hiring

Name the hired member in `actor_id` on `roll`. `rest` heals them with the party.
