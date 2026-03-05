"""
scripts/tools/audit_post_prompt8.py

Campaign In A Box — Post-Prompt-8 Full System Audit (25 steps)

Produces:
  reports/audit/<AUDIT_ID>__post_prompt8_full_audit.json
  reports/audit/<AUDIT_ID>__post_prompt8_full_audit.md
  reports/export/<AUDIT_ID>__prompt8_audit_bundle/

Does NOT modify any code or pipeline data.
"""
from __future__ import annotations

import ast
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent.parent.parent

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

NOW = datetime.datetime.now()
AUDIT_ID = NOW.strftime("%Y-%m-%d__%H%M%S__post_prompt8_full_audit")

# ── helpers ──────────────────────────────────────────────────────────────────
def _newest(root: Path, pattern: str) -> Path | None:
    found = sorted(root.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    found = [f for f in found if ".gitkeep" not in str(f) and f.is_file()]
    return found[0] if found else None

def _csv(path: Path) -> "pd.DataFrame":
    if not PANDAS_OK or not path or not path.exists():
        return None        # type: ignore
    try:
        import pandas as pd
        return pd.read_csv(path)
    except Exception:
        return None        # type: ignore

def _cols(df) -> list:
    if df is None:
        return []
    return list(df.columns)

def _size(p: Path) -> int:
    try: return p.stat().st_size
    except: return 0

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Latest pipeline run
# ═══════════════════════════════════════════════════════════════════════════════
def step1_latest_run() -> dict:
    runs_dir = BASE / "logs" / "runs"
    run_id, run_ts, state, county, contest_id, run_status, elapsed = (
        "unknown", "unknown", "CA", "Sonoma", "unknown", "unknown", "unknown"
    )
    if runs_dir.exists():
        run_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime, reverse=True
        )
        if run_dirs:
            rd = run_dirs[0]
            run_id = rd.name
            # Try run.log
            log = rd / "run.log"
            if log.exists():
                txt = log.read_text(errors="replace")
                m = re.search(r"state[:=\s]+([A-Z]{2})", txt, re.I)
                if m: state = m.group(1)
                m = re.search(r"county[:=\s]+([^\n\r,]+)", txt, re.I)
                if m: county = m.group(1).strip()
                m = re.search(r"contest[:=\s]+([^\n\r,]+)", txt, re.I)
                if m: contest_id = m.group(1).strip()
                m = re.search(r"status[:=\s]+([^\n\r,]+)", txt, re.I)
                if m: run_status = m.group(1).strip()
                m = re.search(r"elapsed[:=\s]+([^\n\r,]+)", txt, re.I)
                if m: elapsed = m.group(1).strip()
            # Try pathway.json
            pj = rd / "pathway.json"
            if pj.exists():
                try:
                    pw = json.loads(pj.read_text())
                    state    = pw.get("state", state)
                    county   = pw.get("county", county)
                    contest_id = pw.get("contest_id", contest_id)
                    run_status  = pw.get("status", run_status)
                    elapsed     = str(pw.get("total_elapsed", elapsed))
                except Exception:
                    pass
            run_ts = rd.name.split("__")[0] if "__" in rd.name else "unknown"
    return dict(run_id=run_id, run_ts=run_ts, state=state, county=county,
                contest_id=contest_id, run_status=run_status, elapsed=elapsed)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Prior audit
# ═══════════════════════════════════════════════════════════════════════════════
def step2_prior_audit() -> str:
    audit_dir = BASE / "reports" / "audit"
    if not audit_dir.exists():
        return "none"
    audits = sorted(
        [f.name for f in audit_dir.glob("*.json")],
        reverse=True
    )
    # Skip prompt8 (current), return previous
    for a in audits:
        if "post_prompt8" not in a:
            return a.replace(".json", "")
    return audits[0].replace(".json", "") if audits else "none"


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Directory structure
# ═══════════════════════════════════════════════════════════════════════════════
REQUIRED_DIRS = [
    "data", "votes",
    "derived/features", "derived/universes", "derived/campaign_targets",
    "derived/turfs", "derived/forecasts",
    "derived/simulation", "derived/ops", "derived/strategy_packs",
    "derived/diagnostics",
    "logs", "needs", "config", "scripts",
]

def step3_dirs() -> dict:
    return {d: (BASE / d).exists() for d in REQUIRED_DIRS}


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Ingestion
# ═══════════════════════════════════════════════════════════════════════════════
def step4_ingestion() -> dict:
    contests = []
    issues = []
    for cj in (BASE / "votes").rglob("contest.json") if (BASE / "votes").exists() else []:
        try:
            c = json.loads(cj.read_text())
            xlsx = (cj.parent / "detail.xlsx").exists() or (cj.parent / "detail.csv").exists()
            contests.append({
                "path": str(cj.relative_to(BASE)),
                "title": c.get("title", c.get("name", c.get("contest_name", ""))),
                "choices": c.get("choices", []),
                "precinct_count": len(c.get("results", {}).get("precincts", c.get("precincts", []))),
                "total_registered": c.get("total_registered", 0),
                "total_ballots":    c.get("total_ballots", 0),
                "detail_xlsx": xlsx,
            })
        except Exception as e:
            issues.append(str(e))
    return dict(contests=contests, issues=issues)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Geography
# ═══════════════════════════════════════════════════════════════════════════════
def step5_geo() -> dict:
    try:
        import geopandas  # noqa
        geopandas_installed = True
    except ImportError:
        geopandas_installed = False
    mprec = bool(_newest(BASE / "data", "*mprec*.geojson"))
    srprec = bool(_newest(BASE / "data", "*srprec*.geojson"))
    bidx   = bool(_newest(BASE / "data", "boundary_index.csv"))
    geom_parsed = False
    if geopandas_installed and mprec:
        try:
            import geopandas as gpd
            f = _newest(BASE / "data", "*mprec*.geojson")
            if f:
                gdf = gpd.read_file(f)
                geom_parsed = not gdf.empty
        except Exception:
            pass
    return dict(
        geopandas_installed=geopandas_installed,
        mprec_geojson=mprec, srprec_geojson=srprec,
        boundary_index=bidx, geometry_parsed=geom_parsed,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Crosswalks
# ═══════════════════════════════════════════════════════════════════════════════
CROSSWALK_NAMES = [
    "SRPREC_TO_2020_BLK", "RGPREC_TO_2020_BLK", "2020_BLK_TO_MPREC",
    "MPREC_to_SRPREC", "SRPREC_to_CITY", "RG_to_RR_to_SR_to_SVPREC",
]

def step6_crosswalks() -> dict:
    cw = {}
    geo_root = BASE / "data"
    for name in CROSSWALK_NAMES:
        found = _newest(geo_root, f"*{name}*") or _newest(geo_root, f"*{name.lower()}*")
        cw[name] = "found" if found else "missing"
    return cw


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Feature engineering
# ═══════════════════════════════════════════════════════════════════════════════
FEATURE_REQUIRED = ["canonical_precinct_id", "registered", "ballots_cast", "turnout_pct", "support_pct"]

def step7_features() -> dict:
    f = (_newest(BASE / "derived" / "features", "*.csv") or
         _newest(BASE / "derived" / "precinct_models", "*precinct_model*.csv"))
    df = _csv(f)
    if df is None:
        return dict(file_found=False, row_count=0, missing_cols=FEATURE_REQUIRED, violations=[], path=None)
    missing = [c for c in FEATURE_REQUIRED if c not in df.columns]
    violations = []
    if PANDAS_OK and df is not None:
        import pandas as pd
        import numpy as np
        for col, lo, hi in [("turnout_pct", 0, 1), ("support_pct", 0, 1)]:
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                bad = vals[(vals < lo) | (vals > hi)]
                if not bad.empty:
                    violations.append(f"{col}: {len(bad)} values outside [{lo},{hi}]")
        if "ballots_cast" in df.columns and "registered" in df.columns:
            bc = pd.to_numeric(df["ballots_cast"], errors="coerce")
            rg = pd.to_numeric(df["registered"], errors="coerce")
            over = (bc > rg).sum()
            if over > 0:
                violations.append(f"ballots_cast > registered: {over} rows")
    return dict(file_found=True, row_count=len(df), missing_cols=missing,
                violations=violations, path=str(f.relative_to(BASE)))


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Universe generation
# ═══════════════════════════════════════════════════════════════════════════════
def step8_universes() -> dict:
    f = _newest(BASE / "derived" / "universes", "*.csv")
    df = _csv(f)
    if df is None:
        return dict(file_found=False, row_count=0, universe_names=[], missing_cols=[])
    req = ["precinct_id", "universe_name", "universe_reason"]
    missing = [c for c in req if c not in df.columns]
    names = list(df["universe_name"].dropna().unique()) if "universe_name" in df.columns else []
    return dict(file_found=True, row_count=len(df), universe_names=names, missing_cols=missing)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Target scoring
# ═══════════════════════════════════════════════════════════════════════════════
TARGET_REQUIRED = ["target_score", "persuasion_potential", "turnout_opportunity",
                   "tier", "walk_priority_rank", "confidence_level"]

def step9_targets() -> dict:
    f = _newest(BASE / "derived" / "campaign_targets", "*.csv")
    df = _csv(f)
    if df is None:
        return dict(file_found=False, row_count=0, missing_cols=TARGET_REQUIRED, tier_dist={})
    missing = [c for c in TARGET_REQUIRED if c not in df.columns]
    tier_dist = {}
    if "tier" in df.columns:
        tier_dist = df["tier"].value_counts().to_dict()
    return dict(file_found=True, row_count=len(df), missing_cols=missing, tier_dist=tier_dist)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 10 — Turf generation
# ═══════════════════════════════════════════════════════════════════════════════
def step10_turfs() -> dict:
    f = _newest(BASE / "derived" / "turfs", "*.csv")
    df = _csv(f)
    if df is None:
        return dict(file_found=False, turf_count=0, missing_cols=[])
    req = ["turf_id", "precinct_ids", "registered_total", "expected_contacts"]
    # Also accept sum_registered instead of registered_total
    actual_cols = list(df.columns)
    missing = [c for c in req if c not in actual_cols and c.replace("registered_total","sum_registered") not in actual_cols]
    missing = [c for c in req if c not in actual_cols]
    return dict(file_found=True, turf_count=len(df), missing_cols=missing)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 11 — Deterministic forecast
# ═══════════════════════════════════════════════════════════════════════════════
DET_REQUIRED = ["precinct_id", "votes_for", "votes_against", "margin", "turnout_pct", "support_pct"]

def step11_deterministic() -> dict:
    f = _newest(BASE / "derived" / "simulation", "*deterministic_forecast*.csv")
    df = _csv(f)
    if df is None:
        return dict(file_found=False, row_count=0, missing_cols=DET_REQUIRED, path=None)
    missing = [c for c in DET_REQUIRED if c not in df.columns]
    return dict(file_found=True, row_count=len(df), missing_cols=missing,
                path=str(f.relative_to(BASE)))


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 12 — Monte Carlo simulation
# ═══════════════════════════════════════════════════════════════════════════════
SIM_REQUIRED = ["scenario", "iteration", "expected_votes_for", "expected_votes_against", "margin", "win"]

def step12_montecarlo() -> dict:
    f = _newest(BASE / "derived" / "simulation", "*simulation_results*.csv")
    df = _csv(f)
    if df is None:
        return dict(file_found=False, row_count=0, scenarios=[], missing_cols=SIM_REQUIRED, max_iter=0)
    missing = [c for c in SIM_REQUIRED if c not in df.columns]
    scenarios = list(df["scenario"].dropna().unique()) if "scenario" in df.columns else []
    max_iter  = int(df["iteration"].max()) if "iteration" in df.columns else 0
    return dict(file_found=True, row_count=len(df), scenarios=scenarios,
                missing_cols=missing, max_iter=max_iter,
                path=str(f.relative_to(BASE)))


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 13 — Scenario summary
# ═══════════════════════════════════════════════════════════════════════════════
SUMM_REQUIRED = ["scenario", "win_probability", "median_margin", "p10_margin", "p90_margin", "avg_turnout"]

def step13_scenario_summary() -> dict:
    f = _newest(BASE / "derived" / "simulation", "*scenario_summary*.csv")
    df = _csv(f)
    if df is None:
        return dict(file_found=False, row_count=0, missing_cols=SUMM_REQUIRED, prob_violations=[])
    missing = [c for c in SUMM_REQUIRED if c not in df.columns]
    prob_v = []
    if PANDAS_OK and "win_probability" in (df.columns if df is not None else []):
        import pandas as pd
        wp = pd.to_numeric(df["win_probability"], errors="coerce").dropna()
        bad = wp[(wp < 0) | (wp > 1)]
        if not bad.empty:
            prob_v.append(f"win_probability out of [0,1]: {list(bad)}")
    scenarios = list(df["scenario"].dropna().unique()) if "scenario" in df.columns else []
    return dict(file_found=True, row_count=len(df), missing_cols=missing,
                scenarios=scenarios, prob_violations=prob_v,
                path=str(f.relative_to(BASE)))


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 14 — Operations planner
# ═══════════════════════════════════════════════════════════════════════════════
def step14_ops() -> dict:
    ops_dir = BASE / "derived" / "ops"
    regions_f   = _newest(ops_dir, "*regions*.csv")
    field_f     = _newest(ops_dir, "*field_plan*.csv")
    regions_df  = _csv(regions_f)
    field_df    = _csv(field_f)

    REG_COLS  = ["region_id", "region_name", "precinct_count", "registered_total", "avg_target_score"]
    PLAN_COLS = ["region_id", "doors_to_knock", "expected_contacts", "volunteers_needed", "weeks_required"]

    return dict(
        dir_exists=ops_dir.exists(),
        regions_found=regions_f is not None,
        field_plan_found=field_f is not None,
        region_count=len(regions_df) if regions_df is not None else 0,
        field_plan_rows=len(field_df) if field_df is not None else 0,
        regions_missing_cols=[c for c in REG_COLS  if regions_df is not None and c not in regions_df.columns],
        field_missing_cols  =[c for c in PLAN_COLS if field_df   is not None and c not in field_df.columns],
        regions_path=str(regions_f.relative_to(BASE)) if regions_f else None,
        field_plan_path=str(field_f.relative_to(BASE)) if field_f else None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 15+16+17 — Strategy pack
# ═══════════════════════════════════════════════════════════════════════════════
PACK_FILES = ["STRATEGY_META.json", "STRATEGY_SUMMARY.md", "TOP_TARGETS.csv",
              "FIELD_PLAN.csv", "SIMULATION_RESULTS.csv"]
META_FIELDS = ["contest_id", "run_id", "model_summary", "topline_metrics",
               "recommended_strategy", "forecast_mode"]
META_TOPLINE = ["baseline_support", "baseline_turnout", "baseline_margin",
                "win_probability", "win_number"]

def step15_to_17_strategy(run_id: str) -> dict:
    sp_root = BASE / "derived" / "strategy_packs"
    packs = sorted(sp_root.rglob("STRATEGY_META.json"), key=lambda p: p.stat().st_mtime, reverse=True) \
        if sp_root.exists() else []

    if not packs:
        return dict(exists=False, packs_found=[], files={}, meta_missing=META_FIELDS,
                    meta_topline_missing=META_TOPLINE, decision_checks={})

    latest_meta_path = packs[0]
    pack_dir = latest_meta_path.parent

    # File presence
    files = {f: (pack_dir / f).exists() for f in PACK_FILES}
    # Also check TOP_TURFS.csv separately (may be empty but present)
    files["TOP_TURFS.csv"] = (pack_dir / "TOP_TURFS.csv").exists()
    files["FIELD_PACE.csv"] = (pack_dir / "FIELD_PACE.csv").exists()

    # Meta validation
    meta_missing = []
    meta_topline_missing = []
    meta = {}
    try:
        meta = json.loads(latest_meta_path.read_text())
        meta_missing = [k for k in META_FIELDS if k not in meta]
        topline = meta.get("topline_metrics", {})
        meta_topline_missing = [k for k in META_TOPLINE if k not in topline]
    except Exception:
        meta_missing = META_FIELDS

    # Decision checks (step 17)
    decision_checks = {
        "has_recommended_strategy": bool(meta.get("recommended_strategy")),
        "has_win_probability":      meta.get("topline_metrics", {}).get("win_probability") is not None,
        "has_precinct_count":       bool(meta.get("model_summary", {}).get("precinct_count")),
        "has_scenario_count":       bool(meta.get("model_summary", {}).get("scenario_count")),
        "has_forecast_mode":        "forecast_mode" in meta,
        "top_targets_present":      (pack_dir / "TOP_TARGETS.csv").exists(),
        "field_plan_present":       (pack_dir / "FIELD_PLAN.csv").exists(),
        "simulation_results_present": (pack_dir / "SIMULATION_RESULTS.csv").exists(),
        "strategy_summary_present": (pack_dir / "STRATEGY_SUMMARY.md").exists(),
    }

    sim_size = _size(pack_dir / "SIMULATION_RESULTS.csv")

    return dict(
        exists=True,
        packs_found=[str(p.parent.relative_to(BASE)) for p in packs[:5]],
        latest_pack=str(pack_dir.relative_to(BASE)),
        files=files,
        meta_missing=meta_missing,
        meta_topline_missing=meta_topline_missing,
        meta_summary={
            "contest_id":    meta.get("contest_id"),
            "contest_mode":  meta.get("contest_mode"),
            "derived_mode":  meta.get("derived_mode"),
            "forecast_mode": meta.get("forecast_mode"),
            "precinct_count":meta.get("model_summary", {}).get("precinct_count"),
            "turf_count":    meta.get("model_summary", {}).get("turf_count"),
            "region_count":  meta.get("model_summary", {}).get("region_count"),
            "scenario_count":meta.get("model_summary", {}).get("scenario_count"),
            "win_probability":meta.get("topline_metrics", {}).get("win_probability"),
            "recommended_strategy": meta.get("recommended_strategy"),
        },
        simulation_results_bytes=sim_size,
        decision_checks=decision_checks,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 18 — UI integration
# ═══════════════════════════════════════════════════════════════════════════════
UI_CHECKS = {
    "strategy_generator_panel":  r"Strategy Generator",
    "contest_selector":          r"sg_contest|contest.*select",
    "forecast_mode_toggle":      r"sg_forecast_mode|Forecast Mode",
    "deterministic_option":      r"deterministic",
    "monte_carlo_option":        r"monte_carlo",
    "both_option":               r'"both"',
    "generate_button":           r"Generate Strategy Pack",
    "download_buttons":          r"st\.download_button",
    "strategy_fn_import":        r"run_strategy_generator",
    "completeness_badge":        r"completeness|derived_mode",
}

def step18_ui() -> dict:
    app_path = BASE / "app" / "app.py"
    checks = {}
    if not app_path.exists():
        return dict(app_found=False, checks={}, pass_count=0, total_checks=len(UI_CHECKS))
    try:
        src = app_path.read_text(errors="replace")
        for key, pattern in UI_CHECKS.items():
            checks[key] = bool(re.search(pattern, src, re.I))
    except Exception:
        checks = {k: False for k in UI_CHECKS}
    return dict(
        app_found=True, checks=checks,
        pass_count=sum(1 for v in checks.values() if v),
        total_checks=len(UI_CHECKS),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 19 — NEEDS system
# ═══════════════════════════════════════════════════════════════════════════════
NEEDS_KEYS = ["simulation_engine", "operations_planner", "strategy_generator"]

def step19_needs() -> dict:
    needs_path = BASE / "needs" / "needs.yaml"
    if not needs_path.exists():
        return dict(file_found=False, entries=[], needs_status=[])
    try:
        data = yaml.safe_load(needs_path.read_text()) or {}
    except Exception:
        return dict(file_found=True, entries=[], parse_error=True, needs_status=[])

    statuses = []
    for key in NEEDS_KEYS:
        entry = data.get(key, {})
        if isinstance(entry, dict):
            # Nested by contest_id
            first_val = next(iter(entry.values()), {}) if entry else {}
            statuses.append({"key": key, "status": first_val.get("status") if isinstance(first_val, dict) else first_val})
        else:
            statuses.append({"key": key, "status": entry})
    return dict(file_found=True, entries=list(data.keys()), needs_status=statuses)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 20 — Static code analysis
# ═══════════════════════════════════════════════════════════════════════════════
def step20_code_analysis() -> list:
    issues = []
    scripts_dir = BASE / "scripts"
    if not scripts_dir.exists():
        return issues
    for pyf in scripts_dir.rglob("*.py"):
        try:
            src = pyf.read_text(errors="replace")
            lines = src.splitlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # bare except
                if re.match(r"except\s*:", stripped):
                    issues.append(dict(severity="low", file=str(pyf.relative_to(BASE)),
                                       line=i, description=f"BARE_EXCEPT: {stripped}"))
                # hard-coded absolute paths (Windows)
                if re.search(r'["\']C:\\\\', line) or re.search(r'["\']C:/', line):
                    issues.append(dict(severity="low", file=str(pyf.relative_to(BASE)),
                                       line=i, description="HARD_CODED_PATH"))
                # TODO
                if "TODO" in line or "FIXME" in line or "HACK" in line:
                    issues.append(dict(severity="info", file=str(pyf.relative_to(BASE)),
                                       line=i, description=f"MARKER: {stripped[:80]}"))
        except Exception:
            pass
    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 21 — Repository health
# ═══════════════════════════════════════════════════════════════════════════════
def step21_repo_health() -> dict:
    total = py = geo = vote = derived = sp = 0
    largest = []
    for root, dirs, files in os.walk(BASE):
        # Skip hidden/venv
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".venv", "venv")]
        for fn in files:
            p = Path(root) / fn
            total += 1
            if fn.endswith(".py"): py += 1
            if fn.endswith((".geojson", ".shp", ".gpkg")): geo += 1
            if fn in ("contest.json", "detail.xlsx", "detail.csv"): vote += 1
            rp = str(p.relative_to(BASE))
            if rp.startswith("derived"): derived += 1
            if "strategy_packs" in rp: sp += 1
            try:
                sz = p.stat().st_size
                largest.append(dict(path=rp, bytes=sz))
            except: pass
    largest.sort(key=lambda x: x["bytes"], reverse=True)

    # Missing configs
    missing_configs = [c for c in ["field_ops.yaml", "strategy.yaml"]
                       if not (BASE / "config" / c).exists()]

    return dict(
        total_files=total, python_files=py, geo_files=geo,
        vote_files=vote, derived_outputs=derived, strategy_packs=sp,
        largest_files=largest[:5], missing_configs=missing_configs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 22+23+24 — Write reports
# ═══════════════════════════════════════════════════════════════════════════════
def write_reports(data: dict) -> tuple[Path, Path, Path]:
    (BASE / "reports" / "audit").mkdir(parents=True, exist_ok=True)
    base_name = f"{AUDIT_ID}"
    json_path = BASE / "reports" / "audit" / f"{base_name}.json"
    md_path   = BASE / "reports" / "audit" / f"{base_name}.md"
    exp_dir   = BASE / "reports" / "export" / f"{base_name}__prompt8_audit_bundle"
    exp_dir.mkdir(parents=True, exist_ok=True)

    # ── JSON ──────────────────────────────────────────────────────────────────
    json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # ── Markdown ──────────────────────────────────────────────────────────────
    ss   = data.get("system_status", "?")
    run  = data.get("run_id", "?")
    diag = data.get("issues", [])
    recs = data.get("recommendations", [])
    ms   = data.get("model_summary", {})
    sim  = data.get("simulation", {})
    ops  = data.get("ops", {})
    sp   = data.get("strategy_pack", {})
    ui   = data.get("ui", {})
    nds  = data.get("needs_detail", {})

    def tick(v): return "✅" if v else "❌"
    def _dir_table(d: dict) -> str:
        rows = [f"| `{k}` | {tick(v)} |" for k, v in d.items()]
        return "| Directory | Status |\n|---|---|\n" + "\n".join(rows)

    md = f"""# Post-Prompt-8 Full System Audit
**Audit ID:** `{AUDIT_ID}`
**Run ID:** `{run}`
**System Status:** **{ss}**
**Generated:** {NOW.strftime("%Y-%m-%d %H:%M:%S")}

---

## Executive Summary

| Metric | Value |
|---|---|
| Precincts Modeled | {ms.get("precinct_count", "?")} |
| Turfs Generated | {ms.get("turf_count", "?")} |
| Regions Generated | {ms.get("region_count", "?")} |
| Scenarios Simulated | {ms.get("scenario_count", "?")} |
| Strategy Packs | {len(sp.get("packs_found", []))} |
| Constraint Violations | {len(data.get("constraint_violations", []))} |
| Code Issues | {len(diag)} |
| UI Checks Passed | {ui.get("pass_count", 0)}/{ui.get("total_checks", 0)} |

---

## Pipeline Health

{_dir_table(data.get("dirs", {}))}

---

## Simulation Engine Validation

### Deterministic Forecast
- **File found:** {tick(data.get("deterministic", {}).get("file_found"))} `{data.get("deterministic", {}).get("path", "—")}`
- **Row count:** {data.get("deterministic", {}).get("row_count", 0)}
- **Missing columns:** {data.get("deterministic", {}).get("missing_cols", []) or "None ✅"}

### Monte Carlo
- **File found:** {tick(sim.get("file_found"))} `{sim.get("path", "—")}`
- **Rows:** {sim.get("row_count", 0):,} ({sim.get("max_iter", 0)} iterations per scenario)
- **Scenarios:** {sim.get("scenarios", [])}
- **Missing columns:** {sim.get("missing_cols", []) or "None ✅"}

### Scenario Summary
- **File found:** {tick(data.get("scenario_summary", {}).get("file_found"))}
- **Scenarios:** {data.get("scenario_summary", {}).get("scenarios", [])}
- **Probability violations:** {data.get("scenario_summary", {}).get("prob_violations", []) or "None ✅"}

---

## Operations Planner Validation

- **derived/ops/ exists:** {tick(ops.get("dir_exists"))}
- **Regions file:** {tick(ops.get("regions_found"))} — {ops.get("region_count", 0)} regions
- **Field plan:** {tick(ops.get("field_plan_found"))} — {ops.get("field_plan_rows", 0)} rows
- **Regions missing cols:** {ops.get("regions_missing_cols", []) or "None ✅"}
- **Field plan missing cols:** {ops.get("field_missing_cols", []) or "None ✅"}

---

## Strategy Generator Validation

- **Pack exists:** {tick(sp.get("exists"))}
- **Latest pack:** `{sp.get("latest_pack", "—")}`
- **Simulation results size:** {sp.get("simulation_results_bytes", 0):,} bytes

### File Presence
| File | Present |
|---|---|
""" + "\n".join(f"| `{k}` | {tick(v)} |" for k, v in sp.get("files", {}).items()) + f"""

### Strategy Decisions
| Check | Status |
|---|---|
""" + "\n".join(f"| {k} | {tick(v)} |" for k, v in sp.get("decision_checks", {}).items()) + f"""

### Meta Summary
- **win_probability:** {sp.get("meta_summary", {}).get("win_probability")}
- **recommended_strategy:** {sp.get("meta_summary", {}).get("recommended_strategy")}
- **scenario_count:** {sp.get("meta_summary", {}).get("scenario_count")}
- **forecast_mode:** {sp.get("meta_summary", {}).get("forecast_mode")}

---

## UI Integration Validation

{tick(ui.get("app_found"))} app.py found | **{ui.get("pass_count", 0)}/{ui.get("total_checks", 0)} checks passed**

| Check | Status |
|---|---|
""" + "\n".join(f"| {k} | {tick(v)} |" for k, v in ui.get("checks", {}).items()) + f"""

---

## NEEDS System Validation

| Key | Status |
|---|---|
""" + "\n".join(f"| `{n['key']}` | `{n['status']}` |" for n in nds.get("needs_status", [])) + f"""

---

## Issues Detected ({len(diag)})

""" + ("\n".join(f"- [{i['severity'].upper()}] `{i['file']}` L{i['line']}: {i['description']}" for i in diag[:20]) or "None") + f"""

---

## Recommendations

""" + ("\n".join(f"- {r}" for r in recs) or "None") + """

---

*Generated by `audit_post_prompt8.py`*
"""
    md_path.write_text(md, encoding="utf-8")

    # ── Export bundle ─────────────────────────────────────────────────────────
    shutil.copy(json_path, exp_dir / "audit_report.json")
    shutil.copy(md_path,   exp_dir / "audit_report.md")
    needs_src = BASE / "needs" / "needs.yaml"
    if needs_src.exists():
        shutil.copy(needs_src, exp_dir / "needs.yaml")

    # Copy latest run.log, pathway.json
    runs_dir = BASE / "logs" / "runs"
    if runs_dir.exists():
        run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()],
                          key=lambda d: d.stat().st_mtime, reverse=True)
        if run_dirs:
            for fname in ["run.log", "pathway.json", "validation.md", "qa.md"]:
                src = run_dirs[0] / fname
                if src.exists():
                    shutil.copy(src, exp_dir / fname)

    # Copy latest strategy_meta.json
    sp_root = BASE / "derived" / "strategy_packs"
    metas = sorted(sp_root.rglob("STRATEGY_META.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True) if sp_root.exists() else []
    if metas:
        shutil.copy(metas[0], exp_dir / "strategy_meta.json")
        summary_md = metas[0].parent / "STRATEGY_SUMMARY.md"
        if summary_md.exists():
            shutil.copy(summary_md, exp_dir / "strategy_summary.md")

    # Manifest
    manifest = {"audit_id": AUDIT_ID, "files": [f.name for f in exp_dir.iterdir()]}
    (exp_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return json_path, md_path, exp_dir


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  CAMPAIGN IN A BOX — POST-PROMPT-8 FULL SYSTEM AUDIT")
    print(f"  {NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    run_info = step1_latest_run()
    prior_id = step2_prior_audit()
    dirs     = step3_dirs()
    ingest   = step4_ingestion()
    geo      = step5_geo()
    xwalk    = step6_crosswalks()
    features = step7_features()
    univs    = step8_universes()
    targets  = step9_targets()
    turfs    = step10_turfs()
    det      = step11_deterministic()
    mc       = step12_montecarlo()
    summ     = step13_scenario_summary()
    ops      = step14_ops()
    sp       = step15_to_17_strategy(run_info["run_id"])
    ui       = step18_ui()
    needs    = step19_needs()
    issues   = step20_code_analysis()
    repo     = step21_repo_health()

    # Model summary
    ms = dict(
        precinct_count=features.get("row_count", 0),
        turf_count=turfs.get("turf_count", 0),
        region_count=ops.get("region_count", 0),
        scenario_count=len(mc.get("scenarios", [])),
        strategy_packs=len(sp.get("packs_found", [])),
    )

    # Constraint violations
    violations = []
    for v in features.get("violations", []):
        violations.append(dict(category="features", description=v))

    # Recommendations
    recs = []
    missing_dirs = [k for k, v in dirs.items() if not v]
    if missing_dirs:
        recs.append(f"Missing dirs: {missing_dirs} — run pipeline to create.")
    if not geo.get("geopandas_installed"):
        recs.append("geopandas not installed — run `pip install geopandas`.")
    if not det.get("file_found"):
        recs.append("No deterministic_forecast.csv — run simulation engine.")
    if not mc.get("file_found"):
        recs.append("No simulation_results.csv — run Monte Carlo simulation.")
    if not ops.get("regions_found"):
        recs.append("No regions.csv — run operations planner.")
    if not sp.get("exists"):
        recs.append("No strategy pack — run strategy generator.")
    if ui.get("pass_count", 0) < ui.get("total_checks", 1):
        failed = [k for k, v in ui.get("checks", {}).items() if not v]
        recs.append(f"UI checks failed: {failed}")
    if features.get("missing_cols"):
        recs.append(f"Feature CSV missing canonical cols: {features['missing_cols']}")
    missing_xw = [k for k, v in xwalk.items() if v == "missing"]
    if missing_xw:
        recs.append(f"Missing crosswalks: {missing_xw}")
    sim_probs = summ.get("prob_violations", [])
    if sim_probs:
        recs.append(f"Scenario summary probability violations: {sim_probs}")

    # System status
    critical_ok = (
        (BASE / "derived" / "simulation").exists() and
        (BASE / "derived" / "ops").exists() and
        (BASE / "derived" / "strategy_packs").exists() and
        ui.get("pass_count", 0) >= 8
    )
    feature_warn = (
        not features.get("file_found") or
        not turfs.get("file_found") or
        not det.get("file_found") or
        not mc.get("file_found") or
        not sp.get("exists")
    )
    system_status = "OK" if (critical_ok and not feature_warn and not violations) else "WARN"

    data = dict(
        system_status=system_status,
        audit_id=AUDIT_ID,
        prior_audit_id=prior_id,
        timestamp=NOW.isoformat(),
        **run_info,
        dirs=dirs,
        ingestion=ingest,
        geo=geo,
        crosswalk=xwalk,
        features=features,
        universes=univs,
        targets=targets,
        turfs=turfs,
        deterministic=det,
        simulation=mc,
        scenario_summary=summ,
        ops=ops,
        strategy_pack=sp,
        ui=ui,
        needs_detail=needs,
        model_summary=ms,
        constraint_violations=violations,
        needs_status=needs.get("needs_status", []),
        issues=issues,
        recommendations=recs,
        repo_metrics=repo,
    )

    json_path, md_path, exp_dir = write_reports(data)

    print(f"\n  JSON   -> {json_path.relative_to(BASE)}")
    print(f"  MD     -> {md_path.relative_to(BASE)}")
    print(f"  Bundle -> {exp_dir.relative_to(BASE)}")
    print("=" * 60)
    print()
    print("PROMPT-8 SYSTEM AUDIT COMPLETE")
    print("=" * 60)
    print(f"Run ID              : {run_info['run_id']}")
    print(f"Audit ID            : {AUDIT_ID}")
    print(f"System Status       : {system_status}")
    print()
    print(f"Precincts Modeled   : {ms['precinct_count']}")
    print(f"Turfs Generated     : {ms['turf_count']}")
    print(f"Regions Generated   : {ms['region_count']}")
    print(f"Scenarios Simulated : {ms['scenario_count']}")
    print(f"Strategy Packs      : {ms['strategy_packs']}")
    print()
    print(f"UI Checks Passed    : {ui.get('pass_count', 0)}/{ui.get('total_checks', 0)}")
    print()
    print(f"Audit Bundle:")
    print(f"  {exp_dir.relative_to(BASE)}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
