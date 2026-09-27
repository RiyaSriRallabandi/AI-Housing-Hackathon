from __future__ import annotations

from housing_review.data.demographics import CensusEstimate, DemographicSiteContext
from housing_review.schemas.analyst import Claim
from housing_review.schemas.common import Typology

USPS_GAP = "USPS postal vacancy was not retrieved."
VACANCY_BY_TYPE_GAP = (
    "ACS tables retrieved do not split vacancy rate by units-in-structure; "
    "B25024 is inventory mix, not vacancy by typology."
)

UNIT_FIELD = {
    Typology.duplex: "units_2",
    Typology.apartment: "units_5_or_more",
    Typology.townhome: "units_1_attached",
    Typology.adu: "nonfamily_households",
    Typology.senior_housing: "population_65_plus",
    Typology.detached_single_family: "units_1_detached",
}


def estimate_source(item: CensusEstimate) -> str:
    return f"{item.vintage} table {item.table_id} variable {item.variable}"


def _fmt(item: CensusEstimate) -> str:
    moe = f" (MOE ±{item.moe})" if item.moe is not None else ""
    return f"{item.value}{moe}"


def _hh_size_note(context: DemographicSiteContext) -> str | None:
    newer = context.acs_2023.avg_household_size
    older = context.acs_2018.avg_household_size
    if None in (newer.value, newer.moe, older.value, older.moe):
        return None
    delta = float(newer.value) - float(older.value)
    combined = (float(newer.moe) ** 2 + float(older.moe) ** 2) ** 0.5
    if abs(delta) <= combined:
        return (
            f"Change in average household size ({older.value} to {newer.value}) is smaller "
            f"than combined MOE (±{round(combined, 2)}); treat as not statistically distinguished."
        )
    return None


def deterministic_claims_for_typology(
    typology: Typology,
    context: DemographicSiteContext,
) -> list[Claim]:
    a23 = context.acs_2023
    a18 = context.acs_2018
    d20 = context.dec_2020
    hh_note = _hh_size_note(context)
    mix_name = UNIT_FIELD[typology]
    mix_item = getattr(a23, mix_name)
    claims = [
        Claim(
            statement=(
                f"ACS 2019-2023 average household size is {_fmt(a23.avg_household_size)}; "
                f"ACS 2014-2018 was {_fmt(a18.avg_household_size)}."
            ),
            basis="measured",
            source=estimate_source(a23.avg_household_size),
            confidence_note=hh_note,
        ),
        Claim(
            statement=(
                f"ACS 2019-2023 vacancy rate is {_fmt(a23.vacancy_rate)} "
                f"({a23.vacant_units.value} vacant of {a23.housing_units.value} units). "
                f"2020 Census PL vacant units: {d20.vacant_units.value}."
            ),
            basis="measured",
            source=estimate_source(a23.vacancy_rate),
            confidence_note="Vacancy is ACS/Decennial housing-unit status, not USPS postal vacancy.",
        ),
        Claim(
            statement=(
                f"Tract population ACS 2019-2023 {_fmt(a23.population)}; "
                f"ACS 2014-2018 {_fmt(a18.population)}; "
                f"2020 Census PL {d20.population.value}."
            ),
            basis="measured",
            source=estimate_source(a23.population),
        ),
        Claim(
            statement=(
                f"ACS 2019-2023 {mix_name.replace('_', ' ')} count is {_fmt(mix_item)} "
                f"(inventory mix for demand-fit context, not vacancy by typology)."
            ),
            basis="measured",
            source=estimate_source(mix_item),
        ),
    ]
    return claims


def facts_pack_for_llm(context: DemographicSiteContext) -> dict:
    a23, a18, d20 = context.acs_2023, context.acs_2018, context.dec_2020

    def pack(item: CensusEstimate) -> dict:
        return {
            "value": item.value,
            "moe": item.moe,
            "var": item.variable,
            "table": item.table_id,
            "vintage": item.vintage,
            "source": estimate_source(item),
        }

    return {
        "geoid": context.geoid,
        "tract_name": context.tract_name,
        "acs_2019_2023": {
            "population": pack(a23.population),
            "vacancy_rate": pack(a23.vacancy_rate),
            "avg_household_size": pack(a23.avg_household_size),
            "family_households": pack(a23.family_households),
            "nonfamily_households": pack(a23.nonfamily_households),
            "units_1_detached": pack(a23.units_1_detached),
            "units_1_attached": pack(a23.units_1_attached),
            "units_2": pack(a23.units_2),
            "units_3_to_4": pack(a23.units_3_to_4),
            "units_5_or_more": pack(a23.units_5_or_more),
            "population_65_plus": pack(a23.population_65_plus),
        },
        "acs_2014_2018": {
            "population": pack(a18.population),
            "vacancy_rate": pack(a18.vacancy_rate),
            "avg_household_size": pack(a18.avg_household_size),
            "family_households": pack(a18.family_households),
            "nonfamily_households": pack(a18.nonfamily_households),
        },
        "census_2020_pl": {
            "population": pack(d20.population),
            "vacant_units": pack(d20.vacant_units),
        },
        "household_size_change_vs_moe": _hh_size_note(context),
        "unit_mix_field_by_typology": {item.value: UNIT_FIELD[item] for item in Typology},
    }


def code_side_cannot_determine() -> list[str]:
    return [
        USPS_GAP,
        VACANCY_BY_TYPE_GAP,
        "County Housing Needs Assessment is subregion-scale and was not used for parcel-level claims.",
    ]
