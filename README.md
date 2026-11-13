# crs-sniffer

Guess the most likely coordinate reference system (EPSG code) of a list of coordinates, or of a GeoJSON/CSV file, from value ranges and known projected extents. Useful when a file arrives without a `.prj` or `crs` member and you need a starting hypothesis. It has no dependencies.

## Install

```
pip install git+https://github.com/AmmarYasser455/crs-sniffer
```

## CLI

```
$ crs-sniffer --coords="530000,180000;531000,181000"
best: EPSG:27700  OSGB36 / British National Grid
also: EPSG:3857  WGS 84 / Pseudo-Mercator

$ crs-sniffer --coords="651000,6862000;652000,6863000"
best: EPSG:2154  RGF93 v1 / Lambert-93
also: EPSG:3857  WGS 84 / Pseudo-Mercator

$ crs-sniffer --coords="3750000,2900000;4300000,3300000"
best: EPSG:3035  ETRS89 / LAEA Europe
also: EPSG:3857  WGS 84 / Pseudo-Mercator

$ crs-sniffer --coords=13.4,52.5 --json
[{"epsg": 4326, "name": "WGS 84 (lon/lat)"}, {"epsg": 27700, "name": "OSGB36 / British National Grid"}, {"epsg": 3857, "name": "WGS 84 / Pseudo-Mercator"}]

$ crs-sniffer points.csv          # also .geojson / .json
$ crs-sniffer --coords=1,2,3 --allow-z
```

Coordinates are `x,y` pairs separated by `;`. Use `--coords=-1,2` (with `=`) for negative values.

Exit status: `0` at least one candidate, `1` no known CRS fits (also with `--json`, which prints `[]`), `2` invalid input.

## Python

```python
from crs_sniffer import sniff, read_file

sniff([(1490000.0, 6890000.0)])      # [Match(epsg=3857, name='WGS 84 / Pseudo-Mercator')]
sniff(read_file("parcels.geojson"))
```

CSV files may have a header (`x`/`lon`/`easting` and `y`/`lat`/`northing` columns, any order) or be headerless two-column `x,y`. Semicolon- and tab-separated files (common spreadsheet exports) are also read: the file is parsed with `,` first, and `;` then tab are tried only if that fails, so comma files are read exactly as before. Decimal commas (`13,4;52,5`) and mixed delimiters are rejected.

## Malformed input safety net

Input is validated strictly at every boundary: numbers must be `int`/`float` (not `bool`), finite and convertible to float (huge integers such as `10**400` are rejected); GeoJSON `type` must be a string; containers must be lists; mappings, strings and wrong arity are rejected.

- `sniff` and the file readers raise `ValueError` for malformed content, and any unexpected exception during validation is converted to `ValueError`. Missing or unreadable files raise `OSError`.
- The CLI reports any failure as `invalid input: <message>` on stderr with exit status 2 and no traceback.
- One table-driven test (`test_malformed_inputs_table`) runs dozens of malformed points, GeoJSON documents, CSV files and `--coords` strings. Points are checked through the API only; files are checked through both the API and the CLI; `--coords` strings through the CLI.

## How it ranks

Only CRSs whose approximate extent contains every point are returned. Values that fit in degrees rank WGS 84 first; otherwise the smaller (more specific) extent ranks first.

Known CRSs: EPSG:4326, 3857, 3035, 2154, 27700.

## Limitations

- Small built-in set with approximate extents; UTM zones are not identified.
- Lat/lon axis order and datum differences are not distinguished.
- Small coordinates fit several CRSs; the result is a ranked guess, not proof.
- Z values (GeoJSON, `--allow-z`) are validated but ignored when guessing; CSV Z columns are not read.
