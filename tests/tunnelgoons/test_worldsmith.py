from collections.abc import Callable

from pydantic import BaseModel
from support.table import TUNNELGOONS, game, narrowed
from support.tunnelgoons import small_world

from aidm.core.entities import EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.rooms.drafts import MapDraft
from aidm.engines.rooms.engine import MORE_MAP
from aidm.engines.rooms.world import Item, Place, Way
from aidm.engines.rooms.worldsmith import extension_refusal, map_refusal
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.world import Npc, TunnelGoonsGame
from aidm.engines.tunnelgoons.worldsmith import AUTHORING

ENGINE = TunnelGoonsEngine()

ONLY = EntityId("only")
HIDDEN = EntityId("hidden")
FAR_HALL = EntityId("far-hall")
FAR_VAULT = EntityId("far-vault")
FAR_ITEM = EntityId("far-item")
HALL = EntityId("hall")

THIN = MapDraft[Npc](
    places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
    start=ONLY,
)


def _tunnelgoons_game() -> TunnelGoonsGame:
    _, state = game(TUNNELGOONS)
    state = narrowed(state, TunnelGoonsGame)
    return state


def _region() -> MapDraft[Npc]:
    return MapDraft[Npc](
        places={
            FAR_HALL: Place(id=FAR_HALL, name="Far Hall", brief="b", known=False, description="d"),
            FAR_VAULT: Place(
                id=FAR_VAULT, name="Far Vault", brief="b", known=False, description="d"
            ),
        },
        ways={FAR_HALL: [Way(to=FAR_VAULT)]},
        items={FAR_ITEM: Item(id=FAR_ITEM, name="Far Item", brief="b", known=False, on=FAR_HALL)},
        start=FAR_HALL,
    )


def _wide_region() -> MapDraft[Npc]:
    canon = _tunnelgoons_game().payload
    return MapDraft[Npc](
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.current.id,
    )


def test_a_one_place_map_with_no_ways_passes_the_map_bar_and_builds() -> None:
    assert map_refusal(THIN) is None

    built = ENGINE.build_scenario(
        ScenarioMeta(title="Only", premise="", scope="One room, one visit."), (), THIN, "source"
    )

    assert built.payload.start == ONLY


def test_an_extension_of_one_hidden_place_with_no_ways_installs_hidden() -> None:
    draft = _tunnelgoons_game().draft()
    extension = MapDraft[Npc](
        places={HIDDEN: Place(id=HIDDEN, name="Hidden", brief="b", known=False, description="d")},
        start=HIDDEN,
    )
    assert extension_refusal(extension, draft.payload) is None

    facts = ENGINE.install_extension(draft, extension)

    assert [fact.kind for fact in facts] == ["region_added"]
    assert not facts[0].told
    assert not draft.payload.places[HIDDEN].known
    assert draft.payload.way(draft.payload.current.id, HIDDEN) is not None


def test_the_shipped_scenario_passes_the_map_bar() -> None:
    assert map_refusal(_wide_region()) is None


def test_attach_joins_at_the_current_place_and_the_world_validates() -> None:
    state = small_world()
    world = state.payload
    anchor = world.current.id

    region = _region()
    world.attach(region, region.start)

    assert FAR_HALL in world.places
    assert FAR_VAULT in world.places
    assert world.way(anchor, FAR_HALL) is not None
    assert world.way(FAR_HALL, anchor) is not None


def test_a_region_reusing_an_id_already_in_the_world_is_refused() -> None:
    state = small_world()
    reused = _region().model_copy(
        update={
            "places": {
                HALL: Place(id=HALL, name="Hall Again", brief="b", known=False, description="d"),
                FAR_VAULT: Place(
                    id=FAR_VAULT, name="Far Vault", brief="b", known=False, description="d"
                ),
            },
            "ways": {HALL: [Way(to=FAR_VAULT)]},
            "start": HALL,
        }
    )

    refused = extension_refusal(reused, state.payload)
    assert refused is not None
    assert "not already in the world" in refused


def test_more_map_is_offered_only_once_every_place_is_known() -> None:
    state = small_world()
    assert ENGINE.player_view(state).action is None

    draft = state.draft()
    for place in draft.payload.places.values():
        place.known = True
    assert ENGINE.player_view(draft.commit()).action == MORE_MAP


def test_install_extension_on_a_game_from_the_engine() -> None:
    draft = _tunnelgoons_game().draft()
    anchor = draft.payload.current.id

    facts = ENGINE.install_extension(draft, _region())

    assert [fact.kind for fact in facts] == ["region_added"]
    assert not facts[0].told
    assert FAR_HALL in draft.payload.places
    assert draft.payload.way(anchor, FAR_HALL) is not None


def test_attach_appends_unknown_ways_both_directions() -> None:
    state = small_world()
    world = state.payload
    anchor = world.current.id
    region = _region()

    world.attach(region, region.start)

    out = world.way(anchor, FAR_HALL)
    back = world.way(FAR_HALL, anchor)
    assert out is not None and not out.known
    assert back is not None and not back.known


async def test_write_extension_asks_for_the_map_draft() -> None:
    recorded: list[type[BaseModel]] = []
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        recorded.append(model)
        prompts.append(prompt)
        return model.model_validate(THIN.model_dump())

    _ = await ENGINE.write_extension(small_world(), "Push north.", answer)

    assert recorded == [MapDraft[Npc]]
    # The `hp` rule reaches the worldsmith only through the engine's guidance.
    assert AUTHORING in prompts[0]


async def test_write_extension_prompt_carries_scenes_so_far() -> None:
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        return model.model_validate(THIN.model_dump())

    _ = await ENGINE.write_extension(small_world(), "Nose around the docks.", answer)

    assert "SCENES SO FAR" in prompts[0]
