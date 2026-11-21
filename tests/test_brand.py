import re
import xml.etree.ElementTree as ET
from pathlib import Path

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
ALLOWED = {
    "logo.svg": {"#121417", "#F2552C"},
    "logo-dark.svg": {"#F3EEE4", "#F2552C"},
}


def test_logos_parse_and_use_only_brand_colours():
    for name, allowed in ALLOWED.items():
        path = BRAND / name
        assert path.is_file()
        root = ET.parse(path).getroot()
        assert root.get("viewBox") == "0 0 100 100"
        assert root.get("width") == "100" and root.get("height") == "100"
        text = path.read_text(encoding="utf-8")
        colours = {c.upper() for c in re.findall(r"#[0-9a-fA-F]{3,8}\b", text)}
        assert colours == allowed
        assert "opacity" not in text and "<text" not in text
