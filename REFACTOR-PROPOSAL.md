Yes. The code is already unusually disciplined at the local level; the main maintainability cost is **architectural indirection**, not messy functions. Your own rules already point in the right direction—pure functions, strict boundaries, no speculative abstractions, and one-way imports. 

I see **three refactors worth seriously considering**, plus one much more radical product/architecture change.

### 1. Replace the giant `Engine` callback bag with an engine object

This is the clearest simplification.

`Engine` currently acts as a manually assembled vtable: models plus `creation_steps`, `create_character`, `preview_character`, `validate`, `new_game`, `known`, `record`, `history`, `master_sections`, views, `Authoring`, `Transition`, etc.  `Authoring` and `Transition` add another layer of callback bundles. 

You can see the resulting ceremony in the three scene engines: their `build()` functions are largely wiring the same shared functions into the same slots.   

I would seriously test this shape instead:

```python
class BreathlessEngine:
    id = EngineId("breathless")
    title = "BREATHLESS"

    def __init__(self, packs_dir: Path):
        self.packs = load_packs(...)

    def create_character(...): ...
    def validate(...): ...
    def new_game(...): ...
    def tools(...): ...

    async def write_world(...): ...
    def install_world(...): ...

    def narrator_view(...): ...
    def player_view(...): ...
```

And for the three scene games:

```python
class SceneEngine:
    # implements history, known, record, views,
    # scene transitions, authoring, etc.
```

```python
class BreathlessEngine(SceneEngine):
    Character = Survivor
    Game = BreathlessGame

    def mechanics_tools(self): ...
    def player_from_character(self, character): ...
    def worldsmith_guidance(self): ...
```

That would eliminate:

* `Authoring`
* `Transition`
* much of `Engine`
* most `partial(...)` construction
* most of the wrapper `worldsmith.py` functions
* probably some per-engine `views.py` plumbing
* the cognitive distinction between “engine configuration” and “engine behaviour”

The important thing is **not** to build a classical OOP hierarchy with 14 abstract methods. Make `SceneEngine` concrete and boring, and override only actual differences.

This is consistent with your stated reality: *three engines already share one scene lifecycle*.  Right now the architecture says that, but the source tree still makes each engine look more independent than it really is.

**Expected payoff: high. Risk: low-medium.**

---

### 2. Collapse the scene Worldsmith type hierarchy into one discriminated result

This area looks more complicated than the underlying concept.

Currently there are:

* `SceneDraft`
* `NextDraft`
* `JobDraft`
* `HubDraft`
* `ReturnDraft`

with runtime `isinstance()` dispatch to determine what gets installed. 

Then `write_next()` decides which Python model class the model must produce based on whether you're returning, at the hub, or elsewhere.  Installation performs more subtype tests to interpret `recap`, `job`, `offers`, and `debrief`. 

Conceptually there is really only:

> "Write the next place, optionally closing the previous segment and optionally updating campaign metadata."

I'd experiment with one model:

```python
class SceneDraft(Frozen):
    place: Slug
    title: str
    question: str
    situation: str
    secret: str = ""
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    cast: dict[EntityId, Person] = {}

    recap: str | None = None
    campaign: CampaignUpdate | None = None
```

Perhaps:

```python
class CampaignUpdate(Frozen):
    job: str | None = None
    debrief: str | None = None
    offers: tuple[Offer, ...] | None = None
```

The **requested schema** can still be made strict according to context. You don't need inheritance to obtain that strictness: dynamically construct/validate requirements after the answer, or have separate tiny input models and normalize immediately into one `SceneDraft`.

The important simplification is:

> Different model-output schemas should not necessarily become different domain concepts.

At the moment an LLM-output distinction leaks all the way into installation logic.

That is exactly the sort of complexity I'd remove.

**Expected payoff: medium-high. Risk: low.**

---

### 3. Make "world growth" one operation instead of `ready → write → install → arrival_brief`

The current `Transition` abstraction exposes four independent concepts:

```text
ready
write
install
arrival_brief
```



Consequently `GameService` needs to orchestrate a second mini-state-machine after the ordinary turn. It distinguishes normal movement, map extension, scene writing, narration after arrival, silent installation, failed installation, etc. The `play()` path already branches on whether `arrival_brief` exists and may transition into `_grow()`. 

I'd ask whether the platform really needs to understand all those phases.

Try making the engine expose:

```python
async def advance(
    state: Game,
    intent: str,
    worldsmith: Worldsmith,
) -> AdvanceResult | None:
    ...
```

where:

```python
class AdvanceResult:
    state: Game
    facts: tuple[Fact, ...]
    narration_context: str | None
```

Then `GameService` knows:

```python
result = await engine.advance(...)
if result:
    narrate_if_needed(result)
    commit(result.state)
```

For Tunnel Goons, `advance()` grows the map.

For scene engines, `advance()` writes the next scene.

The engine owns the whole transaction.

That fits your architectural principle that **the engine owns the world** much better than having `GameService` understand the stages by which an engine grows it. 

It would also shrink `GameService`, which currently carries a considerable number of responsibilities and live-state concepts (`busy`, `step`, `turn`, `write_failure`, illustrations, sessions, spawning, persistence, engine coordination). 

**Expected payoff: high. Risk: medium.**

---

## 4. The radical option: eliminate the Worldsmith role entirely

This is the one I'd prototype rather than immediately commit to.

Your three-role architecture is:

* master decides/resolves
* narrator presents only revealed information
* worldsmith expands the world

The **Narrator separation is valuable**. I would keep it. It gives you a genuine information-flow guarantee: hidden canon literally has no field through which it can reach the narrator. That's much stronger than prompting one model to pretend it doesn't know something. 

I'm less convinced that Worldsmith deserves to be a separate architectural actor.

Instead, the master could request world expansion through a tool whose argument **is the proposed world addition**:

```text
open_scene(
    place,
    title,
    question,
    situation,
    secret,
    present,
    hidden,
    new_cast,
    ...
)
```

or for Tunnel Goons:

```text
extend_map(...)
```

The resolver validates and applies it exactly as today.

That changes the system from:

```text
Player
  ↓
Master
  ↓
Python
  ↓
Worldsmith
  ↓
Python
  ↓
Narrator
```

to:

```text
Player
  ↓
Master ── typed proposals ──> Python
                               ↓
                            Narrator
```

This could delete a surprising amount:

* Worldsmith session management
* `WorldsmithAnswer`
* `Authoring`
* most/all `Transition.write`
* engine `worldsmith.py` adapter layers
* `_write()` / some of `_grow()` in `GameService`
* a whole role's configuration and failure/retry paths
* the distinction between model-authored mechanics changes and model-authored world changes

And conceptually you'd get a beautifully simple invariant:

> **The Master proposes everything that changes reality. Python validates/applies everything. The Narrator sees the resulting public projection.**

That may actually be a stronger conceptual model than the current three-agent decomposition.

The cost is substantial: world creation has huge prompts/source material, and you currently deliberately give that work to a specialized role. The Worldsmith can also take several minutes and has its own context needs. So I'd prototype this on one scene engine and compare output quality/context usage before changing architecture.

**Potential payoff: enormous. Risk: high / product-quality dependent.**

---

## What I would *not* simplify

I would keep several things that might initially look like abstraction overhead.

**`Game`'s draft/commit model is good.** A deep copied mutable transaction followed by complete Pydantic validation gives you a very understandable atomicity boundary. The implementation is tiny relative to the guarantee it provides.

**`Fact` is worth keeping.** It serves simultaneously as resolver evidence, player-visible cards, dice reporting and narration evidence. That's useful convergence rather than abstraction-for-abstraction's-sake.

**The Narrator projection boundary is excellent.** `NarratorView` physically lacks hidden information.  Don't trade that for convenience.

**Typed tool proposals + resolver-owned mutation are also worth keeping.** `MasterTool` is small, and `apply_to_draft()` centralizes meaningful invariants around decisions, visibility and validation. 

I also would **not introduce event sourcing, repositories, DI containers, command buses, plugin frameworks, or a generic ECS**. Those would move this codebase in exactly the wrong direction.

## If I owned the refactor

My sequence would be:

1. **Turn `Engine` into an object**, with a concrete `SceneEngine` implementation.
2. Move the complete transition transaction behind `engine.advance()`.
3. Normalize the five scene-draft classes into one internal representation.
4. See how much of `breathless/worldsmith.py`, `loner3e/worldsmith.py`, `twentyfourxx/worldsmith.py`, and the corresponding wiring disappears.
5. Only then prototype **Master-as-Worldsmith**.

I suspect steps 1–3 could make the architecture feel dramatically smaller without actually reducing features or weakening your correctness boundaries.

The litmus test I'd use is this: **adding a fifth scene-based RPG should mostly involve its state model, character creation, and actual rules/tools—not re-declaring the common lifecycle.** Today, the three nearly-identical `build()` assemblies show you're not quite there yet. 

If you want the single highest-leverage idea: **make `SceneEngine` a real implementation rather than a collection of shared functions wired into an `Engine` callback record.** That's the refactor I'd bet on.


# DEV NOTE

WORLDMSITH IS USEFUL FOR AUTHORING AND REMOVING IT WOULD MAKE MASTER DOO TOO MUCH

# SECOND RESPONSE OF THE PROPOSAL

Yes — with those two constraints, I would **not eliminate the Worldsmith**. I’d downgrade that idea from “possible radical simplification” to “probably the wrong tradeoff for this product.”

The separate role is doing two genuinely different jobs that would otherwise land on the Game Master:

1. **Rules adjudication:** decide what procedure applies, call tools, resolve consequences.
2. **World authorship:** invent coherent places/cast/secrets, preserve source canon, manage scene structure, campaign offers, recaps/debriefs, and map growth.

Your architecture explicitly treats those as separate responsibilities: the GM selects procedures and world changes, while the Worldsmith writes both the opening world and subsequent world growth. 

### The Game Master would get significantly harder

It's not primarily the raw **number of tools** that worries me. You could theoretically hide all world creation behind one giant `write_scene`/`extend_world` tool.

The larger problem is the GM's **attention budget**.

Right now it can think roughly:

> What did the player try? What rules apply? What actually changes? Do I need dice? Is the scene settled?

If it also becomes the author, it needs to think:

> What should the next scene be? What unresolved threads should it use? What new cast is appropriate? Which characters are present versus hidden? What secret should exist? What does the source permit? What should the campaign board contain? Is this a job departure, ordinary transition, or return? What recap should be retained?

And Tunnel Goons makes that even more pronounced because world growth isn't merely a scene—it can mean authoring a new map region with places, ways, NPCs and items.

That's exactly the kind of role expansion where model reliability tends to degrade even if the Python API itself remains neat: you haven't just given it more functions, you've given it **another profession**.

It would also muddy one of your nicest conceptual rules:

> GM = play the existing world.
> Worldsmith = author more world.

That's a useful division.

### Scenario authoring is an even stronger reason to keep it

This is the point that changes my recommendation most.

Scenario creation isn't a side effect of the runtime architecture; it's a first-class product feature. The current scenario workflow deliberately makes **one Worldsmith call to author the complete opening world**, after assembling the premise/source and engine-specific requirements. 

That role can therefore be optimized for things the GM shouldn't normally need:

* potentially very large source documents,
* source fidelity,
* coherent initial cast/world construction,
* hidden canon,
* opening situation design,
* campaign hub/board generation,
* engine-specific world-generation instructions.

If you removed it, you'd probably end up recreating a separate "scenario authoring model call" anyway.

At that point you've eliminated the **name** Worldsmith but not the architectural responsibility.

## So I'd keep the role and simplify the seam instead

I think this is the better target:

```text
                    ┌──────────────┐
scenario creation ─▶│              │
                    │  Worldsmith  │
game transition  ──▶│              │
                    └──────┬───────┘
                           │ typed WorldDraft
                           ▼
                         Engine
                           │
                           ▼
                         Game
```

The GM should preferably **not know how world generation works at all**.

It should only establish the game-state fact that makes growth appropriate. For a scene game, something like:

```python
settle_scene(job_done=False)
```

Then later the player says:

```text
I follow the smugglers toward the old relay station.
```

And the application knows:

```python
if engine.can_advance(state):
    draft = await worldsmith.write_next(state, intent)
    state = engine.install(draft)
```

The Master never gets `create_person`, `write_scene`, `create_offer`, `add_secret`, etc.

That keeps its tool surface small, which is already an explicit design goal—you cap engines at fifteen GM tools. 

### Where I *would* refactor Worldsmith

I'd simplify the Python machinery around it rather than merge the AI roles.

Right now there are several concepts:

```text
Authoring
    answer
    prompt
    build

Transition
    ready
    write
    install
    arrival_brief
```



I'd try to make the conceptual API more like:

```python
class Engine:
    async def author_scenario(
        self,
        worldsmith,
        source,
        ...
    ) -> Scenario:
        ...

    async def advance_world(
        self,
        worldsmith,
        game,
        intent,
    ) -> Advance:
        ...
```

Or, if you want the app to retain responsibility for invoking AI:

```python
class WorldRequest:
    prompt: str
    answer_model: type[BaseModel]
    validate: Callable[...]

class Engine:
    def scenario_request(...) -> WorldRequest: ...
    def build_scenario(...) -> Scenario: ...

    def advance_request(...) -> WorldRequest | None: ...
    def apply_advance(...) -> tuple[Fact, ...]: ...
```

That's considerably easier to reason about than separately wiring `ready/write/install/arrival_brief`, while preserving the **important agent boundary**.

### There's also a useful asymmetry here

I wouldn't strive to make Master, Narrator, and Worldsmith architecturally symmetrical.

They're fundamentally different.

**Master** is interactive and procedural. It uses a suite of tools and may make several calls during one turn.

**Narrator** is essentially a pure renderer:

```text
public game projection + settled facts -> prose
```

**Worldsmith** is essentially a structured generator/compiler:

```text
existing world + source + player direction -> validated world addition
```

That asymmetry is actually clean. Trying to make all three fit the same generic "role" abstraction may create more complexity than it removes.

So my revised view is:

**Keep the three-role concept.** The Worldsmith is earning its existence, especially because scenario authoring is core functionality. Simplify the **Worldsmith ↔ engine ↔ runtime protocol**, not the responsibility itself.

And I would still strongly pursue the earlier `SceneEngine` refactor—the duplicated scene-engine wiring looks like a much safer source of substantial simplification than collapsing the AI roles.
