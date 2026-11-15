import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOWCASE = ROOT / "showcase"

_spec = importlib.util.spec_from_file_location("make_showcase", SHOWCASE / "make_showcase.py")
make_showcase = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_showcase)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_geojson_matches_committed(tmp_path):
    make_showcase.main(out_dir=tmp_path, png=False)
    assert _load(tmp_path / "map.geojson") == _load(SHOWCASE / "map.geojson")
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == (
        SHOWCASE / "index.html"
    ).read_text(encoding="utf-8")


def test_png_is_produced(tmp_path):
    pytest.importorskip("matplotlib")
    make_showcase.main(out_dir=tmp_path)
    png = tmp_path / "map.png"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    width = int.from_bytes(png.read_bytes()[16:20], "big")
    assert 1200 <= width <= 1600


def test_result_is_lon_lat_cairo_and_sniffed_as_wgs84():
    doc = _load(SHOWCASE / "map.geojson")
    extent, *stations = doc["features"]
    assert extent["properties"]["best"] == "EPSG:4326"
    assert extent["properties"]["stations"] == len(stations) == 86
    ring = extent["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    # Shoelace area > 0: exterior ring is counter-clockwise (RFC 7946).
    assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) > 0
    by_name = {f["properties"]["name_en"]: f["geometry"]["coordinates"] for f in stations}
    # Sadat station is under Tahrir Square, ~31.236 E, 30.044 N; a swapped axis fails here.
    lon, lat = by_name["Sadat"]
    assert math.isclose(lon, 31.236, abs_tol=0.01) and math.isclose(lat, 30.044, abs_tol=0.01)
    # Helwan (south terminus of line 1) is south of Shobra Al-Kheima (north terminus of line 2).
    assert by_name["Helwan"][1] < by_name["Shobra Al-Kheima"][1]
    assert all(f["properties"]["best"] == "EPSG:4326" for f in stations)


FC = '{"type": "FeatureCollection", "features": [%s]}'
PT = '{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": %s}}'

MALFORMED = [
    ("null", "null"),
    ("string", '"cairo"'),
    ("list", "[]"),
    ("empty object", "{}"),
    ("bare point", '{"type": "Point", "coordinates": [31.2, 30.0]}'),
    ("single feature", PT % "[31.2, 30.0]"),
    ("no features", FC % ""),
    ("features is mapping", '{"type": "FeatureCollection", "features": {}}'),
    ("null geometry", FC % '{"type": "Feature", "properties": {}, "geometry": null}'),
    ("linestring", FC % '{"type": "Feature", "properties": {}, "geometry":'
     ' {"type": "LineString", "coordinates": [[31.2, 30.0], [31.3, 30.1]]}}'),
    ("string coords", FC % (PT % '["31.2", "30.0"]')),
    ("NaN coord", FC % (PT % "[NaN, 30.0]")),
    ("mapping coords", FC % (PT % '{"x": 31.2, "y": 30.0}')),
    ("one value", FC % (PT % "[31.2]")),
    ("null coords", FC % (PT % "null")),
    ("bool coord", FC % (PT % "[true, 30.0]")),
]


@pytest.mark.parametrize("label,text", MALFORMED, ids=[m[0] for m in MALFORMED])
def test_load_stations_rejects_malformed_input(tmp_path, label, text):
    path = tmp_path / "bad.geojson"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        make_showcase.load_stations(path)


def test_web_map_keeps_point_style():
    html = (SHOWCASE / "index.html").read_text(encoding="utf-8")
    assert "leaflet@1.9.4/dist/leaflet.js" in html and "fetch('map.geojson')" in html
    assert "f.geometry.type === 'Polygon'" in html  # style callback leaves markers alone
    assert "fitBounds" in html and "github.com/AmmarYasser455/crs-sniffer" in html


def test_notebook_has_saved_image_and_no_errors():
    nb = _load(SHOWCASE / "showcase.ipynb")
    assert nb["nbformat"] == 4
    outputs = [o for c in nb["cells"] if c["cell_type"] == "code" for o in c["outputs"]]
    assert any("image/png" in o.get("data", {}) for o in outputs)
    assert not any(o["output_type"] == "error" for o in outputs)


def test_committed_notebook_executes():
    for mod in ("matplotlib", "nbformat", "nbclient", "ipykernel"):
        pytest.importorskip(mod)
    import nbformat
    from nbclient import NotebookClient

    nb = nbformat.read(SHOWCASE / "showcase.ipynb", as_version=4)
    client = NotebookClient(
        nb, timeout=120, kernel_name="python3", resources={"metadata": {"path": str(SHOWCASE)}}
    )
    client.execute()  # raises CellExecutionError on any error
