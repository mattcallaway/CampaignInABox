"""
scripts/tools/audit_post_prompt85.py

Campaign In A Box — Post-Prompt-8.5 Full System Audit (25 steps)
Covers: ingestion, geography, crosswalks, features, modeling, scoring,
        turfs, forecasting, Monte Carlo, ops planning, strategy generator,
        UI integration, NEEDS system, repo health.

Writes: JSON + Markdown reports + export bundle.
Does NOT modify any code or data files.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

# ── Project root ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TS = datetime.datetime.now().strftime("%Y-%m-%d__%H%M%S")
AUDIT_ID = f"{TS}__post_prompt85_full_audit"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _read_yaml(p: Path) -> dict:
    try:
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _find_latest(root: Path, pattern: str = "*.csv") -> Path | None:
    if not root.exists():
        return None
    matches = sorted(root.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    matches = [m for m in matches if ".gitkeep" not in str(m) and m.is_file()]
    return matches[0] if matches else None

def _read_csv_head(p: Path, n=10_000) -> list[dict]:
    if not p or not p.exists():
        return []
    try:
        with open(p, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))[:n]
    except Exception:
        return []

def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except Exception:
        return 0

def _sha256(p: Path) -> str:
    try:
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest()[:12]
    except Exception:
        return "?"

def _float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

# ── Step 1 — Detect Latest Run ────────────────────────────────────────────────
def step1_detect_run() -> dict:
    runs_dir = BASE_DIR / "logs" / "runs"
    result = {"run_id": "unknown", "run_ts": "unknown", "state": "unknown",
              "county": "unknown", "contest_id": "unknown",
              "run_status": "unknown", "elapsed": "unknown"}
    if not runs_dir.exists():
        return result
    run_logs = sorted(
        [p for p in runs_dir.iterdir() if p.is_dir() or (p.is_file() and p.suffix == ".log")],
        key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not run_logs:
        return result
    latest = run_logs[0]
    run_id = latest.name.replace(".log", "")
    result["run_id"] = run_id
    # Try pathway.json
    pw_files = sorted(runs_dir.glob(f"*pathway*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if pw_files:
        try:
            pw = json.loads(pw_files[0].read_text())
            result["state"]      = pw.get("state", "unknown")
            result["county"]     = pw.get("county", "unknown")
            result["contest_id"] = pw.get("contest_slug", "unknown")
            result["run_status"] = pw.get("run_status", "unknown")
            result["elapsed"]    = pw.get("total_elapsed_s", "unknown")
            result["run_ts"]     = pw.get("started", "unknown")
        except Exception:
            pass
    return result

# ── Step 2 — Detect Latest Prior Audit ────────────────────────────────────────
def step2_prior_audit() -> str:
    audit_dir = BASE_DIR / "reports" / "audit"
    if not audit_dir.exists():
        return "none"
    jsons = sorted(audit_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jsons[0].stem if jsons else "none"

# ── Step 3 — Directory Structure ─────────────────────────────────────────────
REQUIRED_DIRS = [
    "data", "votes",
    "derived/features", "derived/universes", "derived/campaign_targets",
    "derived/turfs", "derived/forecasts", "derived/simulation",
    "derived/ops", "derived/strategy_packs", "derived/diagnostics",
    "derived/precinct_models", "derived/maps",
    "logs", "needs", "config", "scripts",
]

def step3_dirs() -> dict:
    return {d: (BASE_DIR / d).exists() for d in REQUIRED_DIRS}

# ── Step 4 — Data Ingestion ───────────────────────────────────────────────────
def step4_ingestion() -> dict:
    votes_root = BASE_DIR / "votes"
    contests = []
    issues = []
    for contest_json in sorted(votes_root.rglob("contest.json"), key=lambda p: p.stat().st_mtime)[-5:]:
        try:
            meta = json.loads(contest_json.read_text())
        except Exception:
            meta = {}
        detail_xlsx = (contest_json.parent / "detail.xlsx").exists()
        contests.append({
            "path":            str(contest_json.relative_to(BASE_DIR)),
            "title":           meta.get("title", "unknown"),
            "choices":         meta.get("choices", []),
            "precinct_count":  meta.get("precinct_count", 0),
            "total_registered":meta.get("total_registered", 0),
            "total_ballots":   meta.get("total_ballots", 0),
            "detail_xlsx":     detail_xlsx,
        })
    return {"contests": contests, "issues": issues}

# ── Step 5 — Geography ────────────────────────────────────────────────────────
def step5_geography() -> dict:
    try:
        import geopandas
        geopandas_ok = True
    except ImportError:
        geopandas_ok = False

    geo_root = BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography" / "precinct_shapes"
    mprec_geojson = bool(_find_latest(geo_root / "MPREC_GeoJSON", "*.geojson"))
    srprec_geojson = bool(_find_latest(geo_root / "SRPREC_GeoJSON", "*.geojson"))
    boundary_idx_path = BASE_DIR / "data" / "CA" / "counties" / "Sonoma" / "geography" / "boundary_index" / "boundaries_index.csv"
    boundary_index = boundary_idx_path.exists()

    parsed_count = 0
    geometry_parsed = False
    if geopandas_ok and mprec_geojson:
        try:
            import geopandas as gpd
            geojson_path = _find_latest(geo_root / "MPREC_GeoJSON", "*.geojson")
            if geojson_path:
                gdf = gpd.read_file(geojson_path)
                parsed_count = len(gdf)
                geometry_parsed = True
        except Exception:
            pass

    return {
        "geopandas_installed": geopandas_ok,
        "mprec_geojson":  mprec_geojson,
        "srprec_geojson": srprec_geojson,
        "boundary_index": boundary_index,
        "geometry_parsed": geometry_parsed,
        "precinct_count_from_geometry": parsed_count,
    }

# ── Step 6 — Crosswalk Validation ────────────────────────────────────────────
CW_REGISTRY = {
    "SRPREC_TO_2020_BLK":      {"patterns": ["*SRPREC*BLK*", "*srprec*blk*", "*srprec*to*blk*"]},
    "RGPREC_TO_2020_BLK":      {"patterns": ["*RGPREC*BLK*", "*rgprec*blk*"]},
    "2020_BLK_TO_MPREC":       {"patterns": ["*BLK*MPREC*", "*blk*mprec*", "*blk_mprec*"]},
    "MPREC_to_SRPREC":         {"patterns": ["*MPREC*SRPREC*", "*mprec*srprec*"]},
    "SRPREC_to_CITY":          {"patterns": ["*SRPREC*CITY*", "*srprec*city*", "*cities*srprec*"]},
    "RG_to_RR_to_SR_to_SVPREC":{"patterns": ["*RG*SVPREC*", "*rg*svprec*", "*rg*to*sr*"]},
}

def step6_crosswalks() -> dict:
    results = {}
    search_root = BASE_DIR / "data"
    for name, spec in CW_REGISTRY.items():
        found = False
        found_path = None
        for pattern in spec["patterns"]:
            matches = [m for m in sorted(search_root.rglob(pattern))
                       if m.is_file() and ".gitkeep" not in str(m)]
            if matches:
                found = True
                found_path = str(matches[0].relative_to(BASE_DIR))
                break
        results[name] = {
            "status": "found" if found else "missing",
            "path":   found_path,
        }
    # SRPREC_to_CITY can be a fallback from cities_by_county_ca.json
    if results["SRPREC_to_CITY"]["status"] == "missing":
        if (BASE_DIR / "config" / "cities_by_county_ca.json").exists():
            results["SRPREC_to_CITY"]["status"] = "fallback"
            results["SRPREC_to_CITY"]["path"] = "config/cities_by_county_ca.json"
    return results

# ── Step 7 — Feature Engineering ─────────────────────────────────────────────
FEATURE_REQUIRED_COLS = ["canonical_precinct_id", "registered", "ballots_cast",
                          "turnout_pct", "support_pct"]

def step7_features() -> dict:
    feat_path = _find_latest(BASE_DIR / "derived" / "precinct_models", "*precinct_model*.csv")
    if not feat_path:
        feat_path = _find_latest(BASE_DIR / "derived" / "features", "*.csv")
    if not feat_path:
        return {"file_found": False, "row_count": 0, "missing_cols": FEATURE_REQUIRED_COLS, "violations": []}
    rows = _read_csv_head(feat_path)
    if not rows:
        return {"file_found": True, "row_count": 0, "missing_cols": FEATURE_REQUIRED_COLS,
                "violations": [], "path": str(feat_path.relative_to(BASE_DIR))}
    cols = set(rows[0].keys())
    missing = [c for c in FEATURE_REQUIRED_COLS if c not in cols]
    violations = []
    if "turnout_pct" in cols:
        bad = sum(1 for r in rows if not (0 <= _float(r.get("turnout_pct", 0)) <= 1))
        if bad: violations.append(f"turnout_pct out of [0,1]: {bad} rows")
    if "support_pct" in cols:
        bad = sum(1 for r in rows if not (0 <= _float(r.get("support_pct", 0.5)) <= 1))
        if bad: violations.append(f"support_pct out of [0,1]: {bad} rows")
    if "ballots_cast" in cols and "registered" in cols:
        bad = sum(1 for r in rows if _float(r.get("ballots_cast", 0)) > _float(r.get("registered", 999999)))
        if bad: violations.append(f"ballots_cast > registered: {bad} rows")
    return {
        "file_found": True,
        "row_count":  len(rows),
        "missing_cols": missing,
        "violations":   violations,
        "path": str(feat_path.relative_to(BASE_DIR)),
    }

# ── Step 8 — Universe Generation ─────────────────────────────────────────────
def step8_universes() -> dict:
    uni_path = _find_latest(BASE_DIR / "derived" / "universes", "*.csv")
    if not uni_path:
        return {"file_found": False, "row_count": 0, "universe_names": [], "missing_cols": []}
    rows = _read_csv_head(uni_path)
    cols = set(rows[0].keys()) if rows else set()
    req = ["canonical_precinct_id", "universe_name", "universe_reason"]
    missing = [c for c in req if c not in cols and c.replace("canonical_precinct_id", "precinct_id") not in cols]
    names = list({r.get("universe_name", "") for r in rows if r.get("universe_name")})
    return {
        "file_found": True,
        "row_count":  len(rows),
        "universe_names": names,
        "missing_cols":   missing,
        "path": str(uni_path.relative_to(BASE_DIR)),
    }

# ── Step 9 — Target Scoring ───────────────────────────────────────────────────
TARGET_REQUIRED_COLS = ["target_score", "persuasion_potential", "turnout_opportunity",
                         "tier", "walk_priority_rank", "confidence_level"]

def step9_targets() -> dict:
    p = _find_latest(BASE_DIR / "derived" / "campaign_targets", "*.csv")
    if not p:
        p = _find_latest(BASE_DIR / "derived" / "precinct_models", "*precinct_model*.csv")
    if not p:
        return {"file_found": False, "row_count": 0, "missing_cols": TARGET_REQUIRED_COLS, "tier_dist": {}}
    rows = _read_csv_head(p)
    cols = set(rows[0].keys()) if rows else set()
    missing = [c for c in TARGET_REQUIRED_COLS if c not in cols]
    tier_dist = {}
    for r in rows:
        t = r.get("tier", r.get("target_tier", "unknown"))
        tier_dist[t] = tier_dist.get(t, 0) + 1
    return {
        "file_found": True,
        "row_count":  len(rows),
        "missing_cols": missing,
        "tier_dist":    tier_dist,
        "path": str(p.relative_to(BASE_DIR)),
    }

# ── Step 10 — Turf Generation ─────────────────────────────────────────────────
def step10_turfs() -> dict:
    p = _find_latest(BASE_DIR / "derived" / "turfs", "*.csv")
    if not p:
        return {"file_found": False, "turf_count": 0, "missing_cols": []}
    rows = _read_csv_head(p)
    cols = set(rows[0].keys()) if rows else set()
    required = ["turf_id", "registered_total", "expected_contacts"]
    missing = [c for c in required if c not in cols]
    return {
        "file_found": True,
        "turf_count": len(rows),
        "missing_cols": missing,
        "path": str(p.relative_to(BASE_DIR)),
    }

# ── Step 11 — Deterministic Forecast ──────────────────────────────────────────
def step11_deterministic() -> dict:
    p = _find_latest(BASE_DIR / "derived" / "simulation", "*deterministic*.csv")
    if not p:
        return {"file_found": False, "row_count": 0, "missing_cols": []}
    rows = _read_csv_head(p)
    cols = set(rows[0].keys()) if rows else set()
    required = ["precinct_id", "votes_for", "votes_against", "margin", "turnout_pct", "support_pct"]
    alias_map = {"precinct_id": ["precinct_id", "canonical_precinct_id"],
                 "votes_for": ["votes_for", "expected_yes", "yes_votes"],
                 "votes_against": ["votes_against", "expected_no", "no_votes"],
                 "margin": ["margin", "expected_margin"],
                 "turnout_pct": ["turnout_pct", "expected_turnout"],
                 "support_pct": ["support_pct", "expected_support"]}
    missing = []
    for req_col, aliases in alias_map.items():
        if not any(a in cols for a in aliases):
            missing.append(req_col)
    return {
        "file_found": True,
        "row_count": len(rows),
        "missing_cols": missing,
        "path": str(p.relative_to(BASE_DIR)),
    }

# ── Step 12 — Monte Carlo Simulation ──────────────────────────────────────────
def step12_simulation() -> dict:
    p = _find_latest(BASE_DIR / "derived" / "simulation", "*simulation_results*.csv")
    if not p:
        return {"file_found": False, "row_count": 0, "scenarios": [], "missing_cols": []}
    rows = _read_csv_head(p)
    cols = set(rows[0].keys()) if rows else set()
    scenarios = list({r.get("scenario", "") for r in rows if r.get("scenario")})
    required = ["scenario", "iteration", "expected_votes_for", "margin", "win"]
    alias_map = {
        "expected_votes_for": ["expected_votes_for", "net_gain", "expected_yes"],
        "iteration": ["iteration", "sim_id"],
        "margin": ["margin", "net_gain"],
    }
    missing = []
    for req in required:
        if req not in cols:
            alts = alias_map.get(req, [req])
            if not any(a in cols for a in alts):
                missing.append(req)
    max_iter = max((_float(r.get("iteration", 0)) for r in rows), default=0)
    return {
        "file_found": True,
        "row_count":  len(rows),
        "scenarios":  scenarios,
        "missing_cols": missing,
        "max_iter":   int(max_iter),
        "path": str(p.relative_to(BASE_DIR)),
    }

# ── Step 13 — Scenario Summary ────────────────────────────────────────────────
def step13_scenario_summary() -> dict:
    p = _find_latest(BASE_DIR / "derived" / "simulation", "*scenario_summary*.csv")
    if not p:
        return {"file_found": False, "row_count": 0, "scenarios": [], "prob_violations": []}
    rows = _read_csv_head(p)
    cols = set(rows[0].keys()) if rows else set()
    required = ["scenario", "win_probability", "median_margin", "p10_margin", "p90_margin"]
    missing = [c for c in required if c not in cols]
    scenarios = [r.get("scenario", "") for r in rows]
    prob_violations = [r.get("scenario") for r in rows
                       if not 0 <= _float(r.get("win_probability", 0)) <= 1]
    return {
        "file_found": True,
        "row_count":  len(rows),
        "missing_cols": missing,
        "scenarios": scenarios,
        "prob_violations": prob_violations,
        "path": str(p.relative_to(BASE_DIR)),
    }

# ── Step 14 — Operations Planner ──────────────────────────────────────────────
def step14_ops() -> dict:
    ops_dir = BASE_DIR / "derived" / "ops"
    r_path = _find_latest(ops_dir, "*regions*.csv")
    fp_path = _find_latest(ops_dir, "*field_plan*.csv")
    r_rows = _read_csv_head(r_path) if r_path else []
    fp_rows = _read_csv_head(fp_path) if fp_path else []
    r_cols = set(r_rows[0].keys()) if r_rows else set()
    fp_cols = set(fp_rows[0].keys()) if fp_rows else set()
    r_req = ["region_id", "region_name", "precinct_count", "registered_total", "avg_target_score"]
    fp_req = ["region_id", "doors_to_knock", "expected_contacts", "volunteers_needed", "weeks_required"]
    return {
        "dir_exists":       ops_dir.exists(),
        "regions_found":    bool(r_path),
        "field_plan_found": bool(fp_path),
        "region_count":     len(r_rows),
        "field_plan_rows":  len(fp_rows),
        "regions_missing_cols":   [c for c in r_req  if c not in r_cols],
        "field_missing_cols":     [c for c in fp_req if c not in fp_cols],
        "regions_path":   str(r_path.relative_to(BASE_DIR))  if r_path  else None,
        "field_plan_path": str(fp_path.relative_to(BASE_DIR)) if fp_path else None,
    }

# ── Step 15 — Strategy Pack ───────────────────────────────────────────────────
STRATEGY_FILES = ["STRATEGY_META.json", "STRATEGY_SUMMARY.md", "TOP_TARGETS.csv",
                  "TOP_TURFS.csv", "FIELD_PLAN.csv", "SIMULATION_RESULTS.csv", "FIELD_PACE.csv"]

def step15_strategy_pack() -> dict:
    sp_root = BASE_DIR / "derived" / "strategy_packs"
    if not sp_root.exists():
        return {"exists": False, "packs_found": [], "latest_pack": None, "files": {}}
    all_packs = sorted(sp_root.rglob("STRATEGY_META.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    if not all_packs:
        return {"exists": True, "packs_found": [], "latest_pack": None, "files": {}}
    latest_dir = all_packs[0].parent
    files_status = {f: (latest_dir / f).exists() for f in STRATEGY_FILES}
    return {
        "exists": True,
        "packs_found": [str(p.parent.relative_to(BASE_DIR)) for p in all_packs[:5]],
        "latest_pack": str(latest_dir.relative_to(BASE_DIR)),
        "files": files_status,
    }

# ── Step 16 — Strategy Meta ───────────────────────────────────────────────────
STRATEGY_META_REQUIRED = [
    "contest_id", "run_id", "precinct_count", "turf_count", "region_count",
    "scenario_count", "win_probability", "recommended_strategy",
]

def step16_strategy_meta(sp: dict) -> dict:
    if not sp.get("latest_pack"):
        return {"file_found": False, "meta_missing": STRATEGY_META_REQUIRED, "meta_topline_missing": []}
    meta_path = BASE_DIR / sp["latest_pack"] / "STRATEGY_META.json"
    if not meta_path.exists():
        return {"file_found": False, "meta_missing": STRATEGY_META_REQUIRED, "meta_topline_missing": []}
    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        return {"file_found": True, "meta_missing": ["(parse error)"], "meta_topline_missing": []}

    topline = meta.get("topline_metrics", meta)
    all_keys = set(meta.keys()) | set(topline.keys())
    meta_missing = [k for k in STRATEGY_META_REQUIRED if k not in all_keys]
    topline_missing = [k for k in ["baseline_support", "baseline_turnout", "baseline_margin"]
                       if k not in all_keys]
    return {
        "file_found": True,
        "meta_missing": meta_missing,
        "meta_topline_missing": topline_missing,
        "meta_summary": {
            "contest_id":        meta.get("contest_id", "?"),
            "contest_mode":      meta.get("contest_mode", "?"),
            "derived_mode":      meta.get("derived_mode", "?"),
            "forecast_mode":     meta.get("forecast_mode", "?"),
            "precinct_count":    meta.get("precinct_count", topline.get("precinct_count", 0)),
            "scenario_count":    meta.get("scenario_count", 0),
            "win_probability":   meta.get("win_probability", topline.get("win_probability", "?")),
            "recommended_strategy": meta.get("recommended_strategy", topline.get("recommended_strategy", "?")),
        },
    }

# ── Step 17 — Strategy Decisions ─────────────────────────────────────────────
def step17_decisions(sp: dict) -> dict:
    if not sp.get("latest_pack"):
        return {k: False for k in ["top_targets_present", "field_plan_present",
                                    "simulation_results_present", "strategy_summary_present"]}
    pack_dir = BASE_DIR / sp["latest_pack"]
    return {
        "top_targets_present":        (pack_dir / "TOP_TARGETS.csv").exists(),
        "field_plan_present":         (pack_dir / "FIELD_PLAN.csv").exists(),
        "simulation_results_present": (pack_dir / "SIMULATION_RESULTS.csv").exists(),
        "strategy_summary_present":   (pack_dir / "STRATEGY_SUMMARY.md").exists(),
    }

# ── Step 18 — UI Integration ─────────────────────────────────────────────────
UI_CHECKS = {
    "strategy_generator_panel":  "strategy_generator",
    "contest_selector":          "contest_selector",
    "forecast_mode_toggle":      "forecast_mode",
    "deterministic_option":      "deterministic",
    "monte_carlo_option":        "monte_carlo",
    "both_option":               '"both"',
    "generate_button":           "generate",
    "download_buttons":          "download",
    "strategy_fn_import":        "run_strategy_generator",
    "completeness_badge":        "completeness",
}

def step18_ui() -> dict:
    app_path = BASE_DIR / "app" / "app.py"
    if not app_path.exists():
        return {"app_found": False, "checks": {k: False for k in UI_CHECKS}, "pass_count": 0, "total_checks": len(UI_CHECKS)}
    src = app_path.read_text(encoding="utf-8", errors="ignore").lower()
    checks = {name: keyword.lower() in src for name, keyword in UI_CHECKS.items()}
    return {
        "app_found": True,
        "checks": checks,
        "pass_count": sum(checks.values()),
        "total_checks": len(checks),
    }

# ── Step 19 — NEEDS System ───────────────────────────────────────────────────
NEEDS_KEYS = ["simulation_engine", "operations_planner", "strategy_generator"]

def step19_needs() -> dict:
    needs_path = BASE_DIR / "needs" / "needs.yaml"
    if not needs_path.exists():
        return {"file_found": False, "entries": [], "needs_status": []}
    data = _read_yaml(needs_path)
    entries = list(data.keys())
    status = []
    for key in NEEDS_KEYS:
        val = data.get(key)
        status.append({"key": key, "status": val.get("status") if isinstance(val, dict) else val})
    return {"file_found": True, "entries": entries, "needs_status": status}

# ── Step 20 — Static Code Analysis ───────────────────────────────────────────
CODE_PATTERNS = {
    "BARE_EXCEPT": re.compile(r"^\s*except\s*:", re.MULTILINE),
    "HARD_CODED_PATH": re.compile(r"['\"]C:\\\\Users|['\"]\/home\/\w+", re.MULTILINE),
    "TODO": re.compile(r"#\s*TODO", re.IGNORECASE | re.MULTILINE),
    "FIXME": re.compile(r"#\s*FIXME", re.IGNORECASE | re.MULTILINE),
}

def step20_code_analysis() -> list:
    issues = []
    py_files = [p for p in (BASE_DIR / "scripts").rglob("*.py")
                if ".gitkeep" not in str(p) and "__pycache__" not in str(p)]
    for pyf in py_files[:100]:
        try:
            src = pyf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pat in CODE_PATTERNS.items():
            severity = "high" if label == "HARD_CODED_PATH" else "medium" if label == "FIXME" else "low"
            for m in pat.finditer(src):
                line_no = src[:m.start()].count("\n") + 1
                issues.append({
                    "severity": severity,
                    "file":     str(pyf.relative_to(BASE_DIR)),
                    "line":     line_no,
                    "description": f"{label}: {m.group()[:80].strip()}",
                })
    return issues

# ── Step 21 — Repo Health ────────────────────────────────────────────────────
def step21_repo_health() -> dict:
    all_files   = list(BASE_DIR.rglob("*"))
    py_files    = [f for f in all_files if f.suffix == ".py" and f.is_file()]
    geo_files   = [f for f in all_files if f.suffix in (".geojson", ".gpkg", ".shp") and f.is_file()]
    vote_files  = [f for f in all_files if "detail.xlsx" in f.name and f.is_file()]
    derived_outs = [f for f in (BASE_DIR / "derived").rglob("*") if f.is_file() and ".gitkeep" not in str(f)] if (BASE_DIR / "derived").exists() else []
    sp_files    = [f for f in (BASE_DIR / "derived" / "strategy_packs").rglob("*") if f.is_file()] if (BASE_DIR / "derived" / "strategy_packs").exists() else []
    # Largest files (top 5, skip node_modules and .git)
    sized = sorted(
        [(f, f.stat().st_size) for f in (BASE_DIR.rglob("*"))
         if f.is_file() and ".git" not in str(f) and "node_modules" not in str(f)],
        key=lambda x: x[1], reverse=True
    )[:5]
    missing_configs = [c for c in ["strategy.yaml", "model_weights.yaml", "universe_rules.yaml"]
                       if not (BASE_DIR / "config" / c).exists()]
    return {
        "total_files":     len([f for f in all_files if f.is_file()]),
        "python_files":    len(py_files),
        "geo_files":       len(geo_files),
        "vote_files":      len(vote_files),
        "derived_outputs": len(derived_outs),
        "strategy_packs":  len(sp_files),
        "largest_files": [{"path": str(f.relative_to(BASE_DIR)), "bytes": s} for f, s in sized],
        "missing_configs": missing_configs,
    }

# ── Step 22 — Write JSON ──────────────────────────────────────────────────────
def write_json(result: dict) -> Path:
    out_dir = BASE_DIR / "reports" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{AUDIT_ID}.json"
    p.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return p

# ── Step 23 — Write Markdown ──────────────────────────────────────────────────
def write_markdown(result: dict) -> Path:
    r = result
    sp = r.get("strategy_pack", {})
    sm = r.get("strategy_meta", {})
    meta = sm.get("meta_summary", {})
    ui = r.get("ui", {})
    ops = r.get("ops", {})
    sim = r.get("simulation", {})
    det = r.get("deterministic", {})
    turfs = r.get("turfs", {})

    def sym(ok): return "✅" if ok else "❌"
    def warn(ok): return "✅" if ok else "⚠️"

    md = f"""# Post-Prompt-8.5 Full System Audit
**Audit ID:** `{AUDIT_ID}`  **Prior:** `{r.get("prior_audit_id", "none")}`
**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — **Status: {r.get("system_status", "?")}**

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Run ID | `{r.get("run_id", "?")}` |
| State / County | {r.get("state", "?")} / {r.get("county", "?")} |
| Precincts Modeled | {r.get("model_summary", {}).get("precinct_count", "?")} |
| Turfs Generated | {r.get("model_summary", {}).get("turf_count", "?")} |
| Regions | {r.get("model_summary", {}).get("region_count", "?")} |
| Scenarios Simulated | {r.get("model_summary", {}).get("scenario_count", "?")} |
| Strategy Packs | {r.get("model_summary", {}).get("strategy_packs", "?")} |
| Strategy `derived_mode` | **{meta.get("derived_mode", "?")}** |
| System Status | **{r.get("system_status", "?")}** |

---

## 2. Pipeline Health

| Step | Status |
|---|---|
| Data ingestion | {sym(bool(r.get("ingestion", {}).get("contests")))} |
| Geography loaded | {sym(r.get("geo", {}).get("mprec_geojson"))} |
| geopandas installed | {warn(r.get("geo", {}).get("geopandas_installed"))} |
| Crosswalks (4+ of 6) | {sym(sum(1 for v in r.get("crosswalks", {}).values() if v.get("status") in ("found", "fallback")) >= 4)} |
| Features (0 violations) | {sym(len(r.get("features", {}).get("violations", [])) == 0)} |
| Universes | {sym(r.get("universes", {}).get("file_found"))} |
| Targets | {sym(r.get("targets", {}).get("file_found"))} |
| Turfs | {sym(turfs.get("file_found"))} |
| Deterministic forecast | {sym(det.get("file_found"))} |
| Monte Carlo simulation | {sym(sim.get("file_found"))} |
| Operations planner | {sym(ops.get("regions_found") and ops.get("field_plan_found"))} |
| Strategy pack (full mode) | {sym(meta.get("derived_mode") == "full")} |
| UI (10/10 checks) | {sym(ui.get("pass_count") == 10)} |

---

## 3. Simulation Engine

| Metric | Value |
|---|---|
| Deterministic rows | {det.get("row_count", 0)} |
| Monte Carlo rows | {sim.get("row_count", 0)} |
| Scenarios | {", ".join(sim.get("scenarios", []))} |
| Max iteration | {sim.get("max_iter", 0)} |
| Simulation file size | {r.get("strategy_pack", {}).get("simulation_results_bytes", "n/a")} bytes |

---

## 4. Operations Planner

| Metric | Value |
|---|---|
| Regions found | {ops.get("region_count", 0)} |
| Field plan rows | {ops.get("field_plan_rows", 0)} |
| Regions missing cols | {ops.get("regions_missing_cols", [])} |
| Field plan missing cols | {ops.get("field_missing_cols", [])} |

---

## 5. Strategy Generator

| Metric | Value |
|---|---|
| `derived_mode` | **{meta.get("derived_mode", "?")}** |
| `forecast_mode` | {meta.get("forecast_mode", "?")} |
| `win_probability` | {meta.get("win_probability", "?")} |
| `recommended_strategy` | {str(meta.get("recommended_strategy", "?"))[:80]} |
| STRATEGY_META.json | {sym(sp.get("files", {}).get("STRATEGY_META.json"))} |
| STRATEGY_SUMMARY.md | {sym(sp.get("files", {}).get("STRATEGY_SUMMARY.md"))} |
| TOP_TARGETS.csv | {sym(sp.get("files", {}).get("TOP_TARGETS.csv"))} |
| FIELD_PLAN.csv | {sym(sp.get("files", {}).get("FIELD_PLAN.csv"))} |
| SIMULATION_RESULTS.csv | {sym(sp.get("files", {}).get("SIMULATION_RESULTS.csv"))} |
| TOP_TURFS.csv | {sym(sp.get("files", {}).get("TOP_TURFS.csv"))} |

---

## 6. UI Integration

| Check | Status |
|---|---|
""" + "\n".join(
        f"| {k.replace('_', ' ').title()} | {sym(v)} |"
        for k, v in ui.get("checks", {}).items()
    ) + f"""

**UI Pass Rate:** {ui.get("pass_count", 0)}/{ui.get("total_checks", 0)}

---

## 7. NEEDS System

| Key | Status |
|---|---|
""" + "\n".join(
        f"| `{s['key']}` | {s['status'] or '(no entry)'} |"
        for s in r.get("needs_status", [])
    ) + """

---

## 8. Repository Health

| Metric | Value |
|---|---|
""" + "\n".join(
        f"| {k.replace('_', ' ').title()} | {v} |"
        for k, v in r.get("repo_metrics", {}).items()
        if not isinstance(v, list)
    ) + """

---

## 9. Issues Detected

| Severity | File | Line | Description |
|---|---|---|---|
""" + "\n".join(
        f"| {i.get('severity')} | `{i.get('file')}` | {i.get('line')} | {i.get('description', '')[:70]} |"
        for i in r.get("issues", [])[:30]
    ) + """

---

## 10. Recommended Fixes

""" + "\n".join(f"- {rec}" for rec in r.get("recommendations", []))

    out_dir = BASE_DIR / "reports" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{AUDIT_ID}.md"
    p.write_text(md, encoding="utf-8")
    return p

# ── Step 24 — Export Bundle ───────────────────────────────────────────────────
def write_bundle(json_path: Path, md_path: Path, run_id: str) -> Path:
    bundle_dir = BASE_DIR / "reports" / "export" / f"{AUDIT_ID}__prompt85_audit_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(json_path, bundle_dir / "audit_report.json")
    shutil.copy2(md_path,   bundle_dir / "audit_report.md")

    # Collect companion files
    runs_dir = BASE_DIR / "logs" / "runs"
    for log_glob in [f"*{run_id}*run.log", "*__run.log", "*.log"]:
        matches = sorted(runs_dir.glob(log_glob) if runs_dir.exists() else [], key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            shutil.copy2(matches[0], bundle_dir / "run.log")
            break

    for pw_glob in [f"*{run_id}*pathway*", "*pathway*.json"]:
        matches = sorted(runs_dir.glob(pw_glob) if runs_dir.exists() else [], key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            shutil.copy2(matches[0], bundle_dir / "pathway.json")
            break

    needs_path = BASE_DIR / "needs" / "needs.yaml"
    if needs_path.exists():
        shutil.copy2(needs_path, bundle_dir / "needs.yaml")

    # Latest run QA
    qa_dir = BASE_DIR / "reports" / "qa"
    if qa_dir.exists():
        mds = sorted(qa_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if mds: shutil.copy2(mds[0], bundle_dir / "qa.md")

    # Validation report
    val_dir = BASE_DIR / "reports" / "validation"
    if val_dir.exists():
        mds = sorted(val_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if mds: shutil.copy2(mds[0], bundle_dir / "validation.md")

    # Strategy meta
    sp_root = BASE_DIR / "derived" / "strategy_packs"
    metas = sorted(sp_root.rglob("STRATEGY_META.json"), key=lambda p: p.stat().st_mtime, reverse=True) if sp_root.exists() else []
    if metas: shutil.copy2(metas[0], bundle_dir / "strategy_meta.json")

    return bundle_dir

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"  CAMPAIGN IN A BOX — POST-PROMPT-8.5 FULL SYSTEM AUDIT")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    run_info    = step1_detect_run()
    prior_audit = step2_prior_audit()
    dirs        = step3_dirs()
    ingestion   = step4_ingestion()
    geo         = step5_geography()
    crosswalks  = step6_crosswalks()
    features    = step7_features()
    universes   = step8_universes()
    targets     = step9_targets()
    turfs       = step10_turfs()
    deterministic = step11_deterministic()
    simulation  = step12_simulation()
    scen_summary = step13_scenario_summary()
    ops         = step14_ops()
    sp          = step15_strategy_pack()
    sp_meta     = step16_strategy_meta(sp)
    sp_decisions = step17_decisions(sp)
    ui          = step18_ui()
    needs       = step19_needs()
    code_issues = step20_code_analysis()
    repo        = step21_repo_health()

    # ── Derive status ─────────────────────────────────────────────────────────
    constraint_violations = features.get("violations", [])
    derived_mode = sp_meta.get("meta_summary", {}).get("derived_mode", "unknown")

    has_error = (
        not dirs.get("derived/simulation") or
        not sp.get("exists") or
        not ops.get("regions_found")
    )
    has_warn = (
        not geo.get("geopandas_installed") or
        len(constraint_violations) > 0 or
        derived_mode not in ("full", "partial") or
        sum(1 for v in crosswalks.values() if v.get("status") in ("found", "fallback")) < 4
    )
    system_status = "ERROR" if has_error else ("WARN" if has_warn else "OK")

    # ── Simulation size ───────────────────────────────────────────────────────
    sim_bytes = 0
    if sp.get("latest_pack"):
        p = BASE_DIR / sp["latest_pack"] / "SIMULATION_RESULTS.csv"
        if p.exists():
            sim_bytes = p.stat().st_size

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = []
    if not geo.get("geopandas_installed"):
        recs.append("geopandas not installed — run `pip install geopandas`.")
    cw_missing = [k for k, v in crosswalks.items() if v.get("status") == "missing"]
    if cw_missing:
        recs.append(f"Missing crosswalks: {cw_missing}")
    if constraint_violations:
        recs.append(f"Constraint violations in features: {constraint_violations}")
    if derived_mode not in ("full", "partial"):
        recs.append(f"Strategy pack in `{derived_mode}` mode — check inputs_missing in STRATEGY_META.json")
    bare_excepts_new = [i for i in code_issues if "BARE_EXCEPT" in i["description"]
                        and "audit_post_prompt" not in i["file"]]
    if bare_excepts_new:
        recs.append(f"{len(bare_excepts_new)} BARE_EXCEPT(s) in production code — add specific exception types")

    # ── Compile result ────────────────────────────────────────────────────────
    result = {
        "system_status": system_status,
        "audit_id":      AUDIT_ID,
        "prior_audit_id": prior_audit,
        "timestamp":     datetime.datetime.now().isoformat(),
        "run_id":        run_info["run_id"],
        "run_ts":        run_info["run_ts"],
        "state":         run_info["state"],
        "county":        run_info["county"],
        "contest_id":    run_info["contest_id"],
        "run_status":    run_info["run_status"],
        "elapsed":       run_info["elapsed"],
        "dirs":          dirs,
        "ingestion":     ingestion,
        "geo":           geo,
        "crosswalks":    crosswalks,
        "features":      features,
        "universes":     universes,
        "targets":       targets,
        "turfs":         turfs,
        "deterministic": deterministic,
        "simulation":    simulation,
        "scenario_summary": scen_summary,
        "ops":           ops,
        "strategy_pack": {**sp, "simulation_results_bytes": sim_bytes,
                          "decision_checks": sp_decisions},
        "strategy_meta": sp_meta,
        "ui":            ui,
        "needs_detail":  needs,
        "model_summary": {
            "precinct_count": features.get("row_count", 0),
            "turf_count":     turfs.get("turf_count", 0),
            "region_count":   ops.get("region_count", 0),
            "scenario_count": len(simulation.get("scenarios", [])),
            "strategy_packs": len(sp.get("packs_found", [])),
        },
        "constraint_violations": [{"category": "features", "description": v} for v in constraint_violations],
        "needs_status":  needs.get("needs_status", []),
        "issues":        [i for i in code_issues if "audit_post_prompt" not in i.get("file", "")][:50],
        "recommendations": recs,
        "repo_metrics":  repo,
    }

    # Write reports
    json_path = write_json(result)
    md_path   = write_markdown(result)
    bundle    = write_bundle(json_path, md_path, run_info["run_id"])

    print(f"\n  JSON   -> {json_path.relative_to(BASE_DIR)}")
    print(f"  MD     -> {md_path.relative_to(BASE_DIR)}")
    print(f"  Bundle -> {bundle.relative_to(BASE_DIR)}")
    print("=" * 60)
    print("\nPROMPT-8.5 SYSTEM AUDIT COMPLETE")
    print("=" * 60)
    print(f"Run ID              : {run_info['run_id']}")
    print(f"Audit ID            : {AUDIT_ID}")
    print(f"System Status       : {system_status}")
    print()
    print(f"Precincts Modeled   : {result['model_summary']['precinct_count']}")
    print(f"Turfs Generated     : {result['model_summary']['turf_count']}")
    print(f"Regions Generated   : {result['model_summary']['region_count']}")
    print(f"Scenarios Simulated : {result['model_summary']['scenario_count']}")
    print(f"Strategy Packs      : {result['model_summary']['strategy_packs']}")
    print(f"Strategy Mode       : {derived_mode}")
    print()
    print(f"Crosswalks Found    : {sum(1 for v in crosswalks.values() if v.get('status') in ('found','fallback'))}/6")
    print(f"Constraint Violations: {len(constraint_violations)}")
    print(f"UI Checks Passed    : {ui.get('pass_count', 0)}/{ui.get('total_checks', 0)}")
    print()
    print(f"Audit Bundle:")
    print(f"  {bundle}")
    print("=" * 60)


if __name__ == "__main__":
    main()
