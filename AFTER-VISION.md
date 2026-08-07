# AFTER IMPLEMENTATION OF VISION

DEV ASKED "Is there a way after the whole refactor to considerably simplify the schema of the outputs without losing features?"
RESPONSE:

Yes. In fact, **the refactor creates the opportunity to make the model-facing schemas much smaller than they are today**.

The important trick is:

> **Simplify the semantic output the model must produce, while keeping strict validation underneath.**

Right now the Director plan has to express too much of the execution structure: action choice, unconditional effects, conditional branches, narrative intent, and so on. Once the Rule VM owns resolution, most of that can disappear from model output.

### 1. The Rules Director can become almost trivial

I would aim for something conceptually like:

```json
{
  "action": "attack",
  "actor": "kael",
  "target": "goblin",
  "weapon": "longsword"
}
```

or:

```json
{
  "action": "cast-spell",
  "actor": "kael",
  "spell": "fireball",
  "target": "ogre"
}
```

No:

* success/failure branches;
* dice;
* damage;
* resource spending;
* effects;
* outcome selection;
* state changes.

The VM already knows what `attack` or `cast-spell` means.

So the model only answers:

> **Which mechanic is happening, and what choices does that mechanic require?**

That is probably the single biggest schema simplification available.

---

### 2. Keep it simple to the model, strict to the runtime

I would **not** change this to:

```json
{
  "action": "attack",
  "args": {
    "...": "anything"
  }
}
```

with an unrestricted dictionary.

That's aesthetically generic, but it throws away one of the things that made your small models reliable.

Instead, generate a strict discriminated schema from `actions.yaml`.

Conceptually the engine says:

```yaml
actions:
  attack:
    inputs:
      actor: entity(actor)
      target: entity(actor)
      weapon: content(weapon)

  cast-spell:
    inputs:
      actor: entity(actor)
      spell: content(spell)
      target:
        type: entity(actor)
        optional: true
```

At runtime AIDM derives something equivalent to:

```text
AttackPlan
  action = "attack"
  actor
  target
  weapon

CastSpellPlan
  action = "cast-spell"
  actor
  spell
  target?
```

So **the Python code knows about only generic ActionPlans**, but the model still sees a highly constrained schema.

That gives you both goals:

```text
simple architecture
+
strict small-model output
```

---

## The bigger simplification: remove effects from plans

I think this is where the architecture becomes substantially cleaner.

Today the conceptual plan resembles:

```text
intent
tone
speaker
action
effects
branches
    success effects
    failure effects
    ...
```

After the refactor:

```text
Scene Director
    ↓
scene brief

Rules Director
    ↓
action invocation

Rule VM
    ↓
facts + effects
```

The Director shouldn't have to say:

```json
{
  "branches": {
    "success": [
      {"type": "adjust_counter", "target": "goblin", "counter": "hp", "amount": -7}
    ]
  }
}
```

The engine definition already says what a successful attack does.

The Director should say:

```json
{
  "action": "attack",
  "actor": "kael",
  "target": "goblin",
  "weapon": "longsword"
}
```

Everything else follows deterministically.

---

# I would also simplify the other roles

Once roles are specialized, each role can have an extremely small schema.

### Scene Director

Something like:

```json
{
  "focus": "Mara confronts Kael about the map",
  "pressure": "Her trust is at stake",
  "threads": ["mara-trust"]
}
```

Potentially even:

```json
{
  "focus": "Mara confronts Kael about the map",
  "threads": ["mara-trust"]
}
```

because `pressure` may simply be part of `focus`.

I would resist adding lots of fields like:

```text
tone
dramatic_goal
pacing
tension
npc_intention
stakes
scene_type
desired_emotion
...
```

unless your evals prove that those fields improve downstream behavior.

Small output types are likely better.

---

### Rules Director

Ideally:

```json
{
  "action": "persuade",
  "actor": "kael",
  "target": "mara"
}
```

That's it.

The Scene Director has already established why this matters.

---

### Narrator

Possibly **no schema at all** beyond validated text.

It receives:

```text
scene brief
+
facts
+
visible state
```

and writes prose.

If you need presentation metadata later, keep it tiny:

```json
{
  "text": "...",
  "speaker": "mara"
}
```

But even `speaker` may belong in Facts rather than Narrator output.

---

# Worldkeeper can also become much smaller

This one is interesting.

Instead of having lots of special creation output models, you could eventually have a small generic proposal vocabulary:

```json
{
  "proposals": [
    {
      "kind": "entity",
      "name": "Old Tomas",
      "entity_kind": "actor",
      "brief": "The cloister's aging groundskeeper"
    }
  ]
}
```

Core decides how that becomes persisted state.

Likewise relations:

```json
{
  "proposals": [
    {
      "kind": "relation",
      "relation_kind": "connected-to",
      "source": "cloister",
      "target": "bell-tower"
    }
  ]
}
```

I would still make this a **strict union**, not arbitrary operations.

---

# Memorykeeper could be almost absurdly simple

Something like:

```json
{
  "memories": [
    {
      "subject": "mara",
      "text": "Kael lied about why he wanted the vault map."
    }
  ]
}
```

Maybe `importance` if you genuinely need it:

```json
{
  "subject": "mara",
  "text": "...",
  "importance": 2
}
```

But again: don't ask the model to classify ten dimensions if code doesn't actually need them.

---

# Threadkeeper can also be tiny

If the Threadkeeper only evaluates fuzzy transitions, don't ask it to rewrite the thread.

Give it allowed transitions:

```text
mara-trust:
  suspicious -> warming
  warming -> trusted
```

and have it answer:

```json
{
  "transition": "warming"
}
```

or:

```json
{
  "transition": null
}
```

If multiple threads are being considered:

```json
{
  "transitions": [
    {
      "thread": "mara-trust",
      "to": "warming"
    }
  ]
}
```

Core performs the actual state mutation.

---

# There may be an even deeper unification

After the refactor, you probably end up with **three families of model output** rather than dozens.

### A. Decision

Models choose something from an existing vocabulary.

Examples:

* Scene Director chooses focus/thread.
* Rules Director chooses action + arguments.
* Threadkeeper chooses transition.

Conceptually:

```text
choice + arguments
```

### B. Proposal

Models propose new persistent information.

Examples:

* Worldkeeper proposes entity/relation.
* Memorykeeper proposes memory.

Conceptually:

```text
kind + payload
```

### C. Prose

Narrator writes text.

That's basically it.

So at the architecture level:

```text
MODEL OUTPUTS

Decision
Proposal
Prose
```

You don't necessarily need literal `Decision` and `Proposal` base classes—I would avoid introducing them unless they reduce real duplication—but conceptually that's where the system converges.

---

# And the VM output should probably be generic too

The Rule VM can simplify the other side as well.

Every engine currently has its own understanding of resolution.

Eventually the VM could produce something like:

```text
Resolution
    outcome
    facts[]
    effects[]
```

For example:

```json
{
  "outcome": "success",
  "facts": [
    {
      "kind": "attack-hit",
      "subject": "kael",
      "target": "goblin",
      "data": {
        "damage": 7
      }
    }
  ]
}
```

Internally it may have applied generic effects such as:

```text
AdjustCounter(goblin, hp, -7)
```

The Narrator mostly needs the Facts.

So engine-specific action diversity collapses into:

```text
many input actions
        ↓
one generic VM
        ↓
generic effects + facts
```

That's a very strong simplification.

---

# I would target this final turn interface

At the end of the refactor, I'd love the core turn to be explainable to a new contributor as:

```text
1. Scene Director says what matters.

   SceneBrief
      focus
      relevant threads


2. Rules Director says what the character does.

   ActionPlan
      action
      action-specific arguments


3. Rule VM executes it.

   Resolution
      outcome
      effects
      facts


4. Hooks react to Facts.

   more effects + facts


5. State transaction commits.


6. Narrator describes committed Facts.

   text


7. Maintenance roles make tiny proposals.

   WorldProposal[]
   MemoryProposal[]
   ThreadTransition[]
```

That is dramatically simpler than asking one Director to construct a rich state-transition tree.

---

## One thing I would specifically add to `VISION.md`

I think the earlier document is missing this as an explicit architectural goal:

> **Model-facing schemas should get smaller as the system becomes more capable.**
>
> Each runtime role should output only information that cannot be derived deterministically from its inputs. If code, engine data, or an earlier role already determines a value, later models should not be asked to reproduce it. Engine-specific schemas should be generated from declarative engine definitions so models retain strict validation without requiring engine-specific Python output classes.

That principle is surprisingly powerful.

For every schema field you can ask:

> **Why does the model need to decide this?**

If the answer is “it doesn't; we can derive it,” delete the field.

And I suspect after the full refactor, your **Rules Director schema could be 70–90% smaller conceptually than today's TurnPlan**, while actually supporting substantially more features.
