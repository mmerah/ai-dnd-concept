from pathlib import Path

from aidm.state.packs import CollectionName

ENGINE_DIR = Path(__file__).parent
# Collections whose int facts land on the sheet of any entity that refs a record in them.
PROJECTING: tuple[CollectionName, ...] = ("classes", "races", "monsters")
