from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.census import fetch_demographic_tables, geocode_tract

STRICT = ConfigDict(extra="forbid")


class CensusEstimate(BaseModel):
    model_config = STRICT

    value: float | int | None
    moe: float | int | None = None
    variable: str
    table_id: str
    vintage: str


class GeocoderMeta(BaseModel):
    model_config = STRICT

    source: str
    url: str
    benchmark: str
    vintage: str
    retrieved_on: str


class Acs2023Slice(BaseModel):
    model_config = STRICT

    population: CensusEstimate
    housing_units: CensusEstimate
    occupied_units: CensusEstimate
    vacant_units: CensusEstimate
    vacancy_rate: CensusEstimate
    avg_household_size: CensusEstimate
    households: CensusEstimate
    family_households: CensusEstimate
    nonfamily_households: CensusEstimate
    units_1_detached: CensusEstimate
    units_1_attached: CensusEstimate
    units_2: CensusEstimate
    units_3_to_4: CensusEstimate
    units_5_or_more: CensusEstimate
    population_65_plus: CensusEstimate


class Acs2018Slice(BaseModel):
    model_config = STRICT

    population: CensusEstimate
    housing_units: CensusEstimate
    occupied_units: CensusEstimate
    vacant_units: CensusEstimate
    vacancy_rate: CensusEstimate
    avg_household_size: CensusEstimate
    households: CensusEstimate
    family_households: CensusEstimate
    nonfamily_households: CensusEstimate


class Decennial2020Slice(BaseModel):
    model_config = STRICT

    population: CensusEstimate
    housing_units: CensusEstimate
    occupied_units: CensusEstimate
    vacant_units: CensusEstimate


class DemographicSiteContext(BaseModel):
    """Tract ACS + Decennial slice for the Demographic Analyst. Not a demand verdict."""

    model_config = STRICT

    site_id: str
    geoid: str
    tract_name: str
    state: str
    county: str
    tract: str
    lon: float
    lat: float
    geocoder: GeocoderMeta
    acs_2023: Acs2023Slice
    acs_2018: Acs2018Slice
    dec_2020: Decennial2020Slice
    coverage_notes: list[str] = Field(default_factory=list)


def load_demographic_site_from_path(path: Path) -> DemographicSiteContext:
    return DemographicSiteContext.model_validate(json.loads(path.read_text()))


def _num(value: object) -> float | int | None:
    if value in (None, "", ".", "-888888888", "(X)"):
        return None
    text = str(value)
    if "." in text:
        return float(text)
    return int(text)


def _est(row: dict, variable: str, table_id: str, vintage: str) -> CensusEstimate:
    moe_key = variable[:-1] + "M" if variable.endswith("E") else None
    return CensusEstimate(
        value=_num(row.get(variable)),
        moe=_num(row.get(moe_key)) if moe_key else None,
        variable=variable,
        table_id=table_id,
        vintage=vintage,
    )


def _rate(numer: CensusEstimate, denom: CensusEstimate) -> CensusEstimate:
    if not numer.value or not denom.value:
        value = None
    else:
        value = round(float(numer.value) / float(denom.value), 4)
    return CensusEstimate(
        value=value,
        moe=None,
        variable=f"{numer.variable}/{denom.variable}",
        table_id=numer.table_id,
        vintage=numer.vintage,
    )


def compact_tables(
    *,
    site_id: str,
    lon: float,
    lat: float,
    tract: dict[str, str],
    tables: dict[str, dict],
    retrieved_on: str,
) -> DemographicSiteContext:
    v23 = "ACS 5-Year 2019-2023"
    v18 = "ACS 5-Year 2014-2018"
    v20 = "2020 Census PL 94-171"
    pop = tables["ACSDT5Y2023.B01003"]
    occ = tables["ACSDT5Y2023.B25002"]
    size = tables["ACSDT5Y2023.B25010"]
    structure = tables["ACSDT5Y2023.B25024"]
    hh = tables["ACSDT5Y2023.B11001"]
    age = tables["ACSDT5Y2023.B01001"]
    pop18 = tables["ACSDT5Y2018.B01003"]
    occ18 = tables["ACSDT5Y2018.B25002"]
    size18 = tables["ACSDT5Y2018.B25010"]
    hh18 = tables["ACSDT5Y2018.B11001"]
    p1 = tables["DECENNIALPL2020.P1"]
    h1 = tables["DECENNIALPL2020.H1"]

    age65_vars = [
        "B01001_020E",
        "B01001_021E",
        "B01001_022E",
        "B01001_023E",
        "B01001_024E",
        "B01001_025E",
        "B01001_044E",
        "B01001_045E",
        "B01001_046E",
        "B01001_047E",
        "B01001_048E",
        "B01001_049E",
    ]
    pop65 = sum(_num(age[item]) or 0 for item in age65_vars)
    units_5 = sum(
        _num(structure[item]) or 0
        for item in ("B25024_006E", "B25024_007E", "B25024_008E", "B25024_009E")
    )

    pop_e = _est(pop, "B01003_001E", "ACSDT5Y2023.B01003", v23)
    hu = _est(occ, "B25002_001E", "ACSDT5Y2023.B25002", v23)
    vacant = _est(occ, "B25002_003E", "ACSDT5Y2023.B25002", v23)
    pop18_e = _est(pop18, "B01003_001E", "ACSDT5Y2018.B01003", v18)
    hu18 = _est(occ18, "B25002_001E", "ACSDT5Y2018.B25002", v18)
    vacant18 = _est(occ18, "B25002_003E", "ACSDT5Y2018.B25002", v18)

    return DemographicSiteContext(
        site_id=site_id,
        geoid=tract["geoid"],
        tract_name=tract["name"],
        state=tract["state"],
        county=tract["county"],
        tract=tract["tract"],
        lon=lon,
        lat=lat,
        geocoder=GeocoderMeta(
            source="U.S. Census Bureau Geocoder (TIGER-backed)",
            url="https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
            benchmark="Public_AR_Current",
            vintage="Current_Current",
            retrieved_on=retrieved_on,
        ),
        acs_2023=Acs2023Slice(
            population=pop_e,
            housing_units=hu,
            occupied_units=_est(occ, "B25002_002E", "ACSDT5Y2023.B25002", v23),
            vacant_units=vacant,
            vacancy_rate=_rate(vacant, hu),
            avg_household_size=_est(size, "B25010_001E", "ACSDT5Y2023.B25010", v23),
            households=_est(hh, "B11001_001E", "ACSDT5Y2023.B11001", v23),
            family_households=_est(hh, "B11001_002E", "ACSDT5Y2023.B11001", v23),
            nonfamily_households=_est(hh, "B11001_007E", "ACSDT5Y2023.B11001", v23),
            units_1_detached=_est(structure, "B25024_002E", "ACSDT5Y2023.B25024", v23),
            units_1_attached=_est(structure, "B25024_003E", "ACSDT5Y2023.B25024", v23),
            units_2=_est(structure, "B25024_004E", "ACSDT5Y2023.B25024", v23),
            units_3_to_4=_est(structure, "B25024_005E", "ACSDT5Y2023.B25024", v23),
            units_5_or_more=CensusEstimate(
                value=units_5,
                moe=None,
                variable="B25024_006E+B25024_007E+B25024_008E+B25024_009E",
                table_id="ACSDT5Y2023.B25024",
                vintage=v23,
            ),
            population_65_plus=CensusEstimate(
                value=pop65,
                moe=None,
                variable="B01001_020E-025E+B01001_044E-049E",
                table_id="ACSDT5Y2023.B01001",
                vintage=v23,
            ),
        ),
        acs_2018=Acs2018Slice(
            population=pop18_e,
            housing_units=hu18,
            occupied_units=_est(occ18, "B25002_002E", "ACSDT5Y2018.B25002", v18),
            vacant_units=vacant18,
            vacancy_rate=_rate(vacant18, hu18),
            avg_household_size=_est(size18, "B25010_001E", "ACSDT5Y2018.B25010", v18),
            households=_est(hh18, "B11001_001E", "ACSDT5Y2018.B11001", v18),
            family_households=_est(hh18, "B11001_002E", "ACSDT5Y2018.B11001", v18),
            nonfamily_households=_est(hh18, "B11001_007E", "ACSDT5Y2018.B11001", v18),
        ),
        dec_2020=Decennial2020Slice(
            population=_est(p1, "P1_001N", "DECENNIALPL2020.P1", v20),
            housing_units=_est(h1, "H1_001N", "DECENNIALPL2020.H1", v20),
            occupied_units=_est(h1, "H1_002N", "DECENNIALPL2020.H1", v20),
            vacant_units=_est(h1, "H1_003N", "DECENNIALPL2020.H1", v20),
        ),
        coverage_notes=[
            "Decision support only — not legal, financial, or zoning advice.",
            "Tract-level ACS estimates have margins of error; do not treat point estimates as exact.",
            "2018 ACS 5-Year (2014-2018) and 2023 ACS 5-Year (2019-2023) do not overlap; small population changes may be insignificant given MOE.",
            "Vacancy is ACS/Decennial housing-unit vacant status, not USPS postal vacancy (Useful source not retrieved).",
            "ACS tables retrieved do not split vacancy rate by units-in-structure; B25024 is inventory mix, not vacancy by typology.",
            "County Housing Needs Assessment is subregion-scale and was not used for parcel-level claims.",
        ],
    )


def load_demographic_site(site_id: str, lon: float, lat: float, *, retrieved_on: str = "2026-09-26") -> DemographicSiteContext:
    tract = geocode_tract(lon, lat)
    tables = fetch_demographic_tables(tract["geoid"])
    return compact_tables(
        site_id=site_id,
        lon=lon,
        lat=lat,
        tract=tract,
        tables=tables,
        retrieved_on=retrieved_on,
    )
