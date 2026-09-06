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
on a miss.

## Changing the world

Use the `reveal` arm only for what the player has plainly found. Use the `kill` arm for a death
the story has settled. A helpless target needs no roll.

## Moving

WAYS OUT is the map the player can act on now. Only a way listed there leads anywhere.

A locked way needs a roll, or a key applied with `change_world`, before it opens. Use the
`unlock_way` arm once the story has dealt with it. Only then does `move` carry the player
through.

When WAYS OUT lead nowhere new, the page offers the player more map. There is nothing for you to
call.

## Resting

Use the `rest` arm for a night in a safe spot. You judge what is safe.

## The party

A party member travels with the player from place to place. The player commands them and you
voice them. Use the `join_party` arm when someone here comes along. Use the `leave_party` arm
when they stop. A member without a sheet rolls nothing. Their help is a lower `difficulty` or a
named item. Never volunteer a member's action to soften a scene the player must face alone.

## Hiring

A sheet is for someone hired to work, never for one who only comes along.
Call `hire` when the player takes someone on to work. A hired member then acts like the player.
Name them in `actor_id` on `roll` and `level_up`. The `rest` arm heals them with the party.
