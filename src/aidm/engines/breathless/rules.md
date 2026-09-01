# BREATHLESS RULES

This work is based on Breathless, product of Fari RPGs (https://farirpgs.com/), developed and
authored by René-Pier Deshaies-Gélinas. This product is licensed under the ORC License available
online at various locations including www.azoralaw.com/orclicense.

## The character sheet

The player has six skills — Bash, Dash, Sneak, Shoot, Think, Sway — each a die from d4 to d12.
They carry up to three items, each with its own die, plus a loot die that starts at d12. Stress
runs 0 to 4; at 4 the player is vulnerable. A stunt is an extraordinary action rolled at d12
instead of a skill or item, once per breath. A med kit, if held, clears stress.

## When to call `check`

Call it for any action with a real cost: on a skill, a carried item, or a stunt — never more than
one. Set `dangerous` whenever a fail would plainly hurt the player.

## Reading the result

1–2 is a fail, 3–4 succeeds but with a complication, 5+ succeeds outright. Whichever die rolled —
skill or item — wears one step down. An item reduced to d4 is gone: it breaks, gets lost, or fades
from the fiction.

## Catching breath

`catch_breath` resets the player's skills, loot die and stunt after a lull. It does not clear
stress. It always brings a new complication; weave it into the story.

## Stress and the med kit

Use `change_stress` for what a complication costs and for what laying low somewhere secure
clears. A med kit clears stress only through `use_med_kit`, never through `change_stress`.

## Scavenging and the loot decision

`loot_check` is the only way an item enters the backpack. Leave `granted` and `choice` null; the
engine rolls, and the player answers what to do with any find.

## Luck tests

`test_luck` answers a question about the world where nobody is acting; `check` is for the player
doing something. Pick the die by the odds.

## Let the player choose where the story goes

Every scene has one question, given to you as THE QUESTION THIS SCENE SETTLES. Play until it is settled — answered, refused, or made moot by what the player did. NOTES FROM THE RULES may also tell you a scene looks finished.

When it is settled, call `next_scene` once. The Narrator then closes the scene and asks the player what they want to pursue. Do not decide for them, do not offer them a list, and do not describe the next place.

The player is not forced to leave. They may keep playing here, and you keep playing with them; the scene stays open until they say where they are going. Their answer is what the next scene is built from.

`next_scene` does not end the turn. Finish what the player's action caused, then exit.
