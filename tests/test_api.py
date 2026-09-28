from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from housing_review.analysis import save_analysis
from housing_review.api import create_app
from housing_review.schemas.chair import ChairSynthesis
from housing_review.schemas.common import AnalystName
from housing_review.schemas.debate import Round1Transcript
from tests.test_weighting import SITE, _chair, _round1

ORDER = [
    AnalystName.zoning_analyst.value,
    AnalystName.sustainability_analyst.value,
    AnalystName.demographic_analyst.value,
    AnalystName.pro_forma_analyst.value,
    AnalystName.equity_analyst.value,
]


def _seed(tmp_path: Path) -> None:
    save_analysis(tmp_path, _round1(), _chair())


def _client(tmp_path: Path, runner=None) -> TestClient:
    return TestClient(create_app(cache_root=tmp_path, runner=runner))


def test_get_analysis_returns_cache_without_runner(tmp_path: Path) -> None:
    _seed(tmp_path)
    calls = {"n": 0}

    def boom(site_id: str):
        calls["n"] += 1
        raise AssertionError("LLM pipeline must not run when cache exists")

    response = _client(tmp_path, runner=boom).get(f"/analysis/{SITE}")
    assert response.status_code == 200
    body = response.json()
    assert body["from_cache"] is True
    assert body["site_id"] == SITE
    assert len(body["round_1"]["assessments"]) == 30
    assert len(body["chair"]["typology_comparison"]) == 6
    assert calls["n"] == 0
    print("GET /analysis", SITE, "from_cache", body["from_cache"], "status", response.status_code)


def test_get_analysis_runs_once_then_reads_disk(tmp_path: Path) -> None:
    calls = {"n": 0}

    def runner(site_id: str) -> tuple[Round1Transcript, ChairSynthesis]:
        calls["n"] += 1
        assert site_id == SITE
        return _round1(), _chair()

    client = _client(tmp_path, runner=runner)
    first = client.get(f"/analysis/{SITE}")
    second = client.get(f"/analysis/{SITE}")
    assert first.status_code == 200
    assert first.json()["from_cache"] is False
    assert second.json()["from_cache"] is True
    assert calls["n"] == 1


def test_post_weighted_view_from_preference_order(tmp_path: Path) -> None:
    _seed(tmp_path)
    def boom(site_id: str):
        raise AssertionError("weighted-view must not call the LLM pipeline")

    response = _client(tmp_path, runner=boom).post(
        f"/weighted-view/{SITE}",
        json={"preference_order": ORDER},
    )
    assert response.status_code == 200
    view = response.json()["view"]
    assert view["view_label"] == "user-weighted view"
    assert view["ranking"][0]["rank"] == 1
    assert view["ranking"][0]["contributions"]
    print(
        "POST /weighted-view preference_order ->",
        [(row["rank"], row["typology"], round(row["weighted_score"], 3)) for row in view["ranking"]],
    )


def test_post_weighted_view_from_slider_weights(tmp_path: Path) -> None:
    _seed(tmp_path)
    first = _client(tmp_path).post(f"/weighted-view/{SITE}", json={"preference_order": ORDER})
    weights = dict(first.json()["view"]["weights"])
    weights["sustainability_analyst"] = weights["sustainability_analyst"] + 0.2
    second = _client(tmp_path).post(f"/weighted-view/{SITE}", json={"weights": weights})
    assert second.status_code == 200
    assert second.json()["view"]["weights"]["sustainability_analyst"] > first.json()["view"]["weights"][
        "sustainability_analyst"
    ]


def test_post_weighted_view_requires_cached_analysis(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        f"/weighted-view/{SITE}",
        json={"preference_order": ORDER},
    )
    assert response.status_code == 404


def test_demo_site_returns_parcel_outline(tmp_path: Path) -> None:
    demo = _client(tmp_path).get("/demo-site")
    assert demo.status_code == 200
    assert "0139F00077000000" in demo.json()["map_description"]
    assert demo.json()["geometry"]["type"] == "Polygon"


def test_index_and_static_assets_are_served(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/")
    assert page.status_code == 200
    assert "Typescape" in page.text
    assert "Get Started" in page.text
    assert "TYPESCAPE" in page.text
    assert "typescape-logo-inverse.svg" in page.text
    assert "typescape-logo-inverse-icon.svg" in page.text
    assert "Start typing an address or PIN, for example 170 Aidan Ct" in page.text
    css = client.get("/static/styles.css")
    assert css.status_code == 200
    assert "--site-backdrop-image" in css.text
    assert "pittsburgh-housing.jpg" in css.text
    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "Sortable.create" in js.text
    assert "tile.openstreetmap.org" in js.text
    assert "Cost and feasibility" in js.text
