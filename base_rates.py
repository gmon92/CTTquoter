"""Read address-based reference rates from the local pricing workbook."""

from math import asin, cos, radians, sin, sqrt
from pathlib import Path, PurePosixPath
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

WORKBOOK = Path(__file__).resolve().parent / "Taxi Pricing.xlsx"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

ALIASES = {
    "CHO": ("cho", "charlottesville albemarle airport", "charlottesville airport"),
    "RIC": ("ric", "richmond international airport", "richmond airport"),
    "IAD": ("iad", "dulles", "washington dulles international airport"),
    "DCA": ("dca", "reagan national", "ronald reagan", "washington national airport"),
    "BWI": ("bwi", "baltimore washington international", "baltimore airport"),
    "ROA": ("roa", "roanoke airport", "roanoke blacksburg regional airport"),
    "Lynchburg": ("lynchburg", "lyh"),
    "Keswick": ("keswick",),
    "Cville": ("cville", "charlottesville"),
    "Albemarle Estates": ("albemarle estates",),
    "Lexington": ("lexington",),
    "Amtrak": ("amtrak", "charlottesville station"),
    "Harrisonburg": ("harrisonburg",),
    "Downtown": ("downtown",),
    "Quirk": ("quirk",),
    "Pippin Hill": ("pippin hill",),
    "Miller School": ("miller school",),
    "BHI": ("bhi", "boars head", "boar s head"),
    "Farmington": ("farmington",),
}

# A street address near an airport can match even when its name/code is omitted.
# These matches are explicitly labeled "near" in the reference panel.
AIRPORTS = {
    "CHO": (38.1396, -78.4529),
    "RIC": (37.5052, -77.3197),
    "IAD": (38.9531, -77.4565),
    "DCA": (38.8512, -77.0402),
    "BWI": (39.1754, -76.6684),
    "ROA": (37.3255, -79.9754),
}


def normalized(value):
    value = unicodedata.normalize("NFKD", str(value)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def locations(address, point=None):
    text = " " + normalized(address) + " "
    found = {
        name: "text" for name, aliases in ALIASES.items()
        if any(" " + normalized(alias) + " " in text for alias in aliases)
    }
    if point:
        lat, lon = map(radians, point)
        for name, center in AIRPORTS.items():
            airport_lat, airport_lon = map(radians, center)
            distance = 6371 * 2 * asin(min(1, sqrt(
                sin((lat - airport_lat) / 2) ** 2
                + cos(lat) * cos(airport_lat) * sin((lon - airport_lon) / 2) ** 2
            )))
            if distance <= 1.5:
                found.setdefault(name, "near")
    if "CHO" in found:
        found.pop("Cville", None)
    return found


def read_cells(path):
    """Read the first worksheet with the standard library; no Excel install needed."""
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(item.itertext()) for item in
                       ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = workbook.find("s:sheets/s:sheet", NS)
        if sheet is None:
            raise ValueError("Workbook has no worksheets")
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(rel.attrib["Target"] for rel in relationships
                      if rel.attrib["Id"] == sheet.attrib[f"{{{REL_NS}}}id"])
        sheet_path = target.lstrip("/") if target.startswith("/") else str(PurePosixPath("xl") / target)
        cells = {}
        for cell in ET.fromstring(archive.read(sheet_path)).findall(".//s:sheetData/s:row/s:c", NS):
            kind = cell.get("t")
            value = cell.findtext("s:v", default="", namespaces=NS)
            if kind == "s":
                value = strings[int(value)]
            elif kind == "inlineStr":
                value = "".join(cell.find("s:is", NS).itertext())
            elif value and kind not in ("str", "e", "b"):
                value = float(value)
            cells[cell.attrib["r"]] = value.strip() if isinstance(value, str) else value
        return cells


def number(value):
    return float(value) if isinstance(value, (int, float)) else None


def rate_rows(cells):
    # Each schedule is a contiguous table starting below the row 3 headings.
    blocks = [("C", "A", "B"), ("F", "D", "E"), ("I", "G", None),
              ("L", "J", "K"), ("O", "M", "N")]
    for destination_col, sedan_col, suv_col in blocks:
        row = 4
        while cells.get(f"{destination_col}{row}"):
            label = str(cells[f"{destination_col}{row}"])
            sedan = number(cells.get(f"{sedan_col}{row}"))
            suv = number(cells.get(f"{suv_col}{row}")) if suv_col else None
            shared = None
            if suv_col is None:
                value = cells.get(f"{sedan_col}{row}")
                if isinstance(value, str) and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\s*", value):
                    sedan, suv = map(float, value.split("/"))
                else:
                    shared, sedan = sedan, None
            if sedan is not None or suv is not None or shared is not None:
                yield {"schedule": cells.get(f"{destination_col}1", "Base rates"),
                       "route": label, "sedan": sedan, "suv": suv, "shared_rate": shared}
            row += 1


def match_rate(rate, pickup, destination):
    endpoints = re.split(r"\s+to(?:/from)?\s+", rate["route"], flags=re.IGNORECASE)
    if len(endpoints) == 2:
        start, end = map(locations, endpoints)
        if (start.keys() & pickup.keys() and end.keys() & destination.keys()
                or end.keys() & pickup.keys() and start.keys() & destination.keys()):
            reason = "Pickup and destination match this listed route"
            if any(actual.get(name) == "near" for actual in (pickup, destination)
                   for name in start.keys() | end.keys()):
                reason += "; airport area match"
            return reason
        return None
    expected = locations(rate["route"])
    reasons = []
    for label, actual in (("Pickup", pickup), ("Destination", destination)):
        for name in sorted(expected.keys() & actual.keys()):
            verb = "is near" if actual[name] == "near" else "matches"
            reasons.append(f"{label} {verb} {name}")
    return "; ".join(reasons) or None


def find_reference_rates(pickup, destination, pickup_point=None, destination_point=None, path=WORKBOOK):
    result = {"source": Path(path).name, "status": "ok", "matches": [], "pickup_notes": []}
    try:
        cells = read_cells(path)
        pickup_locations = locations(pickup, pickup_point)
        destination_locations = locations(destination, destination_point)
        for rate in rate_rows(cells):
            reason = match_rate(rate, pickup_locations, destination_locations)
            if reason:
                result["matches"].append({**rate, "match": reason})
        result["matches"].sort(key=lambda rate: "listed route" not in rate["match"])
        for row in range(1, max(int(re.sub(r"\D", "", cell)) for cell in cells) + 1):
            heading = str(cells.get(f"A{row}", ""))
            if not heading.startswith("PICKUP ") or heading[7:] not in pickup_locations:
                continue
            note = {"heading": heading, "base": str(cells.get(f"B{row}", "")), "items": []}
            cursor = row + 1
            while cursor < row + 10 and not cells.get(f"A{cursor}"):
                band, amount = cells.get(f"B{cursor}"), cells.get(f"C{cursor}")
                if band and amount:
                    note["items"].append(f"{band}: {amount}")
                cursor += 1
            if heading == "PICKUP CHO":
                note["items"].extend(str(cells[f"C{r}"]) for r in (53, 54) if cells.get(f"C{r}"))
            result["pickup_notes"].append(note)
    except (OSError, BadZipFile, ET.ParseError, KeyError, IndexError, StopIteration, ValueError):
        result.update(status="unavailable", matches=[], pickup_notes=[])
    return result


def find_trip_reference_rates(addresses, points, path=WORKBOOK):
    """Match each customer leg without treating a trip with stops as a direct ride."""
    if len(addresses) == 2:
        return find_reference_rates(*addresses, *points, path=path)
    result = {"source": Path(path).name, "status": "ok", "matches": [], "pickup_notes": []}
    by_route = {}
    for index in range(len(addresses) - 1):
        reference = find_reference_rates(addresses[index], addresses[index + 1],
                                         points[index], points[index + 1], path=path)
        if reference["status"] != "ok":
            return reference
        if index == 0:
            result["pickup_notes"] = reference["pickup_notes"]
        for match in reference["matches"]:
            key = (match["schedule"], match["route"])
            reason = f"Leg {index + 1}: {match['match']}"
            if key in by_route:
                by_route[key]["match"] += "; " + reason
            else:
                by_route[key] = {**match, "match": reason}
    result["matches"] = list(by_route.values())
    return result
