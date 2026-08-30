"""Probe: the drowned-road fixture the scene-kit probe played against. Reference only."""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from kit import Entity, Scene, SceneState, Sheet, Thread

SOURCE = """THE DROWNED ROAD — a short solo adventure.

The valley of Saint-Ivo flooded nine years ago when the dam at Mourn broke. The village
drowned in a night. Since then the water has never fully left: the road runs a foot under
it for three miles, and the chapel spire still stands above the surface.

People still walk the drowned road. They must, to reach the mill at Carrow on the far side.
They walk it fast, and they do not stop at the chapel.

THE CHAPEL. The bell tower is dry above the waterline. A rope hangs from the bell. The
villagers say the bell rang the night of the flood, and rang for three days after, though
nobody was left to ring it. Inside, under the water, the pews are still in rows.

THE FERRYMAN, GIDEON MARCH. Keeps a flat-bottomed punt at the east bank. He will carry you
for a coin, but not past the chapel — he goes around, which takes till dark. He lost a
daughter, Wren, in the flood. He has never said so aloud.

THE MILL AT CARROW. Working again these two years. The miller pays for grain brought
across. Nobody asks how the grain stays dry.

WHAT IS ACTUALLY HAPPENING. Wren March did not drown. She was pulled out by something in
the water and has lived under the chapel since, changed. She rings the bell. She is waiting
for her father to come and find her, and she has stopped being able to tell waiting from
hunting.

COMPLICATIONS TO USE. A body surfaces face-down and is not dead. The water rises a foot an
hour and nobody says why. A traveller on the road insists they crossed yesterday, though
the road has been shut a week. The bell rings while you are looking at it and the rope
does not move.
"""

GUIDANCE = ("LONER 3E: every actor needs a sheet with a concept and any fitting skills, "
            "frailties or gear as freeform tags, plus luck (1-6). Items and scenery need no "
            "sheet. Tags are plain descriptions, not a fixed list.")

def opening() -> SceneState:
    cast = {
        "player": Entity(id="player", kind="actor", name="Kael", brief="a courier who walks "
                         "roads other people will not", known=True,
                         sheet=Sheet(concept="road-worn courier",
                                     skills=("read weather", "keep walking"),
                                     frailties=("owes money in three towns",),
                                     gear=("oilskin satchel", "short knife"), luck=6)),
        "gideon": Entity(id="gideon", kind="actor", name="Gideon March",
                         brief="the ferryman; grey, careful, will not go past the chapel",
                         known=True, sheet=Sheet(concept="ferryman of the drowned road",
                                                 skills=("read water", "hold a punt steady"),
                                                 frailties=("will not speak of his daughter",),
                                                 gear=("flat-bottomed punt", "long pole"), luck=5)),
        "punt": Entity(id="punt", kind="item", name="the punt",
                       brief="a flat-bottomed boat, poled not rowed", known=True),
        "bell-rope": Entity(id="bell-rope", kind="prop", name="the bell rope",
                            brief="hangs from the tower, wet to the height of a man", known=True),
        "wren": Entity(id="wren", kind="actor", name="Wren",
                       brief="something under the chapel that was a girl, and rings the bell",
                       known=False, sheet=Sheet(concept="the one the water kept",
                                                skills=("move unseen in water", "sound like a child"),
                                                frailties=("cannot leave the chapel",),
                                                gear=(), luck=6)),
        "wrens-shoe": Entity(id="wrens-shoe", kind="item", name="a child's shoe",
                             brief="small, buckled, and not nine years rotted", known=False),
    }
    scene = Scene(
        id="east-bank", title="The East Bank, an hour before dark",
        situation=("Flat brown water to the horizon, and the line of the drowned road just "
                   "under it, marked by posts. The chapel spire stands a mile out. Gideon "
                   "March has his punt against the bank and is not getting into it. The "
                   "light is going."),
        present=("player", "gideon", "punt"), hidden=("wrens-shoe",),
        note="Gideon will not go past the chapel. Pressing him about why is how Wren's name "
             "first surfaces. The shoe is caught under the punt's bow.")
    return SceneState(
        cast=cast, current=scene, player_id="player", source=SOURCE,
        threads={"the-bell": Thread(id="the-bell", title="Who rings the bell",
                                    note="Wren. The player must not learn this cheaply."),
                 "cross-before-dark": Thread(id="cross-before-dark",
                                             title="Reach the mill at Carrow",
                                             note="Gideon's way around takes till dark.")})
