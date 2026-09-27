from __future__ import annotations

from housing_review.data.sustainability import SustainabilitySiteContext
from housing_review.schemas.analyst import Claim
from housing_review.schemas.common import Typology

CARBON_SOURCE = (
    "Generic typology-level direction (not a site LCA or measured kg CO2); "
    "higher density generally lower per-unit carbon and car-dependency than detached single-family."
)

CARBON_STATEMENT = {
    Typology.detached_single_family: (
        "Generic direction: detached single-family typically has higher per-unit embodied/"
        "operational carbon and car-dependency than denser typologies on the same site."
    ),
    Typology.adu: (
        "Generic direction: an ADU increment on an existing lot is generally lower per-unit "
        "carbon than a new detached house, without a site LCA."
    ),
    Typology.duplex: (
        "Generic direction: two-unit buildings generally have lower per-unit carbon and "
        "car-dependency than detached single-family, without a site LCA."
    ),
    Typology.townhome: (
        "Generic direction: attached single-unit (townhome) generally has lower per-unit "
        "carbon than detached single-family, without a site LCA."
    ),
    Typology.apartment: (
        "Generic direction: multi-unit buildings generally have lower per-unit carbon and "
        "car-dependency than detached single-family, without a site LCA."
    ),
    Typology.senior_housing: (
        "Generic direction: senior housing at multi-unit density generally has lower per-unit "
        "carbon than detached single-family, without a site LCA."
    ),
}


def prt_source(context: SustainabilitySiteContext) -> str:
    prt = context.prt
    feed = prt.feed_version or "unknown"
    return (
        f"WPRDC PRT Transit Stops resource {prt.resource_id}, feed_version {feed}; "
        f"{prt.resolved_url}; retrieved {prt.retrieved_on}"
    )


def flood_source(context: SustainabilitySiteContext) -> str:
    flood = context.flood
    return (
        f"City FEMA_2026 overlay {flood.source_url}; NFHL catalog {flood.catalog_url}"
    )


def deterministic_claims_for_typology(
    typology: Typology,
    context: SustainabilitySiteContext,
) -> list[Claim]:
    flood = context.flood
    prt = context.prt
    nearest = prt.nearest[0] if prt.nearest else None
    if nearest:
        transit_stmt = (
            f"Nearest scheduled PRT stop is {nearest.stop_name} ({nearest.mode}), "
            f"about {round(nearest.distance_m)} m from the parcel centroid; "
            f"{prt.unique_within_400m} unique stops within 400 m, "
            f"{prt.unique_within_800m} unique stops within 800 m, "
            f"{prt.unique_within_1500ft} within 1,500 ft."
        )
    else:
        transit_stmt = "No PRT stop within the retrieved search radius of the parcel centroid."
    buffer = context.major_transit_buffer
    return [
        Claim(
            statement=transit_stmt,
            basis="measured",
            source=prt_source(context),
            confidence_note=(
                "Scheduled GTFS-derived service is not on-time reliability. "
                f"City 1,500 ft major-transit overlay: "
                f"in_buffer={buffer.in_1500ft_major_transit_buffer}. {buffer.note}"
            ),
        ),
        Claim(
            statement=(
                f"FEMA-style flood screen: layer_covers_point={flood.layer_covers_point}, "
                f"FLD_ZONE={flood.fld_zone}, SFHA_TF={flood.sfha_tf}, in_sfha={flood.in_sfha}. "
                f"Steep-slope 25%+ overlay flagged={context.steep_slope_25pct.flagged}."
            ),
            basis="measured",
            source=flood_source(context),
            confidence_note=f"{flood.caveat} {context.steep_slope_25pct.caveat}",
        ),
        Claim(
            statement=CARBON_STATEMENT[typology],
            basis="estimated",
            source=CARBON_SOURCE,
            confidence_note="Generic typology-level direction only; not calculated for this building.",
        ),
    ]


def facts_pack_for_llm(
    context: SustainabilitySiteContext,
    typologies: list[Typology],
) -> list[dict]:
    """Only the cited claim statements — not extra PRT rows or unclaimed counts."""
    pack = []
    for typology in typologies:
        claims = deterministic_claims_for_typology(typology, context)
        pack.append(
            {
                "typology": typology.value,
                "claims": [
                    {
                        "statement": item.statement,
                        "source": item.source,
                        "basis": item.basis.value,
                    }
                    for item in claims
                ],
            }
        )
    return pack


def code_side_cannot_determine() -> list[str]:
    return [
        "On-time reliability of scheduled PRT trips.",
        "Site-specific LCA or measured kg CO2.",
        "PA DEP eMapPA and EPA EJScreen were not retrieved.",
    ]
