from __future__ import annotations

from pydantic import BaseModel, ConfigDict

CHAPTER_903_URL = "https://ecode360.com/45474231"
CHAPTER_911_02_URL = "https://ecode360.com/45476524"
TITLE_9_URL = "https://ecode360.com/45474054"
RETRIEVED_ON = "2026-09-26"
CODE_VINTAGE = "Includes legislation through 2026-09-16"

USE_SUBDISTRICTS = {
    "R1D": "Single-Unit Detached Residential",
    "R1A": "Single-Unit Attached Residential",
    "R2": "Two-Unit Residential",
    "R3": "Three-Unit Residential",
    "RM": "Multi-Unit Residential",
}

DENSITY_SUBDISTRICTS = {
    "VL": "Very Low-Density",
    "L": "Low-Density",
    "M": "Moderate-Density",
    "H": "High-Density",
    "VH": "Very-High Density",
}

# Site development standards transcribed from §903.03 (eCode360 Ch. 903, retrieved 2026-09-26).
# Heights/setbacks are the table values; contextual alternatives in §925.06 / §925.07 still apply.
_LOW_RISE = "R1D/R1A/R2/R3"
_RM = "RM"

# Each density: min_lot_sf, and then per group: front, rear, exterior_side, interior_side, height
SITE_DEVELOPMENT = {
    "VL": {
        "min_lot_sf": 6000,
        _LOW_RISE: {
            "front_ft": 30,
            "rear_ft": 30,
            "exterior_side_ft": 30,
            "interior_side": "5 ft on one side; 10 ft on the other side",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
        _RM: {
            "front_ft": 30,
            "rear_ft": 30,
            "exterior_side_ft": 30,
            "interior_side": "30 ft",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
    },
    "L": {
        "min_lot_sf": 3000,
        _LOW_RISE: {
            "front_ft": 30,
            "rear_ft": 30,
            "exterior_side_ft": 30,
            "interior_side": "5 ft",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
        _RM: {
            "front_ft": 25,
            "rear_ft": 25,
            "exterior_side_ft": 30,
            "interior_side": "25 ft",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
    },
    "M": {
        "min_lot_sf": 2400,
        _LOW_RISE: {
            "front_ft": 30,
            "rear_ft": 30,
            "exterior_side_ft": 30,
            "interior_side": "5 ft",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
        _RM: {
            "front_ft": 25,
            "rear_ft": 25,
            "exterior_side_ft": 25,
            "interior_side": "10 ft",
            "max_height": "55 ft (not to exceed 4 stories)",
        },
    },
    "H": {
        "min_lot_sf": 1200,
        _LOW_RISE: {
            "front_ft": 15,
            "rear_ft": 15,
            "exterior_side_ft": 15,
            "interior_side": "5 ft",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
        _RM: {
            "front_ft": 25,
            "rear_ft": 25,
            "exterior_side_ft": 25,
            "interior_side": "10 ft",
            "max_height": "85 ft (not to exceed 9 stories)",
        },
    },
    "VH": {
        "min_lot_sf": None,  # §903.03.E table has no minimum lot size row
        _LOW_RISE: {
            "front_ft": 5,
            "rear_ft": 15,
            "exterior_side_ft": 5,
            "interior_side": "5 ft",
            "max_height": "40 ft (not to exceed 3 stories)",
        },
        _RM: {
            "front_ft": 25,
            "rear_ft": 25,
            "exterior_side_ft": 25,
            "interior_side": "10 ft",
            "max_height": "180 ft",
        },
    },
}


class ResidentialDistrictProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district_code: str
    use_subdistrict: str | None
    use_label: str | None
    density_subdistrict: str | None
    density_label: str | None
    min_lot_sf: int | None
    standards: dict | None
    source: str = CHAPTER_903_URL
    notes: list[str]


def split_residential_code(district_code: str) -> tuple[str | None, str | None]:
    code = district_code.strip().upper()
    if code in USE_SUBDISTRICTS:
        return code, None
    if "-" not in code:
        return None, None
    use, density = code.rsplit("-", 1)
    if use in USE_SUBDISTRICTS and density in DENSITY_SUBDISTRICTS:
        return use, density
    return None, None


def profile_residential_district(district_code: str) -> ResidentialDistrictProfile | None:
    use, density = split_residential_code(district_code)
    if not use:
        return None
    notes = [
        "Primary uses: look up this district's column in the §911.02 Use Table corpus.",
        "Accessory uses including ADU Overlay rules: Chapter 912 corpus; overlay membership is a live map query.",
        "Contextual setbacks/heights may apply per §925.06 and §925.07.",
        f"Dimensional tables transcribed from Chapter 903 corpus; code vintage: {CODE_VINTAGE}. Decision support only.",
    ]
    if use == "RM":
        notes.append("RM construction of 4+ units requires Site Plan Review per §903.02.E.2 / §922.04.")
    if density == "VH":
        notes.append("§903.03.E table does not list a minimum lot size; do not invent one.")
    std = None
    min_lot = None
    if density:
        block = SITE_DEVELOPMENT[density]
        min_lot = block["min_lot_sf"]
        group = _RM if use == "RM" else _LOW_RISE
        if use == "R1A" and density:
            # Interior side for R1A is listed separately; keep the group table and note R1A interior is 5 ft in every density we captured.
            pass
        std = dict(block[group])
        if use == "R1A":
            std["interior_side"] = "5 ft"
    return ResidentialDistrictProfile(
        district_code=district_code,
        use_subdistrict=use,
        use_label=USE_SUBDISTRICTS[use],
        density_subdistrict=density,
        density_label=DENSITY_SUBDISTRICTS.get(density) if density else None,
        min_lot_sf=min_lot,
        standards=std,
        notes=notes,
    )
