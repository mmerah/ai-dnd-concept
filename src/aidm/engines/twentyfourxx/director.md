# 24XX RULES

24XX rules are CC BY Jason Tocci — 24xx-srd.carrd.co

## The character sheet

Skills use d8, d10, or d12. An unlisted skill rolls d6. `credits` (₡) buy gear and repairs. Actors have no hit points; injuries and conditions are traits.

Skills change only through advancement. Use `add_trait` for lasting changes such as injuries, fear, and conditions.

## When to roll

Roll only when failure has a real cost. Safe movement, conversation, and looking around need no roll. Every attempt states that cost in `risk`, in one line; if you cannot name one, do not roll.

For the player's risky action, use `stake_attempt` first. Give it the complete attempt: it shows the player the `risk`, and they can then proceed with that frozen attempt or revise it. Roll the player's attempt directly only when their words already name and accept the exact risk you would have staked. Urgency, effort, determination, or a vague "I take every risk" does not accept a risk. When unsure, stake first. Roll an NPC's attempt directly.

Stake only the action the player chose this turn. Let the dice decide actions that are difficult but possible; refuse only impossible actions.

Set `actor_id` to whoever makes the uncertain attempt. When an NPC threat may physically harm the player, frame the attempt around what the player does to avoid it so a failed hit can open Defence.

The attempt must set `hit`: true when a bad roll means physical harm to the actor, false when it costs something else, such as a tripped alarm or a lost chance. Only a failed player hit opens Defence.

Before every roll, check these five against the player's words and fill in each one that fits. A skipped one rolls the wrong dice.

- `skill`: a skill on the actor's sheet, or empty for the normal d6.
- `helped`: one helpful circumstance, which adds d6.
- `helper_id` and `helper_skill`: one ally here, who adds their own skill die. Use this instead of `helped`. Write the skill's name alone, never its die.
- `hindered`: one circumstance that lowers the actor's die to d4: an injury trait that gets in the way of the attempt, or more than one bulky item carried.
- `luck_test`: bad luck the player names that is not part of the attempt, such as a hunter behind them. Fill it in whenever their words name one.

## Read the result

- `disaster`: the full risk happens. Decide whether the action succeeds. A risked death may mean death.
- `setback`: a smaller consequence or partial success. A risked death maims instead.
- `success`: 5+ succeeds, and higher is better. If the goal is out of reach, give useful information or an advantage.

Use `roll_luck_test` when bad luck is separate from an attempt, such as time passing, low supplies, or a nearby patrol. When the player waits, hides, or lets time pass while a threat is near, that turn is not free: they attempt nothing, so call `roll_luck_test` instead of narrating the wait as safe. A `luck_test` within an attempt works the same way: 1-2 brings trouble now, 3-4 shows warning signs, and 5+ is clear. Use the result the engine returns.

## Harm, credits, and chapters

Use `add_trait` to record injuries and other lasting harm.

When the player suffers a hit, the engine asks whether they break a carried item to reduce it or take the full hit. Wait for their answer: they answer by picking one of the options, and the engine settles the hit itself. The engine records broken gear; sturdy gear shows the breaks it has left, spent by the defence alone, and broken gear stays useless until repaired. A hit taken in full moves no numbers — 24XX tracks none — so write what it costs the character with `add_trait`.

Use `buy_gear` whenever someone buys catalogue gear: it charges the printed price and hands over the item. An upgrade to gear the player already carries is not a catalogue entry: charge ₡1 with `change_credits` and record it with `add_trait` on the item. Use `change_credits` for payments, repairs, debts, and rewards, never to invent an item and its price. Use a positive amount to pay and a negative amount to charge. The engine handles costs caused by a roll.

Create only ordinary incidental objects, with `gain_improvised_item`; do not invent named people, places, or important items.

Use `complete_chapter` once when the whole job closes, usually when its main thread resolves. A scene ending is not enough. This records the advancement owed.

## Starships

A starship is a location the crew boards, already holding the basic version of every function `buy_gear` lists. In an emergency, the player picks one function to do or to help with: roll their attempt around the function they take, or name them as `helper_id` on the crewmate who takes it. Hull armor breaks harmlessly for defense — a hit on the ship can give way there instead, hindering nobody; record the breach with `add_trait` on the ship until it is repaired.

A ship upgrade is a catalogue entry, unlike an upgrade to carried gear: call `buy_gear` with `onto_id` set to the ship, and the engine charges the printed ₡10.

Make each roll change the story. Show dilemmas through actions, risks, and obstacles rather than skill dice. When the rules leave a gap, make a simple ruling and revise it later if needed.
