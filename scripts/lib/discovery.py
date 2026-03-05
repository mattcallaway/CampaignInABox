"""
scripts/lib/discovery.py  — Prompt 8.6

Standalone contest discovery utility.
Scans votes/<year>/<state>/<county>/<slug>/ for detail.xlsx files.
Caches result to derived/index/contests.json.

Usage:
    from scripts.lib.discovery import list_contests
    contests = list_contests(project_root)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def list_contests(project_root: Optional[Path] = None) -> list[dict]:
    """
    Discover all available contests by scanning votes/ folder structure.

    Returns list of dicts:
        {contest_id, year, state, county, contest_slug, title,
         detail_xlsx_path, has_model_outputs}

    Prefers cached derived/index/contests.json if present and fresh.
    """
    root = Path(project_root) if project_root else BASE_DIR
    votes_root = root / "votes"
    cache_path = root / "derived" / "index" / "contests.json"

    contests: list[dict] = []

    if not votes_root.exists():
        return contests

    for detail_xlsx in sorted(votes_root.rglob("detail.xlsx")):
        try:
            # votes/<year>/<state>/<county>/<slug>/detail.xlsx
            parts = detail_xlsx.relative_to(votes_root).parts
            if len(parts) < 5:
                continue
            year, state, county, slug = parts[0], parts[1], parts[2], parts[3]

            contest_id = f"{year}_{state}_{county.lower().replace(' ', '_')}_{slug}"

            # Check for model outputs
            model_dir = root / "derived" / "precinct_models" / state / county
            has_model = any(model_dir.rglob("*.csv")) if model_dir.exists() else False

            # Try to read title from contest.json
            contest_json = detail_xlsx.parent / "contest.json"
            title = "unknown"
            if contest_json.exists():
                try:
                    meta = json.loads(contest_json.read_text(encoding="utf-8"))
                    title = meta.get("title", slug)
                except Exception:
                    pass

            contests.append({
                "contest_id":        contest_id,
                "year":              year,
                "state":             state,
                "county":            county,
                "contest_slug":      slug,
                "title":             title,
                "detail_xlsx_path":  str(detail_xlsx.relative_to(root)),
                "has_model_outputs": has_model,
            })
        except Exception:
            continue

    # Also scan derived/strategy_packs for contests not in votes/
    sp_root = root / "derived" / "strategy_packs"
    if sp_root.exists():
        known_ids = {c["contest_id"] for c in contests}
        for meta_json in sorted(sp_root.rglob("STRATEGY_META.json")):
            try:
                meta = json.loads(meta_json.read_text(encoding="utf-8"))
                cid = meta.get("contest_id", "")
                if cid and cid not in known_ids:
                    contests.append({
                        "contest_id":        cid,
                        "year":              meta.get("year", "unknown"),
                        "state":             meta.get("state", "CA"),
                        "county":            meta.get("county", "unknown"),
                        "contest_slug":      cid.split("_")[-1] if "_" in cid else cid,
                        "title":             cid,
                        "detail_xlsx_path":  None,
                        "has_model_outputs": True,
                    })
                    known_ids.add(cid)
            except Exception:
                continue

    # Cache result
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(contests, indent=2), encoding="utf-8")
    except Exception:
        pass

    return contests
