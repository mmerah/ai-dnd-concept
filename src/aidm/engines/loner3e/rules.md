# LONER 3E RULES

Loner 3e rules CC BY-SA Roberto Bisceglie, Zotiquest Games — lonersrd.zotiquestgames.com

## The sheet

Everything here is a character: a person, an object, a vehicle or a curse. Each one has a
one-line concept and tags by kind: skills, frailties, gear and conditions. Tags are words, not
numbers. A living character also has a goal, a motive and a nemesis.

Luck is not health. It shows how long a character can hold out in a conflict. A character starts
with 6 luck.

## Tags and drives

Call `change_tags` when the story plainly writes a tag or lifts one. Call `drive`
when play shows what a character wants, why, or who stands in their way.

## When to roll

Call `roll` when the answer is uncertain and both yes and no would change the story. When in
doubt, roll. Any real cost for no is enough. Danger, combat, pursuit, stealth and haste always
qualify. Roll before you tell the outcome.

Do not roll for a quiet arrival, plain conversation, or a certain outcome. Finishing a
helpless foe is certain. Call `kill` or the fitting tool instead. A dangerous arrival or
departure is a roll first and `enter` or `leave` after.

The actor is the one doing the uncertain thing. If a monster lunges, ask about the monster.

Set `position` from the story. Set it to `advantage` when a helpful skill, gear tag, condition
or situation clearly matters. Set it to `disadvantage` when a frailty, an opposing tag or the
situation clearly works against the actor. Set it to `neutral` when neither side clearly wins. Any number of
tags gives at most one net edge.

## Reading a roll

The engine answers with one of six results. `yes-and` is success plus an extra benefit. `yes` is
success. `yes-but` is success with a cost. `no-but` is failure that keeps a chance open. `no` is
failure, and the situation holds. `no-and` is failure plus a worse situation.

Keep an answered question settled. If a result fits awkwardly, reveal a complication or a deeper
truth that makes it fit. If no result fits, treat it as `yes-but` with a small complication.

## Conflicts

A conflict has two active sides, such as a fight, a chase, a hunt or an argument. You choose how
much detail it deserves.

One question can settle a whole conflict: leave `opponent_id` null, ask whether the actor wins
it, and let the answer stand. Use this when the opposition is minor, or when the story wants the
contest over in a line.

A series of questions plays the key actions out: leave `opponent_id` null and roll each one. Use
this when the steps matter but holding out does not.

Luck exchanges run a contest of endurance: set `opponent_id`. Use this when both sides can lose
ground over several exchanges and how long each holds out is the point. A person, a vehicle, a
machine and a cursed object all resist the same way. Run one exchange per turn. The engine takes
luck from the result. A strong yes costs the opponent more luck. A strong no costs the acting
side more. Do not add a second effect for a landed blow.

A changed approach can change `position`. The same approach repeated keeps it. Breaking off is
free: roll the escape with no opponent, or call `leave`.

A character at 0 luck loses the conflict. Say how it ends for them in the story. They can be
captured, injured, driven off, cornered, or forced to concede. This does not mean death. Write
any lasting mark now with `change_tags`. This is the one point in a conflict where that
is right. The engine restores the luck of both sides and marks the loser defeated.

A defeated character takes no new conflict. Call `restore_luck` when the defeat is behind them
and a new contest begins: it clears the mark. Call it too after a conflict ends another way and
the character has had a breath.

## Twists

The engine returns a twist subject and action after 3 tied rolls outside a
conflict. Treat the pair as a
complication arriving this turn. Apply any lasting change with tools. Keep the pair and do not
roll it again.

## The end of the adventure

Ask the player what their character learned when the whole adventure closes. Then write it once.
Call `change_tags` for a new or changed skill, gear or frailty. Call `drive` for a
new nemesis. Do not grow skills or frailties before the adventure closes.

## A member's help

A member rolls only as the actor of their own uncertain act. Otherwise their help sets
`position` or names the `edge`.
