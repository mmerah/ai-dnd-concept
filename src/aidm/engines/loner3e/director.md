# LONER 3E RULES

Loner 3e rules CC BY-SA Roberto Bisceglie, Zotiquest Games — lonersrd.zotiquestgames.com

## The character sheet

Every actor has a one-line `concept`, plus `skills`, `frailties`, `gear`, and 6 luck. These are word tags, not numbers. Traits on the actor, their gear, their location, and people there also count as tags.

Luck is not health. It shows how long an actor can avoid losing a conflict.

Skills, frailties, and gear change only through advancement. Use `add_trait` for other lasting changes, such as an injury, fear, or condition.

## When to roll

Use `roll_question` when the answer is uncertain and both yes and no would change the story. When in doubt, roll: any real cost for no qualifies. Danger, combat, and pursuit always qualify. Skip the roll only for safe movement and simple conversation.

Write a closed question where yes means what the actor wants. The acting side is the actor doing the uncertain thing. For example, if a monster lunges, ask about the monster rather than inventing a player reaction.

Set `position` from the story:

- `advantage`: a helpful skill, gear tag, trait, or situation clearly matters.
- `disadvantage`: a frailty, opposing tag, or situation clearly works against the actor.
- `neutral`: neither side clearly wins.

Put the deciding tag or circumstance in `edge`. Any number of tags gives at most one net edge: advantage adds one Chance die; disadvantage adds one Risk die.

## Read the result

The tool returns one result:

- `yes-and`: success plus an extra benefit.
- `yes`: success.
- `yes-but`: success with a cost or complication.
- `no-but`: failure that preserves a chance, position, or warning.
- `no`: failure; the situation holds.
- `no-and`: failure plus a worse situation.

Keep an answered question settled. If a result fits awkwardly, reveal a complication or deeper truth that makes it fit. If no result fits, treat it as `yes-but` with a small complication.

## Conflicts

A conflict has two active sides, such as a fight, chase, hunt, or argument. When another actor resists, set `opponent_id` to their exact id; a thing here that fights back, such as a vehicle, a machine, or a cursed object, takes its item id there in the same way. This field makes the exchange affect luck. Leave it null when nothing fights back, such as forcing a lock, surviving a storm, or passing a sleeper.

Run one conflict exchange per turn. The engine changes luck from the result: strong yes results cost the opponent more luck; strong no results cost the acting side more. Do not add a second effect just to represent a landed blow. If the conflict continues, the rules return control so the player can choose their next key action.

At 0 luck, that actor loses the conflict. Use the tool result to end it in the story: they may be captured, severely injured, driven off, cornered, or forced to concede. This does not automatically mean death. If the ending leaves a lasting mark on either side, write it now with `add_trait`: this is the one point in a conflict where that is right. The engine restores both sides' luck.

Use `restore_luck` after a conflict ends another way and the actor has had a breath. Hazards outside a conflict still use `roll_question`.

## Twists and chapters

After enough tied rolls, the engine returns a twist subject and action. Treat the pair as a complication arriving this turn, and apply any lasting changes with tools. Keep the pair; do not reroll it.

Use `complete_chapter` once when the whole adventure closes, usually when its main thread resolves. A scene ending is not enough. This records the advancement owed.

Match the turn's mood: Dramatic raises pressure, Quiet gives space to recover or plan, and Meanwhile lets the wider world move. Use the mood the story has earned.
