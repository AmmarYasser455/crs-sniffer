"""Build the demo GeoJSON from the example files (used by tests and docs)."""

from __future__ import annotations

import json
from pathlib import Path

from .core import sniff
from .io import read_file


def build_demo(examples_dir) -> dict:
    """Return a GeoJSON FeatureCollection (EPSG:4326, x=lon, y=lat) with one
    marker per example file, carrying the CRS guess for that file."""
    base = Path(examples_dir)
    sites = json.loads((base / "sites.json").read_text(encoding="utf-8"))
    features = []
    for site in sites:
        points = read_file(base / site["file"])
        matches = sniff(points)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "place": site["place"],
                    "marker": site["marker"],
                    "file": site["file"],
                    "points": len(points),
                    "best": matches[0].code if matches else None,
                    "name": matches[0].name if matches else None,
                    "candidates": [m.code for m in matches],
                },
                "geometry": {"type": "Point", "coordinates": [site["lon"], site["lat"]]},
            }
        )
    return {"type": "FeatureCollection", "features": features}
