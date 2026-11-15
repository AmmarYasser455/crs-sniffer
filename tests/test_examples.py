import csv
import json
from pathlib import Path

import pytest

from crs_sniffer import read_file, sniff
from crs_sniffer.demo import build_demo

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"

# Wikidata P625 (lon, lat) per item, as documented in examples/README.md.
WIKIDATA = {
    "Q129143": ("Trafalgar Square", -0.128055555, 51.508055555),
    "Q41225": ("Big Ben", -0.12457, 51.50067),
    "Q192988": ("Royal Observatory", -0.001388888, 51.477833333),
    "Q243": ("Eiffel Tower", 2.294479, 48.858296),
    "Q2981": ("Notre-Dame de Paris", 2.3498, 48.853),
    "Q19675": ("Louvre Museum", 2.335833333, 48.861111111),
    "Q82425": ("Brandenburg Gate", 13.377722222, 52.516272222),
    "Q151897": ("Reichstag", 13.376111111, 52.518611111),
    "Q152783": ("Alexanderplatz", 13.413611111, 52.521666666),
}

# file, EPSG it is stored in, (x column, y column) for CSVs
FILES = [
    ("london_bng.csv", 27700, ("easting", "northing")),
    ("paris_lambert93.csv", 2154, ("x", "y")),
    ("berlin_wgs84.geojson", 4326, None),
]


def _rows(name, cols):
    """Return [(wikidata id, name, x, y)] for one example file."""
    path = EX / name
    if cols is None:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return [
            (f["properties"]["wikidata"], f["properties"]["name"], *f["geometry"]["coordinates"])
            for f in doc["features"]
        ]
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            (r["wikidata"], r["name"], float(r[cols[0]]), float(r[cols[1]]))
            for r in csv.DictReader(fh)
        ]


@pytest.mark.parametrize("name,epsg,cols", FILES)
def test_example_is_sniffed_as_its_stored_crs(name, epsg, cols):
    points = read_file(EX / name)
    assert len(points) == 3
    assert sniff(points)[0].epsg == epsg


@pytest.mark.parametrize("name,epsg,cols", FILES)
def test_every_row_names_its_wikidata_source(name, epsg, cols):
    for qid, label, _x, _y in _rows(name, cols):
        assert WIKIDATA[qid][0] == label


def test_berlin_holds_wikidata_values_unchanged_lon_lat():
    for qid, _label, x, y in _rows("berlin_wgs84.geojson", None):
        assert (x, y) == WIKIDATA[qid][1:]  # x=lon, y=lat
    assert read_file(EX / "berlin_wgs84.geojson")[0] == (13.377722222, 52.516272222)


def test_known_relative_positions():
    # Greenwich is ~8.6 km east of Trafalgar Square and south of it;
    # Notre-Dame is ~4 km east of the Eiffel Tower. A swapped axis fails this.
    london = {r[0]: r[2:] for r in _rows("london_bng.csv", ("easting", "northing"))}
    assert 8000 < london["Q192988"][0] - london["Q129143"][0] < 9500
    assert london["Q192988"][1] < london["Q129143"][1]
    paris = {r[0]: r[2:] for r in _rows("paris_lambert93.csv", ("x", "y"))}
    assert 3500 < paris["Q2981"][0] - paris["Q243"][0] < 4500


# Explicit, grid-free operations used to derive the projected example files
# (see examples/README.md). Pinning them keeps the check independent of which
# PROJ grids (e.g. OSTN15) happen to be installed. Input is (lon, lat) degrees.
PIPELINES = {
    # Inverse of EPSG:1314 "OSGB36 to WGS 84 (6)" Helmert + British National Grid.
    27700: (
        "+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad"
        " +step +proj=push +v_3 +step +proj=cart +ellps=WGS84"
        " +step +inv +proj=helmert +x=446.448 +y=-125.157 +z=542.06"
        " +rx=0.15 +ry=0.247 +rz=0.842 +s=-20.489 +convention=position_vector"
        " +step +inv +proj=cart +ellps=airy +step +proj=pop +v_3"
        " +step +proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717"
        " +x_0=400000 +y_0=-100000 +ellps=airy"
    ),
    # RGF93 v1 = WGS 84 (null transformation) + Lambert-93.
    2154: (
        "+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad"
        " +step +proj=lcc +lat_0=46.5 +lon_0=3 +lat_1=49 +lat_2=44"
        " +x_0=700000 +y_0=6600000 +ellps=GRS80"
    ),
}


@pytest.mark.parametrize("name,epsg,cols", FILES[:2])
def test_projected_rows_match_wikidata_within_half_metre(name, epsg, cols):
    pyproj = pytest.importorskip("pyproj")
    t = pyproj.Transformer.from_pipeline(PIPELINES[epsg])
    for qid, _label, x, y in _rows(name, cols):
        ex, ey = t.transform(*WIKIDATA[qid][1:])
        assert abs(ex - x) <= 0.5 and abs(ey - y) <= 0.5


def test_demo_markers_are_wikidata_landmarks():
    for site in json.loads((EX / "sites.json").read_text(encoding="utf-8")):
        label, lon, lat = WIKIDATA[site["wikidata"]]
        assert (site["marker"], site["lon"], site["lat"]) == (label, lon, lat)


def test_examples_are_small():
    assert sum(p.stat().st_size for p in EX.iterdir()) < 100_000


def test_demo_geojson_is_current():
    committed = json.loads((ROOT / "docs" / "demo.geojson").read_text(encoding="utf-8"))
    assert committed == build_demo(EX)


def test_demo_page_references():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "leaflet@1.9.4/dist/leaflet.js" in html
    assert "OpenStreetMap" in html
    assert "github.com/AmmarYasser455/crs-sniffer" in html
