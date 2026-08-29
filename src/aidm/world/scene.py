from collections.abc import Callable, Mapping, Sequence

from aidm.state.entities import Entity, EntityId, Exit, Trait, kind_word
from aidm.state.model import Game, WorldState
from aidm.state.scene import Scene, SceneSection
from aidm.world.topology import children, location_of, player_location

type EntityText = Callable[[Entity], str]
# One parse of the mechanics blob per scene, closed over by the renderer it returns.
type Describer = Callable[[Game], EntityText]
type DirectorSections = Callable[[Game], tuple[tuple[str, str], ...]]


def label(entity: Entity) -> str:
    return f"{entity.name}[{entity.id}]"


def _entity_state(entity: Entity, describe: EntityText) -> str:
    """Traits are core fiction and the engine never sees them; both reach the prompt here."""
    parts = [describe(entity)]
    if entity.traits:
        parts.append("traits: " + ", ".join(_trait(held) for held in entity.traits))
    return "\n".join(part for part in parts if part)


def placement(
    canon: Mapping[EntityId, Entity],
    party: Sequence[EntityId],
    player_id: EntityId,
    entity: Entity,
) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    if entity.id in party:
        return "travelling with the player"
    holder = None if entity.parent_id is None else canon.get(entity.parent_id)
    if holder is None:
        return ""
    if holder.kind == "location":
        return f"at {holder.name}"
    return "carried" if holder.id == player_id else f"held by {holder.name}"


def _entity_lines(
    canon: Mapping[EntityId, Entity],
    party: Sequence[EntityId],
    player_id: EntityId,
    entities: Sequence[Entity],
    describe: EntityText,
    *,
    detailed: bool,
) -> str:
    return (
        "\n".join(
            _with_state(
                _headline(entity, placement(canon, party, player_id, entity))
                + (_detail(entity) if detailed else ""),
                _entity_state(entity, describe),
                "  ",
            )
            for entity in entities
        )
        or "- (none)"
    )


def _character_block(
    player: Entity,
    location: Entity,
    inventory: Sequence[Entity],
    describe: EntityText,
    *,
    detailed: bool,
) -> str:
    held = "\n".join(
        _with_state(
            f"- {label(item)} — {item.brief}{_detail(item) if detailed else ''}",
            _entity_state(item, describe),
            "  ",
        )
        for item in sorted(inventory, key=lambda item: item.name)
    )
    line = _with_state(
        f"{label(player)} — {player.brief} — at {label(location)}",
        _entity_state(player, describe),
    )
    return f"{line}\ninventory:\n{held or '- (none)'}"


def _exit_lines(
    canon: Mapping[EntityId, Entity], exits: Sequence[Exit], *, found_only: bool
) -> str:
    shown = [way for way in exits if way.known or not found_only]
    return "\n".join(_exit_line(canon, way) for way in shown) or "- (none)"


def _reachable_hidden(world: WorldState, here: Entity) -> tuple[Entity, ...]:
    """Unknown canon a turn could touch: here, one exit away, or a signposted location."""
    near = {here.id, *(way.to for way in here.exits)}
    entities = world.entities.values()
    signposted = {way.to for entity in entities if entity.known for way in entity.exits}
    return tuple(
        entity
        for entity in entities
        if not entity.known and (location_of(world, entity) in near or entity.id in signposted)
    )


def _exit_line(canon: Mapping[EntityId, Entity], way: Exit) -> str:
    locked = " — locked" if way.locked else ""
    unfound = " — the player has not found this way yet" if not way.known else ""
    return f"- {canon[way.to].name}[{way.to}]{locked}{unfound}"


def _headline(entity: Entity, placed: str) -> str:
    return (
        f"- {label(entity)} ({kind_word(entity.kind)})"
        f"{f' — {placed}' if placed else ''} — {entity.brief}"
    )


def _detail(entity: Entity) -> str:
    described = f"\n  detail: {entity.description}" if entity.description else ""
    reached = f"\n  when reached: {entity.when_reached}" if entity.when_reached else ""
    return f"{described}{reached}"


def _trait(trait: Trait) -> str:
    name = f"{trait.name}[{trait.id}]"
    return name + (f" — {trait.text}" if trait.text else "")


def _with_state(line: str, state: str, indent: str = "") -> str:
    if not state:
        return line
    block = "\n".join(f"{indent}  {row}" for row in state.splitlines())
    return f"{line}\n{indent}state:\n{block}"


def rooms_scene(
    describer: Describer, director_sections: DirectorSections
) -> Callable[[Game], Scene]:
    def build(state: Game) -> Scene:
        world = state.world
        player = state.player
        location = world.require_kind(player_location(state), "location")
        rest = [one for one in world.entities.values() if one.id != player.id]
        inventory = children(world, player.id, "item")
        carried = {item.id for item in inventory}
        placed = [one for one in rest if one.id not in carried and one.id != location.id]
        where = {one.id: location_of(world, one) for one in placed}
        here = tuple(one for one in rest if one.known and where.get(one.id) == location.id)
        elsewhere = tuple(
            one for one in rest if one.known and where.get(one.id, location.id) != location.id
        )
        hidden = _reachable_hidden(world, location)
        exits = tuple(sorted(location.exits, key=lambda way: world.require(way.to).name))
        describe = describer(state)

        def blocks(*, shown: bool) -> tuple[tuple[str, str], ...]:
            """`shown` is the player's audience: known canon only, and no authored detail."""
            canon = {one.id: one for one in world.entities.values() if one.known or not shown}

            def listed(entities: Sequence[Entity]) -> str:
                return _entity_lines(
                    canon, world.party, player.id, entities, describe, detailed=not shown
                )

            return (
                (
                    "PLAYER CHARACTER",
                    _character_block(player, location, inventory, describe, detailed=not shown),
                ),
                ("HERE WITH THE PLAYER", listed(here)),
                ("EXITS FROM HERE", _exit_lines(canon, exits, found_only=shown)),
                ("KNOWN TO THE PLAYER, BUT ELSEWHERE", listed(elsewhere)),
                ("EXISTS BUT THE PLAYER DOES NOT KNOW IT YET", "" if shown else listed(hidden)),
            )

        sections = tuple(
            SceneSection(title=title, player=text, director=None if text == full else full)
            for (title, text), (_, full) in zip(
                blocks(shown=True), blocks(shown=False), strict=True
            )
        )
        cast = sorted(
            (one for one in here if one.kind != "location"), key=lambda one: one.kind != "actor"
        )
        found = tuple(world.require(way.to) for way in exits if way.known)
        return Scene(
            key=location.id,
            label=location.name,
            summary=location.brief,
            sections=(
                *sections,
                *(SceneSection(title=one, director=body) for one, body in director_sections(state)),
            ),
            public_entity_ids=frozenset(
                {player.id, location.id}
                | {one.id for one in (*inventory, *here, *elsewhere, *found)}
            ),
            present_entity_ids=frozenset(
                {player.id} | {one.id for one in here if one.kind == "actor"}
            ),
            prompts=tuple(
                (
                    _exit_label(world.require(way.to).name, way),
                    f"Go to {world.require(way.to).name}",
                )
                for way in exits
                if way.known
            ),
            art_prompt="\n".join(
                (
                    f"The place: {location.name} — {location.brief}",
                    *(f"Present: {one.name} — {one.brief}" for one in here),
                )
            ),
            art_subject_ids=tuple(one.id for one in cast),
        )

    return build


def _exit_label(name: str, way: Exit) -> str:
    return f"{name} (locked)" if way.locked else name
