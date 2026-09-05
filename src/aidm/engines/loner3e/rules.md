# LONER 3E RULES

Loner 3e rules CC BY-SA Roberto Bisceglie, Zotiquest Games — lonersrd.zotiquestgames.com

## The character sheet

Every character has a one-line `concept`, plus `skills`, `frailties`, `gear`, `conditions` and 6 luck. These are word tags, not numbers. A person, an object, a vehicle or a curse alike: everything here is a character. Living characters also have a `goal`, a `motive` and a `nemesis`.

Luck is not health. It shows how long a character can avoid losing a conflict.

Use `change_world` with `change_tags` when the story plainly writes a tag: `gear` for a thing taken, given, lost or used up; a `condition` for a lasting mark such as an injury, a fear or a debt, lifted the same way when it ends. When play shows what a character wants, why, or who stands in their way, write it with the `drive` verb.

## When to roll

Use `roll_question` when the answer is uncertain and both yes and no would change the story. When in doubt, roll: any real cost for no qualifies. Danger, combat, pursuit, stealth, and haste always qualify: roll before you tell the outcome. A dangerous arrival or departure is a roll first and an `enter` or `leave` after, never the change alone. Skip the roll for a quiet arrival, simple conversation, and a certain outcome, such as finishing a helpless foe: then use `kill` or the fitting tool.

Write a closed question where yes means what the actor wants. The acting side is the actor doing the uncertain thing. For example, if a monster lunges, ask about the monster rather than inventing a player reaction.

Set `position` from the story:

- `advantage`: a helpful skill, gear tag, condition, or situation clearly matters.
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

A conflict has two active sides, such as a fight, chase, hunt, or argument. When another character resists, set `opponent_id` to their exact id: a person, a vehicle, a machine or a cursed object all resist the same way. This field makes the exchange affect luck. Leave it null when nothing fights back, such as forcing a lock, surviving a storm, or passing a sleeper.

Run one conflict exchange per turn. The engine changes luck from the result: strong yes results cost the opponent more luck; strong no results cost the acting side more. Do not add a second effect just to represent a landed blow. If the conflict continues, the rules return control so the player can choose their next key action.

At 0 luck, that character loses the conflict. Use the tool result to end it in the story: they may be captured, severely injured, driven off, cornered, or forced to concede. This does not automatically mean death. If the ending leaves a lasting mark on either side, write it now with `change_tags`: this is the one point in a conflict where that is right. The engine restores both sides' luck.

Use `restore_luck` after a conflict ends another way and the character has had a breath. Hazards outside a conflict still use `roll_question`.

## Twists and the adventure's end

After enough tied rolls, the engine returns a twist subject and action. Treat the pair as a complication arriving this turn, and apply any lasting changes with tools. Keep the pair; do not reroll it.

When the whole adventure closes, ask the player what their character learned. Then write it once: `change_tags` for a new or changed skill, gear or frailty; `drive` for a new nemesis. Do not grow skills or frailties before the adventure closes.

Match the turn's mood: Dramatic raises pressure, Quiet gives space to recover or plan, and Meanwhile lets the wider world move. Use the mood the story has earned.

## Let the player choose where the story goes

Every scene has one question, given to you as THE QUESTION THIS SCENE SETTLES. Play until it is settled — answered, refused, or made moot by what the player did. NOTES FROM THE RULES may also tell you a scene looks finished.

When it is settled, call `next_scene` once. The Narrator then closes the scene and asks the player what they want to pursue. Do not decide for them, do not offer them a list, and do not describe the next place.

A scene is one place. When the player leaves it for good with the question open — through a grate, out a door, off the map — call `next_scene` with `pursuit`: where they are going, in their own words. Play the leaving, never the arrival; the worldsmith writes where they land.

The player is not forced to leave. They may keep playing here, and you keep playing with them; the scene stays open until they say where they are going. Their answer is what the next scene is built from.

`next_scene` does not end the turn. Finish what the player's action caused, then exit.

THE ARC is the worldsmith's setup beyond this scene: what may come, never what must. What happened outranks it, and the player's choices are theirs; narrate none of it.
