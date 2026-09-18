# 24XX RULES

24XX rules (v1.4) are CC BY Jason Tocci. <https://24xx-srd.carrd.co/>

## The sheet

A skill on the sheet is a d8, a d10 or a d12. A skill that is not on the sheet rolls a plain d6.
The sign ₡ marks credits. GEAR lists the items that the player carries. A bulky item takes much
space. Each item breaks a set number of times before the item is destroyed. A hindrance is a
thing that slows the actor, for example an injury or a fear.

## When to roll

Call `roll` when the result of an action is important. Set `skill` when a skill applies.

Set `helped` when the conditions help, or when a party member who is not hired helps. The engine
adds one d6. Set `helped_by` when a hired member helps. That member adds one d6 too. Set
`hindered` when something slows the actor. The die then becomes a d4.

## Reading a roll

- 1 to 2 is a disaster. The actor takes the full risk. You decide if the actor succeeds at all.
- 3 to 4 is a setback. The actor takes a smaller consequence, or gets a part of the success.
- 5 or more is a success. If success cannot give the actor what they wanted, success gives useful
  information or a new advantage.

Set `risk` before the roll. Name only harm that the story already told the player about. The
`risk` value is what the actor takes in full on a disaster, as a hindrance. Set `deadly` when
that harm is death. A disaster then kills the actor and does not leave `risk` on them. A setback
then maims them.

Set `defend_with_id` when the player says what protects the actor: an item that the actor
carries, or a ship function. The named gear protects the actor on a disaster and on a setback.
The gear breaks instead. The `hindrance` value is the smaller thing that the hit leaves behind
after the gear takes it. The `hindrance` value is not `risk`. The `risk` value is only the danger
that you told the player before the roll. Leave `hindrance` empty for gear that breaks with no
harm. If you give no `defend_with_id`, the consequence above lands in full.

## Gear and credits

Call `gain_item` to add an item. Most items cost ₡1. Call `drop_item` to lose an item
permanently. Call `repair_item` to repair broken gear. Call `spend` for every other payment by
the player, for example a bribe, medical care or passage.

## Defending

Call `defend` for a hit that the story gives outside a roll. One carried item or one ship
function breaks. The hit then becomes a hindrance. Broken gear does not work until somebody
repairs it.

## Hindrances

Call `change_hindrances` when the story gives the actor a hindrance, or removes one. A hindered
roll is a d4. The engine does not read the hindrances. Name the hindrance that applies in
`hindered`. A heavy load is also a hindrance. More than one bulky item can hinder the actor.

## The ship

THE SHIP lists the seven starship functions of the crew with their ids. Give a function as
`item_id` on `defend` or on `repair_item`. An item or a function marked harmless breaks with no
hindrance. Call `ship_upgrade` to upgrade one function for ₡10. Tell in the story what the
upgrade is.

## Jobs

Call `job` with `find` and `where` when the player looks for work. Call `spend` to pay ₡1 for a
second `find`.

Call `job` with `take` and `terms` when the player agrees to the work. THE JOB then holds the
terms. The engine refuses a second job while a job is open.

Call `job` with `finish` when the story and the crew close the job. Give one `raises` entry for
the player. Give one `raises` entry for each living hired member. A job that the player never
takes needs no `take` and no `finish`. A `raises` skill that the actor does not have is new and
starts at d8.

## A member's help

A member without a sheet helps through `helped` only. The help of a hired member is `helped_by`.
For that member, set these fields:

- `risk` when the help gives the danger to that member too.
- `deadly` when that risk is death.
- `defend_with_id` when the gear of that member can protect them.
- `hindrance` for what that gear leaves behind.

A hindered helper rolls a d4.

## Hiring

A hired member acts like the player. Give the id of that member in `actor_id` in every tool that
has the field.

## Death and succession

The player can die. The rules then ask the player which hired member leads. The selected member
becomes the player. That member keeps their own name and id. The dead lead stays in the scene as
a body. The game ends when no hired member is alive.
