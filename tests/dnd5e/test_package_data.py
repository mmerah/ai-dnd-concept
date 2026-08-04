from importlib.resources import files


def test_default_compiled_srd_pack_is_shipped_as_package_data() -> None:
    pack = files("aidm.engines.dnd5e").joinpath("packs", "srd-2014")

    assert pack.joinpath("manifest.json").is_file()
    assert pack.joinpath("monsters.json").is_file()
    assert pack.joinpath("spells.json").is_file()
