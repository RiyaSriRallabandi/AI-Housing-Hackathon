from __future__ import annotations

from pathlib import Path

from housing_review.agents.demographic import run_demographic_analyst
from housing_review.agents.equity import run_equity_analyst
from housing_review.agents.pro_forma import run_pro_forma_analyst
from housing_review.agents.sustainability import run_sustainability_analyst
from housing_review.agents.zoning import run_zoning_analyst
from housing_review.data.demo_site import demo_site_record
from housing_review.data.demographics import DemographicSiteContext, load_demographic_site_from_path
from housing_review.data.equity import EquitySiteContext, load_equity_site_from_path
from housing_review.data.overlays import ADU_OVERLAY_LAYER, OFFICIAL_ZONING_MAP_APP, OverlayHit
from housing_review.data.proforma import ProFormaSiteContext, load_proforma_site_from_path
from housing_review.data.site import ZoningSiteContext, load_zoning_site_from_fixtures
from housing_review.data.sustainability import SustainabilitySiteContext, load_sustainability_site_from_path
from housing_review.llm import Completer, complete_json
from housing_review.schemas.common import AnalystName, Typology
from housing_review.schemas.debate import AGENT_ORDER, Round1Transcript

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
RESPONSIBLE = "Decision support only — not legal, financial, or zoning advice."


class Round1Contexts:
    """One site's five data slices. Round 1 never passes assessments between agents."""

    def __init__(
        self,
        *,
        site_id: str,
        zoning: ZoningSiteContext,
        demographic: DemographicSiteContext,
        pro_forma: ProFormaSiteContext,
        equity: EquitySiteContext,
        sustainability: SustainabilitySiteContext,
        demo_record: dict | None = None,
    ) -> None:
        ids = {
            zoning.site_id,
            demographic.site_id,
            pro_forma.site_id,
            equity.site_id,
            sustainability.site_id,
        }
        if ids != {site_id}:
            raise ValueError(f"Context site_id mismatch: expected {site_id!r}, got {ids}")
        self.site_id = site_id
        self.zoning = zoning
        self.demographic = demographic
        self.pro_forma = pro_forma
        self.equity = equity
        self.sustainability = sustainability
        self.demo_record = demo_record


def load_demo_round1_contexts() -> Round1Contexts:
    """Fixture-backed demo contexts so Round 1 tests do not hit the network."""
    record = demo_site_record()
    pin = str(record["pin"])
    zoning = load_zoning_site_from_fixtures(
        FIXTURES / "parcel_0139F00077000000.geojson",
        FIXTURES / "zoning_r2l_sample.geojson",
    )
    sustainability = load_sustainability_site_from_path(FIXTURES / "sustainability_0139F00077000000.json")
    _attach_fixture_overlay_screen(zoning, sustainability)
    return Round1Contexts(
        site_id=pin,
        zoning=zoning,
        demographic=load_demographic_site_from_path(FIXTURES / "demographic_tract_42003191800.json"),
        pro_forma=load_proforma_site_from_path(FIXTURES / "proforma_0139F00077000000.json"),
        equity=load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json"),
        sustainability=sustainability,
        demo_record=record,
    )


def _attach_fixture_overlay_screen(zoning: ZoningSiteContext, sustainability: SustainabilitySiteContext) -> None:
    """Reuse the Sustainability fixture's overlay flags so Zoning is not overlay-blind."""
    hits: list[OverlayHit] = []
    slope = sustainability.steep_slope_25pct
    if slope.flagged:
        hits.append(
            OverlayHit(
                layer_id="steep_slopes_25pct",
                source_url=slope.source_url,
                attributes={"slope25": "Yes"},
            )
        )
    flood = sustainability.flood
    if flood.layer_covers_point:
        hits.append(
            OverlayHit(
                layer_id="floodplain_fema_2026",
                source_url=flood.source_url,
                attributes=dict(flood.attributes),
            )
        )
    zoning.overlays = hits
    zoning.adu_overlay = {
        "in_adu_overlay": False,
        "layer_url": ADU_OVERLAY_LAYER,
        "official_map": OFFICIAL_ZONING_MAP_APP,
        "hits": [],
        "note": (
            "Last live PGHWebZoningOverlays ADU query (2026-09-27): no ADU-named "
            "polygon at this centroid. Fixture Round 1 does not re-query GIS."
        ),
    }


def run_round1(
    contexts: Round1Contexts,
    *,
    typologies: list[Typology] | None = None,
    completers: dict[AnalystName, Completer] | None = None,
) -> Round1Transcript:
    """Run all five Analysts independently. Sequential calls, no peer transcripts."""
    typologies = typologies or list(Typology)
    shared = complete_json
    assessments = []
    for name in AGENT_ORDER:
        generate = (completers or {}).get(name) or shared
        if name is AnalystName.zoning_analyst:
            batch = run_zoning_analyst(
                contexts.zoning,
                typologies=typologies,
                completer=generate,
                demo_record=contexts.demo_record,
            )
        elif name is AnalystName.demographic_analyst:
            batch = run_demographic_analyst(
                contexts.demographic, typologies=typologies, completer=generate
            )
        elif name is AnalystName.pro_forma_analyst:
            batch = run_pro_forma_analyst(
                contexts.pro_forma, typologies=typologies, completer=generate
            )
        elif name is AnalystName.equity_analyst:
            batch = run_equity_analyst(contexts.equity, typologies=typologies, completer=generate)
        elif name is AnalystName.sustainability_analyst:
            batch = run_sustainability_analyst(
                contexts.sustainability, typologies=typologies, completer=generate
            )
        else:
            raise ValueError(f"Unknown analyst {name}")
        assessments.extend(batch)
    return Round1Transcript(
        site_id=contexts.site_id,
        independent=True,
        agents_in_order=list(AGENT_ORDER),
        assessments=assessments,
        notes=[
            RESPONSIBLE,
            "Round 1 is independent: no Analyst receives another Analyst's output.",
            "Agents are called sequentially so one Groq free-tier TPM budget is not shared in parallel.",
        ],
    )
