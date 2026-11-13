import json

import pytest

from crs_sniffer import read_csv, read_file, read_geojson, sniff
from crs_sniffer.cli import main


def codes(coords, **kw):
    return [m.epsg for m in sniff(coords, **kw)]


def test_lonlat_ranked_first():
    assert codes([(13.4, 52.5), (-0.1, 51.5)])[0] == 4326


def test_web_mercator():
    assert codes([(1490000.0, 6890000.0)])[0] == 3857


def test_british_national_grid_over_mercator():
    assert codes([(530000.0, 180000.0)])[0] == 27700


def test_lambert93():
    assert codes([(652000.0, 6862000.0)])[0] == 2154


def test_no_match():
    assert sniff([(1e9, 1e9)]) == []


def test_overlapping_extents_rank_most_specific_first():
    # Paris-area Lambert-93 point also fits Pseudo-Mercator; smaller extent wins.
    assert codes([(652000.0, 6600000.0)]) == [2154, 3857]
    # A point inside the LAEA extent but outside the others.
    assert codes([(4000000.0, 3000000.0)]) == [3035, 3857]
    # British National Grid point also fits Pseudo-Mercator.
    assert codes([(530000.0, 180000.0)]) == [27700, 3857]


def test_extent_edges_are_inclusive_and_every_point_must_fit():
    assert codes([(180.0, 90.0)])[0] == 4326
    assert 4326 not in codes([(180.0001, 90.0)])
    # One point outside the British grid removes that candidate for all.
    assert 27700 not in codes([(530000.0, 180000.0), (800000.0, 180000.0)])


def test_negative_and_z():
    assert codes([(-100.0, -45.0)])[0] == 4326
    assert codes([(1, 2, 3)], allow_z=True)[0] == 4326


def test_geojson_and_csv_files(tmp_path):
    gj = tmp_path / "a.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": None},
        {"type": "Feature", "geometry": {"type": "Polygon",
                                         "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
    ]}))
    assert len(read_geojson(gj)) == 4
    csv_ = tmp_path / "a.csv"
    csv_.write_text("name,Lat,Lon\na,52.5,13.4\nb,51.5,-0.1\n")
    assert read_csv(csv_) == [(13.4, 52.5), (-0.1, 51.5)]
    assert read_file(csv_) == read_csv(csv_)


def test_cli_exit_codes(capsys):
    assert main(["--coords=13.4,52.5"]) == 0
    assert "EPSG:4326" in capsys.readouterr().out
    assert main(["--coords=1e9,1e9"]) == 1
    assert main(["--coords=1e9,1e9", "--json"]) == 1
    assert capsys.readouterr().out.strip().endswith("[]")
    assert main(["--coords=530000,180000", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["epsg"] == 27700


def test_cli_output_matches_readme_examples(capsys):
    assert main(["--coords=530000,180000;531000,181000"]) == 0
    assert capsys.readouterr().out == (
        "best: EPSG:27700  OSGB36 / British National Grid\n"
        "also: EPSG:3857  WGS 84 / Pseudo-Mercator\n"
    )
    assert main(["--coords=651000,6862000;652000,6863000"]) == 0
    assert capsys.readouterr().out == (
        "best: EPSG:2154  RGF93 v1 / Lambert-93\n"
        "also: EPSG:3857  WGS 84 / Pseudo-Mercator\n"
    )
    assert main(["--coords=3750000,2900000;4300000,3300000"]) == 0
    assert capsys.readouterr().out == (
        "best: EPSG:3035  ETRS89 / LAEA Europe\n"
        "also: EPSG:3857  WGS 84 / Pseudo-Mercator\n"
    )
    assert main(["--coords=13.4,52.5", "--json"]) == 0
    assert capsys.readouterr().out == (
        '[{"epsg": 4326, "name": "WGS 84 (lon/lat)"}, '
        '{"epsg": 27700, "name": "OSGB36 / British National Grid"}, '
        '{"epsg": 3857, "name": "WGS 84 / Pseudo-Mercator"}]\n'
    )
    assert main(["--coords=1e9,1e9"]) == 1
    assert capsys.readouterr().out == "no known CRS fits these coordinates\n"


def test_cli_allow_z(capsys):
    assert main(["--coords=1,2,3", "--allow-z"]) == 0
    assert main(["--coords=1,2,3"]) == 2
    assert main(["--coords=1,2,abc", "--allow-z"]) == 2
    assert main(["--coords=1,2,nan", "--allow-z"]) == 2
    assert main(["--coords=1,2,1,4", "--allow-z"]) == 2
    assert "invalid input:" in capsys.readouterr().err


def test_cli_coords_trailing_semicolon(capsys):
    assert main(["--coords=10,20;30,40;"]) == 0
    with_semicolon = capsys.readouterr().out
    assert main(["--coords=10,20;30,40"]) == 0
    assert capsys.readouterr().out == with_semicolon
    for bad in ("--coords=10,20;;", "--coords=;", "--coords=10,20;;30,40"):
        assert main([bad]) == 2


def test_cli_missing_args_exit_2():
    for argv in ([], ["--coords"], ["p.csv", "--coords"], ["--coords", "1,2", "--coords"]):
        with pytest.raises(SystemExit) as e:
            main(argv)
        assert e.value.code == 2


BIG = 10**400
POINTS = [
    None, True, False, 5, 1.5, "1,2", {"x": 1, "y": 2}, [{"x": 1, "y": 2}], [], (), [[]],
    [[1]], [[1, 2, 3]], [[1, 2], [3]], [[[1, 2]]], [[None, 1]], [[True, 2]], [["1", 2]],
    [[float("nan"), 1]], [[1, float("inf")]], [[BIG, 1]], [[1, -BIG]], [{1, 2}],
    [[[1], [2]]], [[1, [2]]], [b"ab"],
]
GEOJSON = [
    "", "not json", "[]", "null", "5", '"x"', "{}", '{"type": []}', '{"type": null}',
    '{"type": {"a": 1}}', '{"type":"FeatureCollection"}',
    '{"type":"FeatureCollection","features":null}',
    '{"type":"FeatureCollection","features":{}}',
    '{"type":"FeatureCollection","features":[]}',
    '{"type":"FeatureCollection","features":[null]}',
    '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":null}]}',
    '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":5}]}',
    '{"type":"Feature","geometry":{"type":[]}}',
    '{"type":"GeometryCollection","geometries":null}',
    '{"type":"GeometryCollection","geometries":[null]}',
    '{"type":"GeometryCollection","geometries":{}}',
    '{"type":"Point"}', '{"type":"Point","coordinates":null}',
    '{"type":"Point","coordinates":{"x":1,"y":2}}',
    '{"type":"Point","coordinates":[1]}', '{"type":"Point","coordinates":[1,2,3]}',
    '{"type":"Point","coordinates":[NaN,1]}', '{"type":"Point","coordinates":[Infinity,1]}',
    '{"type":"Point","coordinates":[1e999,1]}', '{"type":"Point","coordinates":[1' + "0" * 400 + ',1]}',
    '{"type":"Point","coordinates":[true,1]}', '{"type":"Point","coordinates":["1","2"]}',
    '{"type":"LineString","coordinates":[1,2]}', '{"type":"LineString","coordinates":"ab"}',
    '{"type":"Polygon","coordinates":[[1,2]]}',
    '{"type":"Unknown","coordinates":[1,2]}',
    "[" * 100000, '{"type":"GeometryCollection","geometries":[' * 200 + "]}" * 200,
]
CSV = [
    b"", b"\n\n", b"x,y\n", b"\xff\xfe\x00bad", b"1,broken\n2,3\n", b"1,2,3\n",
    b"1\n", b"a,b\n1,2\n", b"x,y\n1\n", b"x,y,x\n1,2,3\n", b'"1\n2",3\n', b"nan,1\n",
    b"x,y\ninf,1\n", b"x,y\n1e999,1\n", b"1,2\n3\n", b"x,y\n" + b"1" * 200000 + b",2\n",
    b'"unterminated,1\n', b"1,2\0\n",
    b'x,y,label\n1,2,"unclosed\n3,4,label\n',
    b'x,y,2024\n1,2,"unclosed\n3,4,label\n',
]


def test_csv_numeric_metadata_header_and_strict_quotes(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("x,y,2024\n13.4,52.5,value\n")
    assert read_csv(str(p)) == [(13.4, 52.5)]
    p.write_text('x,y,label\n1,2,"unclosed\n3,4,label\n')
    with pytest.raises(ValueError):
        read_csv(str(p))


# (file content, expected points or ValueError). Comma CSVs that parsed before must parse
# identically; ';' and tab are only used when comma parsing fails.
DELIMITED = [
    ("x;y\n13.4;52.5\n", [(13.4, 52.5)]),
    ("13.4;52.5\n-0.1;51.5\n", [(13.4, 52.5), (-0.1, 51.5)]),
    ("name;Lat;Lon\na;52.5;13.4\n", [(13.4, 52.5)]),
    ("x\ty\n530000\t180000\n", [(530000.0, 180000.0)]),
    ("530000\t180000\n", [(530000.0, 180000.0)]),
    ('x;y;"label,description"\n1;2;foo\n', [(1.0, 2.0)]),
    ('x;y;label\n1;2;"a;b"\n', [(1.0, 2.0)]),
    # comma CSVs containing ';' or tabs keep their comma reading
    ('"label;\ninfo",x,y\nfoo,1,2\n', [(1.0, 2.0)]),
    ('label;"note,x,y\nfoo,1,2\n', [(1.0, 2.0)]),
    ("x,y,label;a;b;c\n1,2,note\n", [(1.0, 2.0)]),
    ("x,y,note\n1,2,a;b\n", [(1.0, 2.0)]),
    ("x,y,note\n1,2,a\tb\n", [(1.0, 2.0)]),
    # rejected: decimal commas, mixed delimiters, wrong arity, non-numbers
    ("13,4;52,5\n", ValueError),
    ("x;y\n1;2\n3,4\n", ValueError),
    ("x;y\n1;2;3\n", ValueError),
    ("x;y\nnan;1\n", ValueError),
    ("x\ty\n1\tabc\n", ValueError),
    ("x;y\n", ValueError),
    (";\n", ValueError),
    ("\t\n", ValueError),
]


def test_csv_delimiters_table(tmp_path, capsys):
    for text, expected in DELIMITED:
        path = _write(tmp_path, "d.csv", text)
        if expected is ValueError:
            with pytest.raises(ValueError):
                read_csv(path)
            assert main([path]) == 2, text
            assert capsys.readouterr().err.startswith("invalid input: ")
        else:
            assert read_csv(path) == expected, text
            assert read_file(path) == expected, text


def test_csv_error_message_comes_from_comma_parse(tmp_path):
    path = _write(tmp_path, "e.csv", "x,y\n1,abc\n")
    with pytest.raises(ValueError, match="row 1 y"):
        read_csv(path)


ARGV_COORDS = ["", ";", "1", "1,2;;", "a,b", "nan,1", "inf,1", "1e999,2", "1,2,3", "1,", ",1", "1;2"]


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return str(p)


def test_malformed_inputs_table(tmp_path, capsys):
    """Every malformed input: ValueError from the API, exit 2 and no traceback from the CLI."""
    # points exist only in the API (the CLI builds points from strings, covered below)
    for pts in POINTS:
        with pytest.raises(ValueError):
            sniff(pts)
    with pytest.raises(ValueError):
        sniff([[1, 2, 3, 4]], allow_z=True)
    with pytest.raises(ValueError):
        sniff([[1, 2, "bad"]], allow_z=True)
    for bad_path in (None, 5, True, [], {}):
        with pytest.raises(ValueError):
            read_file(bad_path)
    cases = [("a.geojson", g) for g in GEOJSON] + [("a.csv", c) for c in CSV]
    assert len(cases) + len(POINTS) + len(ARGV_COORDS) >= 25
    for name, data in cases:
        path = _write(tmp_path, name, data)
        with pytest.raises(ValueError):
            read_file(path)
        assert main([path]) == 2, (name, data[:60])
        err = capsys.readouterr().err
        assert err.startswith("invalid input: ") and "Traceback" not in err
    for text in ARGV_COORDS:
        assert main([f"--coords={text}"]) == 2, text
        assert capsys.readouterr().err.startswith("invalid input: ")
    # missing file: OSError from the API, exit 2 from the CLI
    missing = str(tmp_path / "nope.csv")
    with pytest.raises(OSError):
        read_file(missing)
    assert main([missing]) == 2


def test_cli_unreadable_paths_report_cleanly(tmp_path, capsys):
    """Paths that cannot be opened: API error type, exit 2, clean one-line stderr, empty stdout."""
    (tmp_path / "dir.geojson").mkdir()
    (tmp_path / "dir.csv").mkdir()
    cases = [
        (str(tmp_path / "nope.csv"), OSError),
        (str(tmp_path / "nope.txt"), OSError),
        (str(tmp_path / "nope.geojson"), OSError),
        (str(tmp_path / "nope.json"), OSError),
        (str(tmp_path / "missing_dir" / "a.csv"), OSError),
        (str(tmp_path / "dir.geojson"), OSError),
        (str(tmp_path / "dir.csv"), OSError),
        ("", OSError),
        ("a\0b.csv", ValueError),
    ]
    for path, api_error in cases:
        with pytest.raises(api_error):
            read_file(path)
        assert main([path]) == 2, path
        assert main([path, "--json"]) == 2, path
        out, err = capsys.readouterr()
        assert out == "", path
        lines = err.splitlines()
        assert len(lines) == 2 and all(ln.startswith("invalid input: ") for ln in lines), err
        assert "Traceback" not in err
