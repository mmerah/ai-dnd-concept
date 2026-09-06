# BREATHLESS RULES

This work is based on Breathless, product of Fari RPGs (https://farirpgs.com/), developed and
authored by René-Pier Deshaies-Gélinas. This product is licensed under the ORC License available
online at various locations including www.azoralaw.com/orclicense.

## The sheet

A sheet has six skills: Bash, Dash, Sneak, Shoot, Think and Sway. As written, three sit at d4,
one at d6, one at d8 and one at d10. A worn skill never rises above its written rating.

BACKPACK holds up to 3 items, each with its own die, and one med kit. The loot die starts at
d12. Stress runs 0 to 4. At 4 stress the actor is vulnerable. A stunt is one extraordinary
action at d12, and it stays spent until the actor catches their breath.

## When to roll

Call `roll` for an action with a real cost. Do not roll for what the story has already settled.

## Reading a roll

1 to 2 is a fail. 3 to 4 succeeds with a complication. 5 or more succeeds outright.

The die that rolled wears one step down, from d12 to d10 to d8 to d6 to d4. An item worn to d4
is gone. It breaks, goes missing, or fades from the story. With `helped_by`, both actors wear that
skill one step down.

## Catching breath

`catch_breath` does not clear stress. Bring its complication into the story.

## Stress and the med kit

Use the `change_stress` arm for what a complication costs the actor, and for what laying low
somewhere secure clears. Use the `use_med_kit` arm to spend a held med kit. The med kit clears 2
stress and no other arm spends it.

## Scavenging

`loot_check` is the only way an item enters the backpack.

## The party

A party member travels with the player from scene to scene. The player commands them and you
voice them. Use the `join_party` arm when someone here comes along. Use the `leave_party` arm
when they stop. A member without a sheet helps in the story alone and rolls nothing. Never
volunteer a member's action to soften a scene the player must face alone.

## Hiring

A sheet is for someone hired to work, never for one who only comes along.
Call `hire` when the player takes someone on to work. A hired member then acts like the
player. Name them in `actor_id` on `roll` and `catch_breath`, and on the `change_stress`,
`use_med_kit` and `drop_item` arms. Name them in `helped_by` to roll beside the actor.
`loot_check` stays the player's.
