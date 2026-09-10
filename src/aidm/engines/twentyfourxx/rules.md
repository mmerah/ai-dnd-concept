# 24XX RULES

24XX rules (v1.4) are CC BY Jason Tocci. <https://24xx-srd.carrd.co/>

## The sheet

A skill on the sheet is a d8, a d10 or a d12. Any skill not on the sheet rolls a plain d6.
₡ marks credits. GEAR lists the items the player carries. A bulky item takes real space.
Each item breaks a set number of times before it is ruined. A hindrance is anything that slows
the actor down, such as an injury or a fear.

## When to roll

Call `roll` when the outcome of an action matters. Set `skill` when a skill applies.

Set `helped` when circumstances or an unhired party member help. The engine adds one d6.
Set `helped_by` when a hired member helps. They roll their own die of the same skill.
Set `hindered` when something slows the actor. The die drops to d4.

## Reading a roll

1 to 2 is a disaster. 3 to 4 is a setback. 5 or more is a success.

Set `risking_death` before the roll when the actor risks death. A disaster then kills them. A
setback then maims them.

## Gear and credits

Use the `gain_item` arm to add an item. Most items cost ₡1. Use the `drop_item` arm to lose one
for good. Use the `repair_item` arm to mend broken gear. Use the `spend` arm for everything else
the player pays for, such as a bribe, medical care or passage.

## Defending

Use the `defend` arm when the player says their gear takes a hit. One carried item or one ship
function breaks. The hit becomes a hindrance instead. Broken gear is useless until mended.

## Hindrances

Use the `change_hindrances` arm when the story gives the actor a hindrance or lifts one. A
hindered roll is a d4. The engine reads no hindrance itself. Cite the one that applies in
`hindered`, load included. More than one bulky item can hinder the actor.

## The ship

THE SHIP lists the crew's seven starship functions with their ids. Name a function as `item_id`
on the `defend` arm or the `repair_item` arm. An item or function marked harmless breaks with no
hindrance. Use the `ship_upgrade` arm to upgrade one function for ₡10. Say in the story what
the upgrade is.

## Jobs

Call `job` with `find` and `where` when the player looks for work. Use the `spend` arm to pay ₡1
for a second `find`.

Call `job` with `take` and `terms` when the player agrees to the work. THE JOB then holds its
terms. The engine refuses a second job while one is open.

Call `job` with `finish` when the story and the crew close the job. Give one `raises` entry
for the player and one for each living hired member. A job the player never takes needs no
`take` and no `finish`.

## A member's help

A member without a sheet helps through `helped` only.

## Hiring

A hired member then acts like the player. Name them in `actor_id` wherever a tool or arm offers
it.

## Death and succession

The player can die. The rules then ask the player which hired member leads. The chosen member
becomes the player and keeps their own name and id. The dead lead stays in the scene as a body.
The game ends when no hired member lives.
