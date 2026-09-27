from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.residential import ResidentialDistrictProfile
from housing_review.data.zoning_districts import ZoningDistrictHit


class ZoningCodeCitation(BaseModel):
    """A checkable pointer into Title 9. Body text is omitted until retrieval works."""

    model_config = ConfigDict(extra="forbid")

    district_code: str
    title: str
    url: str | None
    retrieval_status: str = Field(
        description="url_only until section text can be retrieved without a bot wall"
    )
    next_step: str
    body: str | None = None


def citations_for_districts(
    districts: list[ZoningDistrictHit],
    *,
    profile: ResidentialDistrictProfile | None = None,
) -> list[ZoningCodeCitation]:
    citations: list[ZoningCodeCitation] = []
    for hit in districts:
        url = hit.code_url or "https://ecode360.com/45474054"
        retrieved = bool(profile and profile.use_subdistrict)
        citations.append(
            ZoningCodeCitation(
                district_code=hit.district_code,
                title=f"Pittsburgh Zoning Code (Title 9) — district {hit.district_code}",
                url=url,
                retrieval_status="retrieved_browser" if retrieved else "url_only",
                next_step=(
                    "Confirm interpretation with City Planning. Corpus includes Chapters 903, 911, 912, 913, and 914."
                    if retrieved
                    else "Open the cited eCode360 section."
                ),
                body=None,
            )
        )
    if not citations:
        citations.append(
            ZoningCodeCitation(
                district_code="unknown",
                title="Pittsburgh Zoning Code (Title 9)",
                url="https://ecode360.com/45474054",
                retrieval_status="url_only",
                next_step="Confirm zoning district with City Planning; GIS returned no district for this point.",
                body=None,
            )
        )
    return citations
