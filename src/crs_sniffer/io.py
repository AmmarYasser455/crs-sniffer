"""File readers. Malformed content raises ValueError; I/O problems raise OSError."""

from __future__ import annotations

import csv
import io
import json
import os

from .core import to_number, validate_position

X_NAMES = ("x", "lon", "lng", "long", "longitude", "easting", "east")
Y_NAMES = ("y", "lat", "latitude", "northing", "north")
MAX_DEPTH = 32  # GeometryCollection nesting limit

# nesting depth of the coordinates array per geometry type (0 = a single position)
GEOMETRY_DEPTH = {
    "Point": 0,
    "MultiPoint": 1,
    "LineString": 1,
    "MultiLineString": 2,
    "Polygon": 2,
    "MultiPolygon": 3,
}


def _check_path(path) -> str:
    if isinstance(path, bool) or not isinstance(path, (str, os.PathLike)):
        raise ValueError(f"path must be a string or path-like, got {type(path).__name__}")
    return os.fspath(path)


def _read_text(path) -> str:
    path = _check_path(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"file is not valid UTF-8: {exc}") from None


def read_file(path, allow_z: bool = False) -> list[tuple[float, float]]:
    """Read coordinates from a .csv/.txt or GeoJSON file (by extension)."""
    p = _check_path(path)
    try:
        if p.lower().endswith((".csv", ".txt")):
            return read_csv(p, allow_z)
        return read_geojson(p, allow_z)
    except (ValueError, OSError):
        raise
    except Exception as exc:
        raise ValueError(f"cannot read {p!r}: {exc}") from exc


def _positions(node, depth: int, out: list, allow_z: bool) -> None:
    if depth == 0:
        out.append(validate_position(node, allow_z))
        return
    if not isinstance(node, list):
        raise ValueError("GeoJSON coordinates must be nested lists")
    for child in node:
        _positions(child, depth - 1, out, allow_z)


def _geometry(geom, out: list, allow_z: bool, level: int = 0) -> None:
    if geom is None:
        return
    if level > MAX_DEPTH:
        raise ValueError("GeometryCollection nested too deeply")
    if not isinstance(geom, dict):
        raise ValueError("GeoJSON geometry must be an object")
    gtype = geom.get("type")
    if not isinstance(gtype, str):
        raise ValueError("GeoJSON 'type' must be a string")
    if gtype == "GeometryCollection":
        geoms = geom.get("geometries")
        if not isinstance(geoms, list):
            raise ValueError("'geometries' must be a list")
        for g in geoms:
            if g is None:
                raise ValueError("'geometries' must not contain null")
            _geometry(g, out, allow_z, level + 1)
    elif gtype in GEOMETRY_DEPTH:
        _positions(geom.get("coordinates"), GEOMETRY_DEPTH[gtype], out, allow_z)
    else:
        raise ValueError(f"unsupported GeoJSON geometry type {gtype!r}")


def read_geojson(path, allow_z: bool = False) -> list[tuple[float, float]]:
    """Read all positions from a GeoJSON file (geometry, Feature or FeatureCollection)."""
    try:
        text = _read_text(path)
        try:
            doc = json.loads(text)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError(f"invalid JSON: {exc}") from None
        out: list[tuple[float, float]] = []
        if not isinstance(doc, dict):
            raise ValueError("GeoJSON root must be an object")
        kind = doc.get("type")
        if not isinstance(kind, str):
            raise ValueError("GeoJSON 'type' must be a string")
        if kind == "FeatureCollection":
            features = doc.get("features")
            if not isinstance(features, list):
                raise ValueError("'features' must be a list")
            for feat in features:
                if not isinstance(feat, dict) or feat.get("type") != "Feature":
                    raise ValueError("each feature must be an object of type 'Feature'")
                _geometry(feat.get("geometry"), out, allow_z)
        elif kind == "Feature":
            _geometry(doc.get("geometry"), out, allow_z)
        else:
            _geometry(doc, out, allow_z)
        if not out:
            raise ValueError("no coordinates found")
        return out
    except (ValueError, OSError):
        raise
    except Exception as exc:
        raise ValueError(f"invalid GeoJSON: {exc}") from exc


def _cell(text: str, what: str) -> float:
    try:
        return to_number(float(text.strip()), what)
    except ValueError:
        raise ValueError(f"{what}: {text!r} is not a finite number") from None


def _is_number(text: str) -> bool:
    try:
        float(text.strip())
        return True
    except ValueError:
        return False


DELIMITERS = (",", ";", "\t")  # tried in this order; comma first keeps old results


def _parse_csv(text: str, delimiter: str, allow_z: bool = False) -> list[tuple[float, float]]:
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        rows = [r for r in reader if r]
    except csv.Error as exc:
        raise ValueError(f"invalid CSV: {exc}") from None
    if not rows:
        raise ValueError("CSV has no rows")
    xi, yi, width = 0, 1, 2
    names = [c.strip().lower() for c in rows[0]]
    known = any(n in X_NAMES for n in names) and any(n in Y_NAMES for n in names)
    if known or not any(_is_number(c) for c in rows[0]):
        xs = [i for i, n in enumerate(names) if n in X_NAMES]
        ys = [i for i, n in enumerate(names) if n in Y_NAMES]
        if len(xs) != 1 or len(ys) != 1:
            raise ValueError("header must contain exactly one x/lon and one y/lat column")
        xi, yi, width = xs[0], ys[0], len(names)
        rows = rows[1:]
        headerless_z = False
    else:
        # headerless x,y,z: the width is fixed by the first row
        headerless_z = allow_z and len(rows[0]) == 3
        if headerless_z:
            width = 3
    out = []
    for n, row in enumerate(rows, start=1):
        if len(row) != width:
            raise ValueError(f"data row {n} has {len(row)} columns, expected {width}")
        if headerless_z:
            _cell(row[2], f"row {n} z")
        out.append((_cell(row[xi], f"row {n} x"), _cell(row[yi], f"row {n} y")))
    if not out:
        raise ValueError("no coordinates found")
    return out


def read_csv(path, allow_z: bool = False) -> list[tuple[float, float]]:
    """Read x,y pairs from a CSV. A header row (no numeric cells) selects columns by name.

    With allow_z, a headerless file may have three columns x,y,z (Z is validated, then ignored).

    The file is parsed with ',' first. Only if that fails completely is it re-parsed
    with ';' and then tab (common spreadsheet exports); the comma error is reported
    when no delimiter yields valid coordinates.
    """
    try:
        text = _read_text(path)
        first_error = None
        for delimiter in DELIMITERS:
            try:
                return _parse_csv(text, delimiter, allow_z)
            except ValueError as exc:
                if first_error is None:
                    first_error = exc
        raise first_error
    except (ValueError, OSError):
        raise
    except Exception as exc:
        raise ValueError(f"invalid CSV: {exc}") from exc
