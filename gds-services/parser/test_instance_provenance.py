import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gdsfactory"))
from gdsfactory.gpdk import get_generic_pdk

_MAIN_PATH = Path(__file__).with_name("main.py")
_SPEC = importlib.util.spec_from_file_location("gds_parser_main", _MAIN_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
parse_gds = _MODULE.parse_gds


def test_parse_gds_preserves_instance_level_provenance(tmp_path) -> None:
    import gdsfactory as gf

    old = os.environ.get("GDS_PROVENANCE")
    os.environ["GDS_PROVENANCE"] = "1"
    get_generic_pdk().activate()
    try:
        c = gf.Component("instance_provenance_test")

        wg_in = c << gf.c.straight(length=20)
        wg_in.name = "wg_in"

        wg_out = c << gf.c.straight(length=20)
        wg_out.name = "wg_out"
        wg_out.dmove((40, 0))

        gdspath = c.write_gds(gdsdir=tmp_path)
        geojson = parse_gds(gdspath.read_bytes())

        features = [
            feature
            for feature in geojson["features"]
            if feature["properties"]["layer"] == 1
            and feature["properties"]["data_type"] == 0
        ]

        prov_by_instance = {
            feature["properties"]["provenance"]["instance_name"]: feature["properties"][
                "provenance"
            ]
            for feature in features
            if feature["properties"].get("provenance", {}).get("instance_name")
        }

        assert set(prov_by_instance) == {"wg_in", "wg_out"}
        assert prov_by_instance["wg_in"]["line"] != prov_by_instance["wg_out"]["line"]
    finally:
        if old is None:
            os.environ.pop("GDS_PROVENANCE", None)
        else:
            os.environ["GDS_PROVENANCE"] = old
