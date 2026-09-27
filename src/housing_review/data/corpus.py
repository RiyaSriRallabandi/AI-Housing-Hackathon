from __future__ import annotations

import json
import re
from pathlib import Path

from housing_review.data.residential import split_residential_code

CORPUS_DIR = Path(__file__).resolve().parents[3] / "data" / "zoning_corpus"
RETRIEVED_ON = "2026-09-26"

CHAPTER_URLS = {
    "903": "https://ecode360.com/45474194",
    "911": "https://ecode360.com/45476524",
    "912": "https://ecode360.com/45477814",
    "913": "https://ecode360.com/45477960",
    "914": "https://ecode360.com/45478031",
}

# Brief/schema slugs vs Title 9 primary-use names (eCode360 Ch. 911, retrieved 2026-09-26).
# The JSON typology field stays the brief slug. Claims should cite the Title 9 name.
TYPOLOGY_TITLE9 = {
    "duplex": {
        "title9_use": "Two-Unit Residential",
        "definition": "Two dwelling units contained within a single building.",
    },
    "apartment": {
        "title9_use": "Multi-Unit Residential",
        "definition": "Four or more dwelling units contained within a single building.",
    },
    "townhome": {
        "title9_use": "Single-Unit Attached Residential",
        "definition": (
            "One dwelling unit on its own separate lot, attached to one or more "
            "dwelling units by a party wall or separate abutting wall. Title 9 "
            "does not use the words townhome or townhouse."
        ),
    },
    "adu": {
        "title9_use": "Accessory Dwelling Unit (Chapter 912, including §912.08)",
        "definition": "Accessory use, not a §911.02 primary-use row. Overlay membership is a live map query.",
    },
    "senior_housing": {
        "title9_use": "Housing for the Elderly (Limited) / Housing for the Elderly (General)",
        "definition": "Look up both Use Table rows for this district column; they may differ (P / S / A / blank).",
    },
    "detached_single_family": {
        "title9_use": "Single-Unit Detached Residential",
        "definition": "One detached housing unit on a zoning lot.",
    },
}

HOUSING_USE_PREFIXES = (
    "Single-Unit Detached",
    "Single-Unit Attached",
    "Two-Unit Residential",
    "Three-Unit Residential",
    "Multi-Unit Residential",
    "Assisted Living",
    "Housing for the Elderly",
)

DENSITY_HEADINGS = {
    "VL": "Very-Low Density Subdistrict",
    "L": "Low Density Subdistrict",
    "M": "Moderate Density Subdistrict",
    "H": "High Density Subdistrict",
    "VH": "Very-High Density Subdistrict",
}


def _read(name: str) -> str:
    return (CORPUS_DIR / name).read_text()


def use_table() -> dict:
    return json.loads((CORPUS_DIR / "use_table_911_02.json").read_text())


def use_table_column_key(district_code: str) -> str | None:
    """Map a GIS district (e.g. R2-L, NDO, RIV-MU) to a §911.02 column key."""
    code = district_code.strip().upper()
    table = use_table()
    columns: list[str] = table["district_columns"]
    if code in columns:
        return code
    use, _density = split_residential_code(code)
    if use and use in columns:
        return use
    if code.startswith("RIV-") and code in columns:
        return code
    prefix = code.split("-", 1)[0]
    if prefix in columns:
        return prefix
    return None


def permissions_for_district(district_code: str) -> list[dict]:
    column = use_table_column_key(district_code)
    if not column:
        return []
    rows = []
    for item in use_table()["rows"]:
        if item.get("type") != "use":
            continue
        use_name = item["use"]
        if not any(use_name.startswith(prefix) for prefix in HOUSING_USE_PREFIXES):
            continue
        status = (item.get("byDistrict") or {}).get(column, "")
        rows.append(
            {
                "use": use_name,
                "status": status or "(blank — not permitted in this column)",
                "standard": item.get("standard") or "",
                "district_column": column,
                "source": "§911.02 Use Table",
            }
        )
    return rows


def chapter_903_density_excerpt(density_code: str | None) -> str | None:
    if not density_code:
        return None
    heading = DENSITY_HEADINGS.get(density_code.upper())
    if not heading:
        return None
    text = _read("ch903.txt")
    start = text.find(heading)
    if start < 0:
        return None
    # include the Map Designation paragraph just before the table heading when present
    block_start = text.rfind("\n", 0, start)
    nxt = len(text)
    order = ["VL", "L", "M", "H", "VH"]
    try:
        idx = order.index(density_code.upper())
    except ValueError:
        idx = -1
    if idx >= 0:
        for later in order[idx + 1 :]:
            later_h = DENSITY_HEADINGS[later]
            pos = text.find(later_h, start + 1)
            if pos > start:
                nxt = pos
                break
    excerpt = text[max(0, start - 400) : nxt].strip()
    return excerpt[:4000]


def section_912_08() -> str:
    text = _read("ch912.txt")
    marker = "§\xa0912.08"
    start = text.rfind(marker)
    if start < 0:
        start = text.rfind("§ 912.08")
    if start < 0:
        return text[-4000:]
    return text[start:].strip()


def parking_schedule_residential_excerpt() -> str:
    """Residential rows of Parking Schedule A — not the chapter TOC."""
    text = _read("ch914.txt")
    marker = "Schedule A. Off-street parking spaces shall be provided"
    start = text.find(marker)
    if start < 0:
        start = text.rfind("§\xa0914.02")
    if start < 0:
        start = text.rfind("914.02")
    if start < 0:
        return text[:2500]
    end = text.find("Non-Residential Uses", start)
    if end < 0:
        end = start + 4000
    return text[start:end].strip()


def lookup_for_mapped_districts(district_codes: list[str]) -> dict:
    """District-dynamic excerpts from the full corpus. Not a site-specific store."""
    primary = district_codes[0] if district_codes else None
    use, density = split_residential_code(primary) if primary else (None, None)
    return {
        "retrieved_on": RETRIEVED_ON,
        "corpus_scope": (
            "Residential-relevant Title 9 chapters 903, 911, 912, 913, and 914 "
            f"from eCode360, retrieved {RETRIEVED_ON}. Commercial/industrial-only "
            "chapters are out of scope by design."
        ),
        "chapter_urls": CHAPTER_URLS,
        "mapped_districts": district_codes,
        "use_subdistrict": use,
        "density_subdistrict": density,
        "use_table_column": use_table_column_key(primary) if primary else None,
        "typology_title9_names": TYPOLOGY_TITLE9,
        "use_table_legend": use_table().get("legend"),
        "use_permissions_this_column": permissions_for_district(primary) if primary else [],
        "chapter_903_density_excerpt": chapter_903_density_excerpt(density),
        "chapter_912_08_adu_overlay_rules": section_912_08(),
        "chapter_913_note": (
            "Chapter 913 lists administrator/special/conditional exceptions not in the "
            "Use Table; it is not a substitute for §911.02."
        ),
        "chapter_914_parking_excerpt": parking_schedule_residential_excerpt(),
    }
