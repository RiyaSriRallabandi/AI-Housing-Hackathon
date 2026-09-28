"""Disk cache for Round 1 + Chair. GET must not rerun the LLM when these files exist."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from housing_review.agents.chair import run_chair
from housing_review.data.cache import REPO_ROOT
from housing_review.data.demo_site import demo_site_id
from housing_review.debate.round1 import load_demo_round1_contexts, run_round1
from housing_review.schemas.chair import ChairSynthesis
from housing_review.schemas.debate import Round1Transcript

DEFAULT_ANALYSIS_DIR = REPO_ROOT / "data" / "cache" / "analysis"
LIVE_DEMO_ROUND1 = REPO_ROOT / "data" / "cache" / "round1_live_gemini35lite_equity_guard.json"
LIVE_DEMO_CHAIR = REPO_ROOT / "data" / "cache" / "chair_live.json"
AnalysisRunner = Callable[[str], tuple[Round1Transcript, ChairSynthesis]]


def _safe_site_id(site_id: str) -> str:
    cleaned = site_id.strip()
    if not cleaned or not re.fullmatch(r"[A-Za-z0-9._-]+", cleaned):
        raise ValueError("site_id must be a parcel PIN or similar token")
    return cleaned


def analysis_dir(root: Path, site_id: str) -> Path:
    return root / _safe_site_id(site_id)


def load_cached_analysis(root: Path, site_id: str) -> tuple[Round1Transcript, ChairSynthesis] | None:
    folder = analysis_dir(root, site_id)
    round1_path = folder / "round1.json"
    chair_path = folder / "chair.json"
    if not round1_path.exists() or not chair_path.exists():
        return None
    round1 = _read_round1(round1_path)
    chair = _read_chair(chair_path)
    if round1.site_id != site_id or chair.site_id != site_id:
        raise ValueError("Cached analysis site_id does not match the request")
    return round1, chair


def save_analysis(root: Path, round1: Round1Transcript, chair: ChairSynthesis) -> None:
    if round1.site_id != chair.site_id:
        raise ValueError("Round 1 and Chair site_id must match before caching")
    folder = analysis_dir(root, round1.site_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "round1.json").write_text(json.dumps(round1.model_dump(mode="json"), indent=2))
    (folder / "chair.json").write_text(json.dumps(chair.model_dump(mode="json"), indent=2))


def get_or_run_analysis(
    site_id: str,
    *,
    cache_root: Path,
    runner: AnalysisRunner | None = None,
) -> tuple[Round1Transcript, ChairSynthesis, bool]:
    """Return cached Round 1 + Chair, or run once and write the cache. Never rerun if present."""
    site_id = _safe_site_id(site_id)
    cached = load_cached_analysis(cache_root, site_id)
    if cached is not None:
        return cached[0], cached[1], True
    if site_id == demo_site_id() and import_live_demo_cache(cache_root):
        cached = load_cached_analysis(cache_root, site_id)
        if cached is not None:
            return cached[0], cached[1], True
    generate = runner or default_analysis_runner
    round1, chair = generate(site_id)
    save_analysis(cache_root, round1, chair)
    return round1, chair, False


def import_live_demo_cache(cache_root: Path) -> bool:
    """Reuse a prior live Round 1 + Chair run for the demo PIN. Does not call an LLM."""
    pin = demo_site_id()
    if load_cached_analysis(cache_root, pin) is not None:
        return False
    if not LIVE_DEMO_ROUND1.exists() or not LIVE_DEMO_CHAIR.exists():
        return False
    try:
        round1 = _read_round1(LIVE_DEMO_ROUND1)
        chair = _read_chair(LIVE_DEMO_CHAIR)
    except (ValueError, TypeError, json.JSONDecodeError):
        return False
    if round1.site_id != pin or chair.site_id != pin:
        return False
    save_analysis(cache_root, round1, chair)
    return True


def default_analysis_runner(site_id: str) -> tuple[Round1Transcript, ChairSynthesis]:
    """Live pipeline. Only the Brookline demo parcel is wired in this slice."""
    if site_id != demo_site_id():
        raise LookupError(
            f"No cached analysis for {site_id}. This demo runs Round 1 + Chair only for "
            f"parcel {demo_site_id()} (170 Aidan Ct)."
        )
    round1 = run_round1(load_demo_round1_contexts())
    chair = run_chair(round1)
    return round1, chair


def _read_round1(path: Path) -> Round1Transcript:
    data = json.loads(path.read_text())
    data.pop("live_meta", None)
    return Round1Transcript.model_validate(data)


def _read_chair(path: Path) -> ChairSynthesis:
    data = json.loads(path.read_text())
    data.pop("live_meta", None)
    return ChairSynthesis.model_validate(data)
