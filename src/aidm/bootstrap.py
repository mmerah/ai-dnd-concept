"""How the application is assembled: the one place that reads configuration, loads packs and names
files. Everything below it takes its collaborators as parameters, which is what lets the game run
from a script, and a test wire the same pieces without a saves directory.

Called once, at startup. A second call would compile the ruleset again — cheap, but it would also
mean two answers to "what is this build playing"."""

from .application.game import GameApplication
from .config import Settings
from .content import load
from .engine.pack_ruleset import compile_ruleset
from .pipeline import TurnOptions
from .store import FileSaves, FileTraces, read_scenario, read_sheet

SLUG = "poc"
SCENARIO = "whispering_vault"
CHARACTER = "kael"


def create_application(
    conf: Settings, slug: str = SLUG, scenario: str = SCENARIO, character: str = CHARACTER
) -> GameApplication:
    """The whole wiring, in one expression: packs, the ruleset compiled from them, the two files a
    game lives in, and the per-turn budgets. Reading the save is the application's own first act."""
    library = load(conf.packs)
    return GameApplication(
        slug=slug,
        scenario=read_scenario(conf.scenarios_dir / f"{scenario}.json"),
        sheet=read_sheet(conf.characters_dir / f"{character}.json"),
        library=library,
        ruleset=compile_ruleset(library),
        saves=FileSaves(conf.saves_dir),
        traces=FileTraces(conf.saves_dir),
        options=TurnOptions(history_window=conf.history_window, max_growth=conf.max_growth),
    )
