from .application.game import GameApplication
from .config import Settings
from .content.library import load
from .engine.pack_ruleset import compile_ruleset
from .pipeline import TurnOptions
from .store import FileSaves, FileTraces, read_scenario, read_sheet

SLUG = "poc"
SCENARIO = "whispering_vault"
CHARACTER = "kael"


def create_application(
    conf: Settings, slug: str = SLUG, scenario: str = SCENARIO, character: str = CHARACTER
) -> GameApplication:
    return GameApplication(
        slug=slug,
        scenario=read_scenario(conf.scenarios_dir / f"{scenario}.json"),
        sheet=read_sheet(conf.characters_dir / f"{character}.json"),
        ruleset=compile_ruleset(load(conf.packs)),
        saves=FileSaves(conf.saves_dir),
        traces=FileTraces(conf.saves_dir),
        options=TurnOptions(history_window=conf.history_window, max_growth=conf.max_growth),
    )
