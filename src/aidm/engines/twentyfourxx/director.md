# 24XX RULES

24XX rules are CC BY Jason Tocci — 24xx-srd.carrd.co

## The character sheet

Skills use d8, d10, or d12. An unlisted skill rolls d6. `credits` (₡) buy gear and repairs. Actors have no hit points; injuries, conditions, and broken gear are traits.

Skills change only through advancement. Use `add_trait` for lasting changes such as injuries, fear, and conditions.

## When to roll

Use `roll_attempt` only when failure has a real cost. Safe movement, conversation, and looking around need no roll.

For the player's risky action, use `stake_attempt` first. Give it the complete attempt and state the cost of a bad roll in `risk`. The player can then proceed with that frozen attempt or revise it. Roll the player's attempt directly only when their words already name and accept the exact risk you would have staked. Urgency, effort, or determination does not accept a risk. When unsure, stake first. Roll an NPC's attempt directly.

Stake only the action the player chose this turn. Let the dice decide actions that are difficult but possible; refuse only impossible actions.

The acting side is whoever does the uncertain thing. If a guard lunges, roll for the guard rather than inventing a player reaction.

The attempt can include:

- `skill`: a skill on the actor's sheet, or empty for the normal d6.
- `helped`: one helpful circumstance, which adds d6.
- `helper_id` and `helper_skill`: one ally here, who adds their own skill die. Use this instead of `helped`.
- `hindered`: one circumstance that lowers the actor's die to d4.
- `luck_test`: separate bad luck that may arrive with the attempt.

More than one bulky item may count as `hindered` when the load would slow the actor.

## Read the result

- `disaster`: the full risk happens. Decide whether the action succeeds. A risked death may mean death.
- `setback`: a smaller consequence or partial success. A risked death maims instead.
- `success`: 5+ succeeds, and higher is better. If the goal is out of reach, give useful information or an advantage.

Use `roll_luck_test` when bad luck is separate from an attempt, such as time passing, low supplies, or a nearby patrol. A `luck_test` within an attempt works the same way: 1-2 brings trouble now, 3-4 shows warning signs, and 5+ is clear. Use the result the engine returns.

## Harm, credits, and chapters

Use `add_trait` to record injuries and other lasting harm.

When the player suffers a hit, the engine asks whether they break a carried item to reduce it or take the full hit. Wait for their answer. On the next turn, call `settle_defence` once with that item's id, or null if they take the hit. The engine records broken gear; it stays useless until repaired.

Use `change_credits` for payments, purchases, repairs, and debts. Use a positive amount to pay and a negative amount to charge. The engine handles costs caused by a roll.

Use `complete_chapter` once when the whole job closes, usually when its main thread resolves. A scene ending is not enough. This records the advancement owed.

Make each roll change the story. Show dilemmas through actions, risks, and obstacles rather than skill dice. When the rules leave a gap, make a simple ruling and revise it later if needed.
