"""One-off download of the showcase data (not needed to rebuild the showcase).

Fetches Cairo Metro station nodes from OpenStreetMap through the Overpass API
and writes them, trimmed to a few tags, to
showcase/data/cairo_metro_stations.geojson (EPSG:4326, x=lon, y=lat).

Data (c) OpenStreetMap contributors, ODbL 1.0.

    python showcase/fetch_data.py
"""

from __future__ import annotations

import datetime
import json
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS = "https://overpass-api.de/api/interpreter"
# Greater Cairo bounding box (south, west, north, east), degrees.
BBOX = (29.80, 31.00, 30.25, 31.60)
QUERY = f"""
[out:json][timeout:60];
node["railway"="station"]["station"="subway"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
out body;
"""
KEEP = ("name", "name:en", "name:ar", "line", "network", "operator")
OUT = Path(__file__).resolve().parent / "data" / "cairo_metro_stations.geojson"


def main() -> None:
    data = urllib.parse.urlencode({"data": QUERY}).encode("ascii")
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "crs-sniffer-showcase"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        doc = json.loads(resp.read().decode("utf-8"))
    features = []
    for el in sorted(doc["elements"], key=lambda e: e["id"]):
        if el.get("type") != "node":
            continue
        tags = el.get("tags", {})
        props = {"osm_id": f"node/{el['id']}"}
        props.update({k: tags[k] for k in KEEP if k in tags})
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
            }
        )
    out = {
        "type": "FeatureCollection",
        "source": "OpenStreetMap via Overpass API",
        "license": "ODbL 1.0, (c) OpenStreetMap contributors",
        "fetched": datetime.date.today().isoformat(),
        "features": features,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"wrote {len(features)} stations to {OUT}")


if __name__ == "__main__":
    main()
