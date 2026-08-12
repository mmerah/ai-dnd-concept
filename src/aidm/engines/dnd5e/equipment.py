from collections.abc import Iterable, Iterator, Mapping
from typing import NamedTuple

from aidm.state.base import PLAYER_ID, Entity, EntityId, Slug
from aidm.state.creation import Picks, picked
from aidm.state.packs import CollectionName, Content, ContentRef, Record, is_int_fact

# The pack collection holding one record per starting-equipment group, and one more per option
# that hands over several things at once or leaves a whole category open. Only a group carries
# the `class` fact; that is what tells a group from an option inside it.
COLLECTION: CollectionName = "equipment_options"


class Gear(NamedTuple):
    """One carried item: the world entity the Narrator reads, and the record backing it."""

    entity: Entity
    ref: ContentRef


class _Unarmored(NamedTuple):
    ability: Slug
    with_shield: bool


# Unarmored Defense adds one more ability modifier to the unarmoured 10 + DEX. Authored because
# nothing upstream answers it: `feature_specific` is None for both records and the rule is prose.
_UNARMORED_DEFENSE: Mapping[Slug, _Unarmored] = {
    "barbarian-unarmored-defense": _Unarmored("constitution", True),
    "monk-unarmored-defense": _Unarmored("wisdom", False),
}


# A record's own text is mechanical prose ("Simple Melee weapon. Damage: 1d4 piercing"); an owned
# item's brief is fiction the Narrator reads. Authored because nothing upstream answers it —
# `Equipment.desc` is null for almost every item a character can start out carrying.
_ITEM_BRIEFS: Mapping[Slug, str] = {
    "leather-armor": "A boiled leather cuirass, scuffed pale where the straps rub.",
    "scale-mail": "Overlapping metal scales that rasp with every step, a few at the hem newer.",
    "chain-mail": "A heavy shirt of riveted rings, dull with oil and cold to the touch.",
    "shield": "A banded wooden shield with the paint chipped back to bare grain.",
    "battleaxe": "A bearded axe head on a stout haft, its edge reground into a shallow curve.",
    "blowgun": "A lacquered tube of dark wood, its mouthpiece bound in waxed thread.",
    "club": "A knot of hard wood worn smooth at the grip and dented at the head.",
    "dagger": "A short blade with a nicked edge and a hilt gone dark from handling.",
    "dart": "Slim weighted spikes, each feathered at the tail, kept in a row of belt loops.",
    "flail": "A spiked head on a short chain, marking the haft where it swings back.",
    "glaive": "A long blade socketed on a pole, the wood spliced once below the head.",
    "greataxe": "A broad crescent blade on a long haft, bright where the whetstone passed.",
    "greatclub": "A rough length of trunk banded in iron, far heavier than it looks.",
    "greatsword": "A long two-handed blade, scratched down its flat and heavy in the hands.",
    "halberd": "An axe blade and back-spike on a tall shaft, the spike bent very slightly.",
    "handaxe": "Stubby axes with chipped bits and hafts bound in cord, hung at the hip.",
    "javelin": "Light throwing spears, iron-tipped, their shafts nicked from old landings.",
    "lance": "A tapering shaft with a fluted vamplate, splintered once and lashed tight.",
    "light-hammer": "A short throwing hammer with a square head and a cord through the butt.",
    "longbow": "A tall stave of yew, its string waxed and its grip darkened by sweat.",
    "longsword": "A straight blade with a plain crossguard, the leather grip beginning to fray.",
    "mace": "A flanged iron head on a short shaft, the flanges rounded from use.",
    "maul": "A two-handed sledge with a scarred iron head, its haft wound in leather.",
    "morningstar": "A studded ball fixed to a shaft, two of the studs blunted flat.",
    "net": "A weighted mesh of tarred cord, folded small and smelling of the harbour.",
    "pike": "A very long shaft topped by a narrow spike, awkward anywhere indoors.",
    "crossbow-hand": "A palm-sized crossbow with a stiff prod and a worn thumb latch.",
    "crossbow-heavy": "A broad crossbow with a cranequin, its stock scuffed to bare wood.",
    "crossbow-light": "A slender crossbow with a stiff windlass and a scarred stock.",
    "quarterstaff": "A shoulder-high pole of hard wood, worn glossy where hands have gripped it.",
    "rapier": "A narrow thrusting blade with a swept guard, polished except at the hilt.",
    "scimitar": "A curved single-edged blade, its point still keen and its sheath cracked.",
    "shortbow": "A short curved bow, one nock chipped and the string a little frayed.",
    "shortsword": "A stubby straight blade with a worn grip, quick to draw from the hip.",
    "sickle": "A small hooked blade with a wooden grip, the inner edge honed bright.",
    "sling": "A leather cradle on two braided cords, with a pouch of river stones.",
    "spear": "A long ash shaft with a leaf-shaped iron head, the wood dark below the socket.",
    "trident": "A three-pronged fishing spear, the middle tine longer than the other two.",
    "war-pick": "A narrow beak of steel on a short haft, made for finding gaps in plate.",
    "warhammer": "A blunt-faced hammer with a claw behind it, the face bright from striking.",
    "whip": "A plaited leather lash with a stiff handle, coiled tight at the belt.",
    "amulet": "A small sacred medallion on a plain chain, its stamped face rubbed nearly flat.",
    "arrow": "A bundle of arrows with grey goose fletching, a few shafts slightly bent.",
    "burglars-pack": "A pack that clinks softly with picks, pitons, bell, and hooded lantern.",
    "component-pouch": "A watertight pouch of compartments, faintly bitter with dried herbs.",
    "crossbow-bolt": "Short iron-headed bolts, their vanes flattened from tight packing.",
    "crystal": "A fist-sized clouded crystal, cool in the palm and threaded with old fractures.",
    "diplomats-pack": "A chest of fine clothes, scroll cases, ink, wax, and stoppered perfume.",
    "dungeoneers-pack": "A stout pack of pitons, crowbar, hammer, torches, and coiled rope.",
    "emblem": "A holy sign inlaid in metal, meant to be shown, its edges bright from polishing.",
    "entertainers-pack": "Costumes, candle stubs, and a kit smelling of old greasepaint.",
    "explorers-pack": "Bedroll, mess kit, torches, rations, and hempen rope, tightly packed.",
    "orb": "A heavy glass sphere with a slow flaw turning in its heart, warm where it is held.",
    "priests-pack": "Vestments, candles, an alms box, and incense blocks wrapped in cloth.",
    "reliquary": "A tiny hinged box holding a splinter of bone, its lid worn smooth.",
    "rod": "A short blackened rod with a banded grip, heavier at one end than it looks.",
    "scholars-pack": "Ink, pens, parchment, a small knife, and a thick book with a bent spine.",
    "spellbook": "A leather-bound tome of blank vellum, its covers warped and its clasp bent.",
    "sprig-of-mistletoe": "A sprig of mistletoe, its pale berries wrinkling, its leaves leathery.",
    "staff": "A straight rod of pale wood, capped in tarnished silver at both ends.",
    "totem": "A bundle of feather, fur, and small bones lashed to a carved stub of wood.",
    "wand": "A slim length of wood with a burnt tip, worn pale where fingers close on it.",
    "wooden-staff": "A staff cut whole from a living tree, bark still clinging near the top.",
    "yew-wand": "A short wand of yew, still faintly green under the bark left at its base.",
    "bagpipes": "A bag of stitched hide with three drones, wheezing before it finds its note.",
    "drum": "A shallow hand drum, its skin slack in damp weather and patched at one edge.",
    "dulcimer": "A trapezoid of strung wood with two felted hammers tucked under the strings.",
    "flute": "A wooden flute in three joints, the middle one darkened where it is held.",
    "horn": "A curved horn with a brass rim, dented near the bell and loud past all reason.",
    "lute": "A round-bellied lute with a scratched soundboard and one peg that will not hold.",
    "lyre": "A small lyre with a scuffed frame, its strings sounding a little sour.",
    "pan-flute": "A raft of stopped reeds bound in waxed cord, breathy on the lowest pipes.",
    "shawm": "A conical reed pipe with a flared bell, shrill enough to carry over a crowd.",
    "viol": "A waisted viol with a worn bow, its lowest string replaced and not yet settled.",
    "thieves-tools": "A rolled cloth of picks, file, pliers, and mirror, each pocket shaped.",
}


def groups(content: Content, class_ref: ContentRef) -> tuple[Record, ...]:
    """The class's starting-equipment groups, in the order the SRD writes them."""
    return tuple(
        record
        for ref, record in content.records.items()
        if ref.collection == COLLECTION and record.facts.get("class") == class_ref.index
    )


def chosen_records(content: Content, class_ref: ContentRef, picks: Picks) -> Iterator[Record]:
    """Every group, and each option already picked that still leaves a category open — the rule
    that turns a picked class into its level-1 row, one level further down."""
    pending = list(groups(content, class_ref))
    while pending:
        record = pending.pop(0)
        yield record
        pending.extend(
            content.require(ref)
            for ref in _picked_refs(record, picks)
            if ref.collection == COLLECTION
        )


def starting_gear(content: Content, class_ref: ContentRef, picks: Picks) -> tuple[Gear, ...]:
    carried = [
        ref
        for record in chosen_records(content, class_ref, picks)
        for ref in (*record.granted, *_picked_refs(record, picks))
        if ref.collection != COLLECTION
    ]
    # Two groups can reach one item — a cleric's mace is also "any simple weapon" — and one entity
    # id lands once, so the second pick would vanish instead of buying anything.
    if twice := sorted({content.require(r).name for r in carried if carried.count(r) > 1}):
        raise ValueError(
            f"{', '.join(twice)} is carried twice: choose a different option for one step"
        )
    return tuple(_carried(content, ref) for ref in carried)


def armor_class(
    content: Content,
    carried: Iterable[ContentRef],
    modifiers: Mapping[Slug, int],
    features: Iterable[ContentRef],
) -> int:
    """Worn armour replaces the unarmoured 10 + DEX and a shield adds on top of either. The SRD's
    strength minimum costs speed, which nothing here models, so it cannot make a choice illegal."""
    worn: int | None = None
    shield = 0
    for ref in carried:
        record = content.require(ref)
        bonus = record.facts.get("armor-bonus")
        if is_int_fact(bonus):
            shield += bonus
        base = record.facts.get("armor-base")
        if is_int_fact(base):
            worn = base + _worn_dexterity(record, modifiers["dexterity"])
    if worn is not None:
        return worn + shield
    return 10 + modifiers["dexterity"] + shield + _unarmored_defense(modifiers, features, shield)


def verify(content: Content, class_refs: Iterable[ContentRef]) -> None:
    """A regenerated pack refuses at engine build, not at play: every offered class needs
    equipment groups, every item any of them can reach needs a brief, and `armor_class` needs the
    class to be unable to wear two armours at once."""
    for class_ref in class_refs:
        found = groups(content, class_ref)
        if not found:
            raise ValueError(f"{class_ref} ships no starting equipment")
        armours = sum(_most_armour(content, record) for record in found)
        if armours > 1:
            raise ValueError(f"{class_ref} can start wearing {armours} armours, and AC adds one")
        defense = f"{class_ref.index}-unarmored-defense"
        if defense in _UNARMORED_DEFENSE:
            _ = content.require(class_ref.sibling("features", defense))
        for ref in _reachable(content, found):
            if ref.index not in _ITEM_BRIEFS:
                raise ValueError(f"{ref} has no authored brief for the item it grants")


def _most_armour(content: Content, record: Record) -> int:
    """The most worn armour one answer to this record can hand over: `armor_class` keeps the last
    it sees, so a second would go unread rather than refuse."""
    worn = sum(1 for ref in record.granted if _worn(content, ref))
    if record.choose is None:
        return worn
    each = sorted(
        _most_armour(content, content.require(ref))
        if ref.collection == COLLECTION
        else int(_worn(content, ref))
        for ref in record.options
    )
    return worn + sum(each[-record.choose :])


def _reachable(content: Content, records: Iterable[Record]) -> Iterator[ContentRef]:
    """Every item a group can end up handing over, through the option records it offers."""
    for record in records:
        for ref in (*record.granted, *record.options):
            if ref.collection == COLLECTION:
                yield from _reachable(content, (content.require(ref),))
            else:
                yield ref


def _picked_refs(record: Record, picks: Picks) -> tuple[ContentRef, ...]:
    chosen = set(picked(picks, record.index))
    return tuple(ref for ref in record.options if ref.index in chosen)


def _worn(content: Content, ref: ContentRef) -> bool:
    return is_int_fact(content.require(ref).facts.get("armor-base"))


def _carried(content: Content, ref: ContentRef) -> Gear:
    record = content.require(ref)
    brief = _ITEM_BRIEFS.get(ref.index)
    if brief is None:
        raise ValueError(f"{ref} has no authored brief for the item it grants")
    return Gear(
        entity=Entity(
            id=EntityId(ref.index),
            kind="item",
            name=record.name,
            brief=brief,
            known=True,
            parent_id=PLAYER_ID,
        ),
        ref=ref,
    )


def _unarmored_defense(
    modifiers: Mapping[Slug, int], features: Iterable[ContentRef], shield: int
) -> int:
    return sum(
        modifiers[held.ability]
        for ref in features
        if (held := _UNARMORED_DEFENSE.get(ref.index)) is not None
        if held.with_shield or not shield
    )


def _worn_dexterity(record: Record, modifier: int) -> int:
    if "add-dex-modifier" not in record.tags:
        return 0
    limit = record.facts.get("dex-limit")
    return min(modifier, limit) if is_int_fact(limit) else modifier
