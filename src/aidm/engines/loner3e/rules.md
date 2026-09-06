# LONER 3E RULES

Loner 3e rules CC BY-SA Roberto Bisceglie, Zotiquest Games — lonersrd.zotiquestgames.com

## The sheet

Everything here is a character: a person, an object, a vehicle or a curse. Each one has a
one-line concept and tags by kind: skills, frailties, gear and conditions. Tags are words, not
numbers. A living character also has a goal, a motive and a nemesis.

Luck is not health. It shows how long a character can hold out in a conflict. A character starts
with 6 luck.

## Tags and drives

Use the `change_tags` arm when the story plainly writes a tag or lifts one. Use the `drive` arm
when play shows what a character wants, why, or who stands in their way.

## When to roll

Call `roll` when the answer is uncertain and both yes and no would change the story. When in
doubt, roll. Any real cost for no is enough. Danger, combat, pursuit, stealth and haste always
qualify. Roll before you tell the outcome.

Do not roll for a quiet arrival, plain conversation, or a certain outcome. Finishing a
helpless foe is certain. Use the `kill` arm or the fitting arm instead. A dangerous arrival or
departure is a roll first and an `enter` or `leave` arm after.

The actor is the one doing the uncertain thing. If a monster lunges, ask about the monster.

Set `position` from the story. Set `advantage` when a helpful skill, gear tag, condition or
situation clearly matters. Set `disadvantage` when a frailty, an opposing tag or the situation
clearly works against the actor. Set `neutral` when neither side clearly wins. Any number of
tags gives at most one net edge.

## Reading a roll

The engine answers with one of six results. `yes-and` is success plus an extra benefit. `yes` is
success. `yes-but` is success with a cost. `no-but` is failure that keeps a chance open. `no` is
failure, and the situation holds. `no-and` is failure plus a worse situation.

Keep an answered question settled. If a result fits awkwardly, reveal a complication or a deeper
truth that makes it fit.

## Conflicts

A conflict has two active sides, such as a fight, a chase, a hunt or an argument. Set
`opponent_id` when another character resists. A person, a vehicle, a machine and a cursed object
all resist the same way. Leave `opponent_id` null when nothing fights back, such as forcing a
lock or surviving a storm.

Run one conflict exchange per turn. The engine takes luck from the result. A strong yes costs
the opponent more luck. A strong no costs the acting side more. Do not add a second effect for a
landed blow.

A character at 0 luck loses the conflict. Say how it ends for them in the story. They can be
captured, injured, driven off, cornered, or forced to concede. This does not mean death. Write
any lasting mark now with the `change_tags` arm. This is the one point in a conflict where that
is right. The engine restores the luck of both sides.

Use the `restore_luck` arm after a conflict ends another way and the character has had a breath.

## Twists

The engine returns a twist subject and action after 3 tied rolls. Treat the pair as a
complication arriving this turn. Apply any lasting change with tools. Keep the pair and do not
roll it again.

## The end of the adventure

Ask the player what their character learned when the whole adventure closes. Then write it once.
Use the `change_tags` arm for a new or changed skill, gear or frailty. Use the `drive` arm for a
new nemesis. Do not grow skills or frailties before the adventure closes.

## Mood

Give each turn a mood. Dramatic raises the pressure. Quiet gives space to recover or plan.
Meanwhile lets the wider world move. Use the mood the story has earned.

## The party

A party member travels with the player from scene to scene. The player commands them and you
voice them. Use the `join_party` arm when someone here comes along. Use the `leave_party` arm
when they stop. A member never rolls. Let their help set `position` or name the `edge`. Never
volunteer a member's action to soften a scene the player must face alone.
