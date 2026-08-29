from aidm.state.entities import DEAD, Entity, EntityId, Exit, Slug, Trait, slug
from aidm.state.facts import Fact, entity_fact
from aidm.state.model import Game
from aidm.state.tools import Validate
from aidm.world.succession import succession_decision
from aidm.world.topology import children, is_here, player_location


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def reveal(draft: Game, entity_id: EntityId) -> list[Fact]:
    """Give standalone reveals a card; byproduct reveals remain card-less."""
    entity = draft.world.require(entity_id)
    facts = draft.reveal(entity)
    if not facts:
        return facts
    return [facts[0].model_copy(update={"card": _sentence(f"{entity.name} discovered")})]


def require_actor_here(state: Game, actor_id: EntityId) -> Entity:
    actor = state.world.require_kind(actor_id, "actor")
    if actor.trait(DEAD) is not None:
        # ponytail: no resurrection path — a corpse takes no trait either way; restart is the exit.
        raise ValueError(f"{actor.name} is dead; they take no further part.")
    if actor_id != state.player_id and not is_here(state, actor):
        raise ValueError(
            f"{actor_id!r} is not here with the player. "
            "Move them here first, or act on who is here."
        )
    return actor


def kill(draft: Game, actor_id: EntityId, validate: Validate) -> list[Fact]:
    actor = draft.world.require_kind(actor_id, "actor")
    if actor.trait(DEAD) is not None:
        raise ValueError(f"{actor.name} is already dead")
    if actor_id != draft.player_id and not is_here(draft, actor):
        raise ValueError(f"{actor_id!r} is not here with the player, so they cannot die here")
    facts = draft.reveal(actor)
    actor.traits.append(Trait(id=DEAD, name="Dead"))
    carried = children(draft.world, actor_id, "item")
    if carried and actor.parent_id is not None:
        where = draft.world.require(actor.parent_id)
        for item in carried:
            item.parent_id = where.id
        loose = ", ".join(draft.label(item) for item in carried)
        # Untold: a dropped item may still be unrevealed, and its name must not reach the narrator.
        facts.append(
            Fact(kind="items_dropped", trace=f"{loose} fell loose at {draft.label(where)}")
        )
    if actor_id in draft.world.party:
        draft.world.party.remove(actor_id)
    facts.append(
        entity_fact(
            actor, "actor_killed", f"{draft.label(actor)} is dead", card=f"{actor.name} is dead"
        )
    )
    if actor_id == draft.player_id:
        draft.pending = succession_decision(draft, validate)
    return facts


def reveal_target(draft: Game, entity_id: EntityId) -> tuple[Entity, list[Fact]]:
    """A place or a thing is not revealed by being acted on, so no unlearned name leaks."""
    entity = draft.world.require(entity_id)
    seen = draft.reveal(require_actor_here(draft, entity_id)) if entity.kind == "actor" else []
    return entity, seen


def _walkable_exit(draft: Game, here: Entity, destination: Entity) -> Exit:
    found = here.exit_to(destination.id)
    if found is None:
        open_exits = [draft.world.require(way.to).name for way in here.exits if not way.locked]
        reachable = ", ".join(open_exits) or "(none)"
        raise ValueError(
            f"no way leads from here to {destination.name}. From here the player can reach: "
            f"{reachable}"
        )
    if found.locked:
        raise ValueError(f"the way to {destination.name} is locked and must be dealt with first")
    return found


def move(draft: Game, entity_id: EntityId, to_id: EntityId) -> list[Fact]:
    moving = draft.world.require(entity_id)
    if moving.kind == "item":
        return _move_item(draft, moving, to_id)
    return _move_actor(draft, entity_id, to_id)


def _move_actor(draft: Game, actor_id: EntityId, to_id: EntityId) -> list[Fact]:
    destination = draft.world.require_kind(to_id, "location")
    here = player_location(draft)
    if actor_id == draft.player_id:
        way = _walkable_exit(draft, draft.world.require(here), destination)
        # Arrival reveals both directions because the player can see the way back.
        way.known = True
        back = destination.exit_to(here)
        if back is not None:
            back.known = True
        facts = [*draft.reveal(destination), draft.move(draft.player, destination)]
        for member_id in draft.world.party:
            member = draft.world.require_kind(member_id, "actor")
            if member.parent_id != destination.id:
                # The player's move already supplies the single travel card.
                followed = draft.move(member, destination)
                facts.append(followed.model_copy(update={"card": ""}))
        return facts
    actor = draft.world.require_kind(actor_id, "actor")
    if actor.parent_id != here and destination.id != here:
        raise ValueError(f"movement of actor {actor_id!r} would not be witnessed")
    revealed = draft.reveal(actor) if destination.id == here else []
    return [*revealed, draft.move(actor, destination)]


def _move_item(draft: Game, item: Entity, to_id: EntityId) -> list[Fact]:
    if to_id == draft.player_id:
        if item.parent_id == draft.player_id:
            raise ValueError(f"the player already carries item {item.id!r}")
        if item.parent_id != player_location(draft):
            raise ValueError(f"item {item.id!r} is not loose at the player's location")
        return [*draft.reveal(item), draft.move(item, draft.player)]
    receiver = draft.world.require(to_id)
    if receiver.kind == "location":
        if receiver.id != player_location(draft):
            raise ValueError("an item is set down at the player's own location, nowhere else")
    else:
        receiver = require_actor_here(draft, to_id)
    if item.parent_id != draft.player_id:
        raise ValueError(f"the player does not carry item {item.id!r}")
    return [*draft.reveal(item), draft.move(item, receiver)]


def improvise(draft: Game, item_name: str) -> list[Fact]:
    item = Entity(
        id=EntityId(slug(item_name, draft.world.all_ids())),
        kind="item",
        name=item_name,
        brief=item_name,
        known=True,
        parent_id=player_location(draft),
    )
    created = draft.add(item)
    moved = draft.move(item, draft.player)
    return [created, moved]


def add_trait(draft: Game, entity_id: EntityId, name: str, text: str = "") -> list[Fact]:
    entity, seen = reveal_target(draft, entity_id)
    trait_id = slug(name, ())
    # Only `kill` may end a life: it drops what the dead carried and offers the succession.
    if trait_id == DEAD:
        raise ValueError(f"call kill to record a death, not add_trait with {name!r}")
    if entity.trait(trait_id) is not None:
        raise ValueError(f"{entity.name} already carries the trait {name!r}")
    entity.traits.append(Trait(id=trait_id, name=name, text=text))
    trace = f"{draft.label(entity)} gained the trait {name}[{trait_id}]"
    if text:
        trace += f" — {text}"
    return [*seen, entity_fact(entity, "trait_added", trace, card=f"{entity.name} gained {name}")]


def remove_trait(draft: Game, entity_id: EntityId, trait_id: Slug) -> list[Fact]:
    entity, seen = reveal_target(draft, entity_id)
    held = entity.trait(trait_id)
    if held is None:
        carried = ", ".join(sorted(one.id for one in entity.traits)) or "(none)"
        raise ValueError(
            f"{entity.name} carries no trait {trait_id!r}. Their traits are: {carried}"
        )
    entity.traits.remove(held)
    trace = f"{draft.label(entity)} lost the trait {held.name}[{held.id}]"
    card = f"{entity.name} lost {held.name}"
    return [*seen, entity_fact(entity, "trait_removed", trace, card=card)]


def unlock_exit(draft: Game, to_id: EntityId) -> list[Fact]:
    here = draft.world.require_kind(player_location(draft), "location")
    there = draft.world.require_kind(to_id, "location")
    way = here.exit_to(to_id)
    if way is None:
        raise ValueError(f"no way leads from {here.name} to {there.name}")
    if not way.locked:
        raise ValueError(f"the way from {here.name} to {there.name} is not locked")
    way.locked = False
    # A lock holds both ways, so leaving the way back shut would strand the player behind it.
    back = there.exit_to(here.id)
    if back is not None:
        back.locked = False
    return [
        entity_fact(
            here,
            "exit_unlocked",
            f"the way from {here.name}[{here.id}] to {there.name}[{there.id}] is unlocked",
            narrate=way.known,
            card=_sentence(f"{there.name} unlocked"),
        )
    ]


def join_party(draft: Game, actor_id: EntityId) -> list[Fact]:
    actor = require_actor_here(draft, actor_id)
    if actor_id in draft.world.party:
        raise ValueError(f"{actor.name} already travels with the player")
    seen = draft.reveal(actor)
    draft.world.party.append(actor_id)
    trace = f"{draft.label(actor)} travels with the player"
    card = f"{actor.name} joins your party"
    return [*seen, entity_fact(actor, "party_joined", trace, card=card)]


def leave_party(draft: Game, actor_id: EntityId) -> list[Fact]:
    actor = draft.world.require_kind(actor_id, "actor")
    if actor_id not in draft.world.party:
        raise ValueError(f"{actor.name} does not travel with the player")
    draft.world.party.remove(actor_id)
    trace = f"{draft.label(actor)} no longer travels with the player"
    card = f"{actor.name} leaves your party"
    return [entity_fact(actor, "party_left", trace, card=card)]
