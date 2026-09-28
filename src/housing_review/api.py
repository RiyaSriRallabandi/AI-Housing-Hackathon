"""HTTP API over cached Round 1 / Chair and the deterministic weighted view."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, model_validator

from housing_review.analysis import (
    DEFAULT_ANALYSIS_DIR,
    AnalysisRunner,
    get_or_run_analysis,
    load_cached_analysis,
)
from housing_review.data.demo_site import demo_site_map_payload
from housing_review.schemas.common import STRICT_CONFIG, AnalystName
from housing_review.weighting import apply_weighted_view

WEB_DIR = Path(__file__).resolve().parent / "web"

RESPONSIBLE_USE = (
    "Decision support only. This is not legal, financial, or zoning advice. "
    "Verify findings with the relevant office before acting."
)


class WeightedViewBody(BaseModel):
    model_config = STRICT_CONFIG

    preference_order: list[AnalystName] | None = None
    weights: dict[str, float] | None = None

    @model_validator(mode="after")
    def _one_source(self) -> WeightedViewBody:
        if self.preference_order is not None and self.weights is not None:
            raise ValueError("Provide preference_order or weights, not both")
        if self.preference_order is None and self.weights is None:
            raise ValueError("Provide preference_order or weights")
        return self


class AppState:
    def __init__(self, cache_root: Path, runner: AnalysisRunner | None) -> None:
        self.cache_root = cache_root
        self.runner = runner


def create_app(
    *,
    cache_root: Path | None = None,
    runner: AnalysisRunner | None = None,
) -> FastAPI:
    app = FastAPI(title="Typescape", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.bundle = AppState(cache_root or DEFAULT_ANALYSIS_DIR, runner)

    @app.get("/demo-site")
    def demo_site() -> dict[str, Any]:
        return demo_site_map_payload()

    @app.get("/analysis/{site_id}")
    def get_analysis(site_id: str) -> dict[str, Any]:
        state: AppState = app.state.bundle
        try:
            round1, chair, from_cache = get_or_run_analysis(
                site_id,
                cache_root=state.cache_root,
                runner=state.runner,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "site_id": round1.site_id,
            "from_cache": from_cache,
            "responsible_use": RESPONSIBLE_USE,
            "round_1": round1.model_dump(mode="json"),
            "chair": chair.model_dump(mode="json"),
        }

    @app.post("/weighted-view/{site_id}")
    def post_weighted_view(site_id: str, body: WeightedViewBody) -> dict[str, Any]:
        state: AppState = app.state.bundle
        try:
            cached = load_cached_analysis(state.cache_root, site_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if cached is None:
            raise HTTPException(
                status_code=404,
                detail="No cached analysis for this site. GET /analysis/{site_id} first.",
            )
        round1, chair = cached
        try:
            view = apply_weighted_view(
                round1,
                chair,
                preference_order=body.preference_order,
                weights=body.weights,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "site_id": site_id,
            "responsible_use": RESPONSIBLE_USE,
            "view": view.model_dump(mode="json"),
        }

    if (WEB_DIR / "index.html").is_file():

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


app = create_app()
