# Examples

Small sample files for `crs-sniffer`. Each holds three well-known landmarks.

| File | Places | Stored as |
|------|--------|-----------|
| `london_bng.csv` | Trafalgar Square, Big Ben, Royal Observatory | OSGB36 / British National Grid (EPSG:27700), metres |
| `paris_lambert93.csv` | Eiffel Tower, Notre-Dame de Paris, Louvre Museum | RGF93 v1 / Lambert-93 (EPSG:2154), metres |
| `berlin_wgs84.geojson` | Brandenburg Gate, Reichstag, Alexanderplatz | WGS 84 lon/lat (EPSG:4326), degrees (x=lon, y=lat) |

`sites.json` places one marker per file on the demo map (`docs/index.html`), at the
first landmark of that file.

## Source and licence

All positions come from the "coordinate location" (P625) statement of each
landmark's item on [Wikidata](https://www.wikidata.org/), retrieved 2026-11-15.
Wikidata's structured data is released under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain
dedication). Every row carries its Wikidata item ID:

| Landmark | Wikidata | lon | lat |
|----------|----------|-----|-----|
| Trafalgar Square | Q129143 | -0.128055555 | 51.508055555 |
| Big Ben | Q41225 | -0.12457 | 51.50067 |
| Royal Observatory | Q192988 | -0.001388888 | 51.477833333 |
| Eiffel Tower | Q243 | 2.294479 | 48.858296 |
| Notre-Dame de Paris | Q2981 | 2.3498 | 48.853 |
| Louvre Museum | Q19675 | 2.335833333 | 48.861111111 |
| Brandenburg Gate | Q82425 | 13.377722222 | 52.516272222 |
| Reichstag | Q151897 | 13.376111111 | 52.518611111 |
| Alexanderplatz | Q152783 | 13.413611111 | 52.521666666 |

For Big Ben the preferred-rank statement is used (the item also has a second,
normal-rank value about 6 m further east).

Transformation: the Berlin file holds the Wikidata values unchanged. The London and
Paris files were projected from them with pyproj using fixed, grid-free operations
and rounded to 0.1 m:

- EPSG:27700: inverse of the EPSG:1314 Helmert "OSGB36 to WGS 84 (6)", then British
  National Grid. This is what PROJ picks when the OSTN15 grid is not installed; with
  OSTN15 the PROJ default gives values a few metres different, so these
  eastings/northings may differ from the official OS transformation by that much.
- EPSG:2154: RGF93 v1 treated as equal to WGS 84, then Lambert-93.

`tests/test_examples.py` pins the same PROJ pipelines, so the check does not depend
on which grids are installed. Wikidata coordinates describe the landmark, not a
surveyed point; they are fine for CRS guessing but are not survey data.

`demo.ipynb` walks through the Python API on these files.
