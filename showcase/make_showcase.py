"""Build the crs-sniffer showcase from showcase/data/ (offline).

Question: a file of Cairo Metro station coordinates arrives without a `crs`
member -- what coordinate reference system does crs-sniffer say it is in, and
which other CRSs can the numbers alone not rule out?

Run from the repository root:

    python showcase/make_showcase.py

Writes showcase/map.geojson, showcase/map.png (needs matplotlib) and
showcase/index.html. All coordinates are EPSG:4326, x=lon, y=lat (RFC 7946).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from crs_sniffer import read_file, sniff  # noqa: E402

DATA = HERE / "data" / "cairo_metro_stations.geojson"
REPO_URL = "https://github.com/AmmarYasser455/crs-sniffer"
CREDIT = "Data: (c) OpenStreetMap contributors, ODbL"
LABELS = ("Sadat", "Attaba", "Shuhada", "Giza", "Helwan", "New El-Marg",
          "Shobra Al-Kheima", "Adly Mansour", "Imbaba", "Cairo University")


def load_stations(path=DATA) -> list[dict]:
    """Return [{"osm_id", "name", "name_en", "lon", "lat"}] for a GeoJSON file of
    Point features. Coordinates are validated by crs_sniffer.read_file; anything
    that is not a non-empty FeatureCollection of Point features raises ValueError."""
    points = read_file(path)  # ValueError for malformed coordinates / structure
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        raise ValueError("expected a GeoJSON FeatureCollection")
    features = doc.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("expected a non-empty FeatureCollection")
    stations = []
    for feat in features:
        geom = feat.get("geometry") if isinstance(feat, dict) else None
        if not isinstance(geom, dict) or geom.get("type") != "Point":
            raise ValueError("every feature must have a Point geometry")
        props = feat.get("properties")
        if not isinstance(props, dict):
            props = {}
        lon, lat = geom["coordinates"][:2]
        stations.append(
            {
                "osm_id": props.get("osm_id"),
                "name": props.get("name"),
                "name_en": props.get("name:en"),
                "lon": float(lon),
                "lat": float(lat),
            }
        )
    if len(stations) != len(points):
        raise ValueError("feature count does not match coordinate count")
    return stations


def _codes(matches) -> str:
    return ", ".join(m.code for m in matches)


def build_geojson(stations: list[dict]) -> dict:
    """Run crs-sniffer on the stations and return the result as GeoJSON (EPSG:4326)."""
    xy = [(s["lon"], s["lat"]) for s in stations]
    whole = sniff(xy)
    swapped = sniff([(y, x) for x, y in xy])  # what a lat/lon (axis-swapped) export gives
    west = min(x for x, _ in xy)
    east = max(x for x, _ in xy)
    south = min(y for _, y in xy)
    north = max(y for _, y in xy)
    names = {s["name_en"] or s["name"] for s in stations}
    features = [
        {
            "type": "Feature",
            "properties": {
                "kind": "input extent",
                "stations": len(stations),
                "distinct_names": len(names),
                "best": whole[0].code,
                "best_name": whole[0].name,
                "candidates": _codes(whole),
                "swapped_axes_best": swapped[0].code,
                "west": west,
                "south": south,
                "east": east,
                "north": north,
            },
            # Exterior ring counter-clockwise (RFC 7946), closed.
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[west, south], [east, south], [east, north],
                                 [west, north], [west, south]]],
            },
        }
    ]
    for s in stations:
        matches = sniff([(s["lon"], s["lat"])])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "station",
                    "osm_id": s["osm_id"],
                    "name": s["name"],
                    "name_en": s["name_en"],
                    "best": matches[0].code,
                    "candidates": _codes(matches),
                    "n_candidates": len(matches),
                },
                "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_png(geojson: dict, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    extent = geojson["features"][0]
    pts = [f for f in geojson["features"] if f["properties"]["kind"] == "station"]
    xs = [f["geometry"]["coordinates"][0] for f in pts]
    ys = [f["geometry"]["coordinates"][1] for f in pts]
    p = extent["properties"]

    fig, ax = plt.subplots(figsize=(9.6, 8.0), dpi=150)  # 1440 x 1200 px
    ring = extent["geometry"]["coordinates"][0]
    ax.plot([c[0] for c in ring], [c[1] for c in ring], ls="--", lw=1.2, color="#555555",
            label=f"Input extent (whole file sniffed as {p['best']})")
    ax.scatter(xs, ys, s=22, color="#c0392b", edgecolor="white", linewidth=0.6, zorder=3,
               label=f"Metro station node (n={p['stations']}), best guess {pts[0]['properties']['best']}")
    labelled = set()
    for f in pts:
        label = f["properties"]["name_en"]
        if label in LABELS and label not in labelled:
            labelled.add(label)
            x, y = f["geometry"]["coordinates"]
            ax.annotate(label, (x, y), xytext=(4, 3),
                        textcoords="offset points", fontsize=7, color="#222222")
    # Equal ground distances in both directions at Cairo's latitude.
    mid_lat = (p["south"] + p["north"]) / 2
    ax.set_aspect(1 / math.cos(math.radians(mid_lat)))
    pad = 0.02
    ax.set_xlim(p["west"] - pad, p["east"] + pad)
    ax.set_ylim(p["south"] - 2.5 * pad, p["north"] + pad)  # room for the legend
    ax.set_xlabel("Longitude (degrees east, EPSG:4326)")
    ax.set_ylabel("Latitude (degrees north, EPSG:4326)")
    ax.set_title("Cairo Metro stations: crs-sniffer guesses EPSG:4326 (WGS 84 lon/lat)\n"
                 f"Every CRS the numbers fit, best first: {p['candidates']}", fontsize=11)
    ax.grid(True, lw=0.3, color="#cccccc")
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.text(0.01, 0.99, CREDIT + "\nNorth up; lon/lat axes", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color="#444444",
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"})
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>crs-sniffer showcase: Cairo Metro stations</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body { margin: 0; font-family: sans-serif; }
  header { padding: 8px 12px; }
  header h1 { font-size: 1.2em; margin: 0 0 4px; }
  header p { margin: 2px 0; font-size: 0.9em; }
  #map { position: absolute; top: 96px; bottom: 0; left: 0; right: 0; }
</style>
</head>
<body>
<header>
  <h1>crs-sniffer showcase: Cairo Metro stations</h1>
  <p>86 Cairo Metro station nodes from OpenStreetMap were passed to crs-sniffer without any CRS metadata; red dots are stations, the dashed box is the input extent.</p>
  <p>It ranks EPSG:4326 (WGS 84 lon/lat) first; click a feature for its candidates. Code: <a href="REPO_URL">REPO_URL</a></p>
</header>
<div id="map"></div>
<script>
  var map = L.map('map');
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  function popup(props) {
    var rows = Object.keys(props).map(function (k) {
      var v = props[k] === null ? '' : String(props[k]);
      var cell = document.createElement('td');
      cell.textContent = v;
      return '<tr><th style="text-align:left">' + k + '</th>' + cell.outerHTML + '</tr>';
    });
    return '<table>' + rows.join('') + '</table>';
  }
  fetch('map.geojson').then(function (r) { return r.json(); }).then(function (data) {
    var layer = L.geoJSON(data, {
      // Only the Polygon (input extent) is styled here; Point markers keep the
      // style set in pointToLayer below.
      style: function (f) {
        if (f.geometry.type === 'Polygon') {
          return { color: '#555555', weight: 2, dashArray: '6 4', fill: false };
        }
        return {};
      },
      pointToLayer: function (f, latlng) {
        return L.circleMarker(latlng, {
          radius: 5, color: '#ffffff', weight: 1, fillColor: '#c0392b', fillOpacity: 0.9
        });
      },
      onEachFeature: function (f, l) { l.bindPopup(popup(f.properties)); }
    }).addTo(map);
    map.fitBounds(layer.getBounds(), { padding: [20, 20] });
  });
</script>
</body>
</html>
"""


def write_html(path) -> None:
    Path(path).write_text(HTML.replace("REPO_URL", REPO_URL), encoding="utf-8")


def main(out_dir=HERE, data_path=DATA, png: bool = True) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    geojson = build_geojson(load_stations(data_path))
    (out / "map.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    write_html(out / "index.html")
    if png:
        write_png(geojson, out / "map.png")
    return geojson


if __name__ == "__main__":
    result = main()
    p = result["features"][0]["properties"]
    print(f"{p['stations']} stations -> best {p['best']}; candidates {p['candidates']}")
