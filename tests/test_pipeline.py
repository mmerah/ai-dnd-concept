"""Full pipeline runs with every role stubbed — no network."""

import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm import store
from aidm.agents import creator as creator_module
from aidm.agents import director as director_module
from aidm.agents import maintainer as maintainer_module
from aidm.agents import narrator as narrator_module
from aidm.agents.context import Scene
from aidm.agents.director import direct
from aidm.agents.history import exchanges_to_messages
from aidm.domain.models import (
    PLAYER_ID,
    ActorEntity,
    EntityId,
    Exchange,
    GameState,
    ItemEntity,
    updated,
)
from aidm.pipeline import run_turn

LIBRARY = store.library()  # the shipped pack; no test here plays against a synthetic one

Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def known_ids(state: GameState) -> set[EntityId]:
    return {e.id for e in state.world.entities.values() if e.known and e.id != PLAYER_ID}


def scene(state: GameState) -> Scene:
    return Scene.of(state)


def structured(**output: object) -> Stub:
    """Structured roles use NativeOutput, so the model replies with schema-shaped JSON text."""

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(output))])

    return stub


def text(body: str) -> Stub:
    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(body)])

    return stub


def stubs(
    stack: ExitStack,
    *,
    director: Stub | None = None,
    narrator: Stub | None = None,
    maintainer: Stub | None = None,
    creator: Stub | None = None,
) -> None:
    """Explicit per-role params, so a renamed role module is a type error, not a KeyError."""
    for module, stub in (
        (director_module, director),
        (narrator_module, narrator),
        (maintainer_module, maintainer),
        (creator_module, creator),
    ):
        if stub is not None:
            stack.enter_context(module.agent().override(model=FunctionModel(stub)))


async def test_search_applies_mechanics_and_creates_nothing(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Kael feels along the flagstone for the vault map.",
                tone="hushed",
                mechanics=[
                    {
                        "action": "roll_check",
                        "ability": "wisdom",
                        "dc": 12,
                        "on_success": [{"action": "take_item", "item_id": "vault_map"}],
                    }
                ],
            ),
            narrator=text("Your fingers find a creased chart beneath the flagstone."),
            maintainer=structured(requests=[]),
        )
        # roll 13 + 2 >= 12
        turn = await run_turn(state, "I search the study.", rng=Random(0), library=LIBRARY)

    # taking a canon item reveals it: inventory and canon can never disagree
    kinds = [e.type for e in turn.events]
    assert kinds == ["dc_rolled", "entity_discovered", "item_moved"]
    carried = {e.id for e in turn.state.world.carried_by(PLAYER_ID)}
    assert carried == {EntityId("lantern"), EntityId("vault_map")}
    assert known_ids(turn.state) == {"study", "mara", "vault_map", "lantern"}
    assert turn.created == []
    assert turn.state.turn == 1
    assert turn.state.history[-1].prompt == "I search the study."


async def test_existing_canon_is_revealed_not_created(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Mara points Kael toward Elena.",
                tone="wary",
                speaker_id="mara",
                mechanics=[{"action": "discover", "entity_id": "elena"}],
            ),
            narrator=text("'Elena would know,' Mara says."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "@Mara who can I ask for help?", library=LIBRARY)

    assert known_ids(turn.state) == {"study", "mara", "elena", "lantern"}
    assert turn.created == []  # revealed from canon, not grown


async def test_an_unbacked_name_is_grown_not_resolved(state: GameState) -> None:
    """The Director cannot reference an id it was never shown, so a name only the Narrator invents
    changes nothing mechanically and is grown into canon by the Maintainer instead."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Nobody in canon fits; Kael must look elsewhere.", tone="dry"
            ),
            narrator=text("'Try Elgin, the apothecary by the east gate,' he mutters."),
            maintainer=structured(
                requests=[{"kind": "actor", "name": "Elgin", "brief": "An apothecary."}]
            ),
            creator=structured(description="A stooped herbalist.", hook="He trades in rumours."),
        )
        turn = await run_turn(state, "@Tomas who can I ask for help?", library=LIBRARY)

    assert turn.events == []  # an empty plan resolves to nothing
    (elgin,) = turn.created
    assert (elgin.id, elgin.known, elgin.authored) == ("elgin", True, False)
    assert isinstance(elgin, ActorEntity) and elgin.location_id == "study"  # no location -> here
    assert list(turn.state.world.entities.values())[-1] == elgin  # created entities go last
    assert turn.state.world.entities[EntityId("vault")].known is False  # authored canon untouched


async def test_a_grown_item_is_contained_by_the_place_it_appears(state: GameState) -> None:
    """Each kind names its place through a different field, so growth must be exercised at every
    kind: an item carries `container_id` where an actor carries `location_id`."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(intent="i", tone="t"),
            narrator=text("A rusted key lies among the papers."),
            maintainer=structured(
                requests=[{"kind": "item", "name": "a rusted key", "brief": "Small and pitted."}]
            ),
            creator=structured(description="d", hook="h"),
        )
        turn = await run_turn(state, "I search the desk.", library=LIBRARY)

    (key,) = turn.created
    assert isinstance(key, ItemEntity) and key.container_id == "study"  # no location -> here


async def test_a_grown_entity_is_placed_in_a_location_grown_the_same_turn(state: GameState) -> None:
    """The Maintainer can request a new location and put a new NPC there in one batch; the location
    is created first, so the NPC resolves to its minted id — not to the player's location."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(intent="i", tone="t"),
            narrator=text("Beyond the arch, a monk named Anselm bends over a desk."),
            maintainer=structured(
                requests=[
                    {"kind": "actor", "name": "Anselm", "brief": "A monk.", "location": "a crypt"},
                    {"kind": "location", "name": "a crypt", "brief": "Cold stone."},
                ]
            ),
            creator=structured(description="d", hook="h"),
        )
        turn = await run_turn(state, "What is beyond the arch?", library=LIBRARY)

    entities = turn.state.world.entities
    crypt = next(e for e in entities.values() if e.name == "a crypt")
    anselm = next(e for e in entities.values() if e.name == "Anselm")
    assert isinstance(anselm, ActorEntity) and anselm.location_id == crypt.id  # not the study


async def test_growth_is_capped(state: GameState) -> None:
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(intent="A crowd presses in.", tone="busy"),
            narrator=text("Names fly past you."),
            maintainer=structured(
                requests=[{"kind": "actor", "name": f"N{i}", "brief": "b"} for i in range(6)]
            ),
            creator=structured(description="d", hook="h"),
        )
        turn = await run_turn(state, "Who is here?", library=LIBRARY)

    assert len(turn.created) == 3
    # the 3 over-cap requests are recorded, not silently dropped
    assert [r.reason for r in turn.rejected] == ["over_cap", "over_cap", "over_cap"]


@pytest.mark.parametrize(
    "consequence",
    [
        {"action": "discover", "entity_id": "ghost"},
        {"action": "move", "location_id": "ghost"},  # an id no list ever showed
        {"action": "move", "location_id": "mara"},  # a real id, but an actor is not a location
        {"action": "take_item", "item_id": "study"},  # a location is not an item
        {"action": "damage", "amount": 2, "target_id": "study"},  # a location has no hit points
        # the player is an actor in canon now, so naming them here passes the kind check
        {"action": "give_item", "item_id": "lantern", "actor_id": "player"},
    ],
)
async def test_a_plan_referencing_canon_wrongly_is_rejected(
    state: GameState, consequence: dict[str, object]
) -> None:
    """The Director's output validator relocates the Actor's per-tool ModelRetry to id selection.
    An id must both exist and name the kind of thing the consequence acts on."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(intent="i", tone="t", mechanics=[consequence]),
        )
        with pytest.raises(UnexpectedModelBehavior):
            await direct("go", scene(state))


async def test_a_bad_id_nested_in_a_branch_is_caught_as_well(state: GameState) -> None:
    """Ids are read off every field marked `References`, in a check's branches as much as at the
    top level — so a branch cannot smuggle an unknown id past the validator."""
    nested = {
        "action": "roll_check",
        "ability": "wisdom",
        "dc": 10,
        "on_failure": [{"action": "take_item", "item_id": "ghost"}],
    }
    with ExitStack() as stack:
        stubs(stack, director=structured(intent="i", tone="t", mechanics=[nested]))
        with pytest.raises(UnexpectedModelBehavior):
            await direct("pry the lid", scene(state))


async def test_a_dice_amount_is_rolled_by_the_engine_not_chosen_by_the_director(
    state: GameState,
) -> None:
    """Improvised randomness survives the fold: the Director names dice, the engine rolls them.
    '2d1' is deterministic, so the player ends on 8 hp."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="A dart springs from the wall.",
                tone="sharp",
                mechanics=[{"action": "damage", "amount": "2d1"}],
            ),
            narrator=text("Something bites your calf."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "I step on the loose flagstone.", library=LIBRARY)

    assert [e.type for e in turn.events] == ["dice_rolled", "hp_changed"]
    assert turn.state.player.stats.hp == 8


async def test_a_hidden_speaker_is_a_retry_not_a_downstream_failure(state: GameState) -> None:
    """A speaker the player has not met is caught as a retry in the validator, so it never reaches
    the Narrator's hard-failing view."""
    with ExitStack() as stack:
        stubs(stack, director=structured(intent="i", tone="t", speaker_id="elena"))  # known=False
        with pytest.raises(UnexpectedModelBehavior):
            await direct("talk to her", scene(state))


@pytest.mark.parametrize(
    "direction",
    [
        {"speaker_id": "mara"},  # you could once address any actor from anywhere
        {"mechanics": [{"action": "damage", "amount": 2, "target_id": "mara"}]},
        {"mechanics": [{"action": "give_item", "item_id": "lantern", "actor_id": "mara"}]},
    ],
)
async def test_acting_on_an_actor_who_is_elsewhere_is_a_retry(
    state: GameState, direction: dict[str, object]
) -> None:
    """`References(present=True)` is one rule for every id that must be here with the player. With
    the player in the vault, Mara (known, but in the study) is out of reach of all three — as a
    retry the model can fix, never the dropped turn the resolver's own guard would cost."""
    player = updated(state.player, location_id=EntityId("vault"))
    entities = {**state.world.entities, PLAYER_ID: player}
    in_vault = updated(state, world=updated(state.world, entities=entities))
    with ExitStack() as stack:
        stubs(stack, director=structured(intent="i", tone="t", **direction))
        with pytest.raises(UnexpectedModelBehavior):
            await direct("reach for Mara", scene(in_vault))


async def test_moving_to_hidden_canon_reveals_it_end_to_end(state: GameState) -> None:
    """Reveal-on-arrival must survive the whole pipeline, not just the resolver."""
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="Kael descends toward the vault.",
                tone="cold",
                mechanics=[{"action": "move", "location_id": "vault"}],
            ),
            narrator=text("The stair opens into a low, cold chamber."),
            maintainer=structured(requests=[]),
        )
        turn = await run_turn(state, "I go down to the vault.", library=LIBRARY)

    assert [e.type for e in turn.events] == ["entity_discovered", "moved"]
    assert turn.state.player.location_id == "vault"
    assert known_ids(turn.state) == {"study", "vault", "mara", "lantern"}
    assert turn.created == []


def test_exchanges_become_alternating_messages() -> None:
    messages = exchanges_to_messages(
        [Exchange(prompt="I open the door.", narration="It creaks wide.")]
    )
    assert [type(m) for m in messages] == [ModelRequest, ModelResponse]


async def test_failing_role_leaves_state_untouched(state: GameState) -> None:
    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("narrator exploded")

    before = state.model_dump_json()
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(
                intent="anything",
                tone="grim",
                mechanics=[{"action": "damage", "amount": 3}],
            ),
            narrator=boom,
        )
        with pytest.raises(RuntimeError):
            await run_turn(state, "I kick the door.", library=LIBRARY)

    assert state.model_dump_json() == before
