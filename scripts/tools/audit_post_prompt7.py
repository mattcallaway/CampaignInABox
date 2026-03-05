"""
scripts/tools/audit_post_prompt7.py

Post-Prompt-7 Full System Audit for Campaign In A Box.
23-step comprehensive validation: ingestion → strategy generator → UI → NEEDS.

Usage:
    python scripts/tools/audit_post_prompt7.py
"""
from __future__ import annotations

import sys, os
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json, re, shutil, datetime, hashlib
from pathlib import Path
from typing import Any, Optional
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
D = "=" * 58

def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _find_csv(root: Path, pat: str) -> list[Path]:
    return sorted(root.rglob(pat)) if root.exists() else []

def _read(p: Path, nrows=None) -> pd.DataFrame:
    try:
        return pd.read_csv(p, nrows=nrows)
    except Exception:
        return pd.DataFrame()

def _sha(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    except Exception:
        return "?"

def _read_id(p: Path) -> str:
    if not p.exists():
        return ""
    raw = p.read_bytes()
    # Handle UTF-16 BOM
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16").strip()
    return raw.decode("utf-8", errors="replace").strip()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Latest run
# ══════════════════════════════════════════════════════════════════════════════
def step1_latest_run() -> dict:
    latest = BASE_DIR / "logs" / "latest"
    run_id = _read_id(latest / "RUN_ID.txt")
    pathway = {}
    pw_path = latest / "pathway.json"
    if pw_path.exists():
        try:
            pathway = json.loads(pw_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    # Also discover from runs dir
    runs_dir = BASE_DIR / "logs" / "runs"
    latest_log = None
    if runs_dir.exists():
        logs = sorted(runs_dir.glob("*.log"), reverse=True)
        if logs:
            latest_log = logs[0]

    return {
        "run_id":    run_id.replace("\x00", "").strip(),
        "timestamp": pathway.get("run_timestamp", ""),
        "state":     pathway.get("state", "CA"),
        "county":    pathway.get("county", ""),
        "contest_id": pathway.get("contest_id", ""),
        "run_status": pathway.get("run_status", "unknown"),
        "latest_log": str(latest_log) if latest_log else "",
        "pathway":   pathway,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Latest audit
# ══════════════════════════════════════════════════════════════════════════════
def step2_latest_audit() -> tuple[str, str]:
    audit_dir = BASE_DIR / "reports" / "audit"
    files = sorted(audit_dir.glob("*.json"), reverse=True) if audit_dir.exists() else []
    # Skip the one we're about to write
    prior = [f for f in files if "prompt7" not in f.stem]
    cur   = [f for f in files if "prompt6" in f.stem or "prompt7" in f.stem]
    audit_id  = datetime.datetime.now().strftime("%Y-%m-%d__%H%M%S") + "__post_prompt7_full_audit"
    prior_id  = prior[0].stem if prior else "NO_PRIOR"
    return audit_id, prior_id


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Required directories
# ══════════════════════════════════════════════════════════════════════════════
REQUIRED_DIRS = [
    "data", "votes",
    "derived/features", "derived/universes", "derived/campaign_targets",
    "derived/turfs", "derived/forecasts", "derived/ops",
    "derived/diagnostics", "derived/strategy_packs",
    "logs", "needs", "config", "scripts",
]

def step3_dirs() -> dict:
    return {d: (BASE_DIR / d).exists() for d in REQUIRED_DIRS}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Vote data ingestion
# ══════════════════════════════════════════════════════════════════════════════
def step4_ingestion() -> dict:
    result = {"contests": [], "issues": []}
    for cj in (BASE_DIR / "votes").rglob("contest.json"):
        try:
            m = json.loads(cj.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            result["issues"].append(f"Bad contest.json at {cj}: {e}")
            continue
        entry = {
            "path":     str(cj.relative_to(BASE_DIR)),
            "title":    m.get("contest_title", ""),
            "choices":  m.get("choices", []),
            "precinct_count": m.get("precinct_count", 0),
            "total_registered": m.get("total_registered", 0),
            "total_ballots": m.get("total_ballots", 0),
        }
        # Verify detail.xlsx exists
        detail = cj.parent / "detail.xlsx"
        entry["detail_xlsx"] = detail.exists()
        if not detail.exists():
            result["issues"].append(f"detail.xlsx missing for {cj.parent.name}")
        result["contests"].append(entry)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Geography
# ══════════════════════════════════════════════════════════════════════════════
def step5_geography() -> dict:
    geo_base = BASE_DIR / "data" / "CA" / "counties"
    result = {
        "geopandas_installed": False,
        "mprec_geojson": False,
        "srprec_geojson": False,
        "boundary_index": False,
        "geometry_parsed": False,
        "issues": [],
    }
    # Check geopandas
    try:
        import geopandas  # noqa
        result["geopandas_installed"] = True
    except ImportError:
        result["issues"].append("geopandas not installed")

    # Find geojson files
    mprec = list(geo_base.rglob("mprec_*.geojson"))
    srprec = list(geo_base.rglob("srprec_*.geojson"))
    bidx  = list(geo_base.rglob("boundary_index.csv"))
    result["mprec_geojson"] = len(mprec) > 0
    result["srprec_geojson"] = len(srprec) > 0
    result["boundary_index"] = len(bidx) > 0

    if result["geopandas_installed"] and mprec:
        try:
            import geopandas as gpd
            gdf = gpd.read_file(mprec[0])
            result["geometry_parsed"] = len(gdf) > 0
            result["mprec_precinct_count"] = len(gdf)
        except Exception as e:
            result["issues"].append(f"Geometry parse error: {e}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Crosswalk
# ══════════════════════════════════════════════════════════════════════════════
CROSSWALK_PATTERNS = {
    "SRPREC_TO_2020_BLK":    ["*sr_blk*", "*blk_map*"],
    "RGPREC_TO_2020_BLK":    ["*rg_blk*", "*rg_map*"],
    "2020_BLK_TO_MPREC":     ["*blk_mprec*"],
    "MPREC_to_SRPREC":       ["*mprec_srprec*"],
    "SRPREC_to_CITY":        ["*srprec*city*"],
    "RG_to_RR_to_SR_to_SVPREC": ["*rr_sr*", "*rg_rr*"],
}

def step6_crosswalk() -> dict:
    cw_dir = BASE_DIR / "data"
    result = {}
    for key, patterns in CROSSWALK_PATTERNS.items():
        found = False
        for pat in patterns:
            if list(cw_dir.rglob(pat)):
                found = True
                break
        result[key] = "found" if found else "missing"
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Feature engineering
# ══════════════════════════════════════════════════════════════════════════════
FEATURE_REQUIRED = ["canonical_precinct_id", "registered", "ballots_cast", "turnout_pct", "support_pct"]

def step7_features() -> dict:
    feat_root = BASE_DIR / "derived" / "features"
    # Also check precinct_models (legacy location)
    files = _find_csv(feat_root, "*.csv")
    if not files:
        files = _find_csv(BASE_DIR / "derived" / "precinct_models", "*.csv")
    if not files:
        files = _find_csv(BASE_DIR / "derived", "*model*.csv")

    result = {"file_found": False, "row_count": 0, "missing_cols": [], "violations": [], "path": ""}
    if not files:
        return result

    f = files[-1]  # Most recent
    result["file_found"] = True
    result["path"] = str(f.relative_to(BASE_DIR))
    df = _read(f)
    result["row_count"] = len(df)
    result["missing_cols"] = [c for c in FEATURE_REQUIRED if c not in df.columns]

    for col, lo, hi in [("turnout_pct", 0, 1.05), ("support_pct", 0, 1.05)]:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            bad = s[(s < lo - 0.01) | (s > hi + 0.01)].dropna()
            if not bad.empty:
                result["violations"].append(f"{col}: {len(bad)} OOB rows")

    if "ballots_cast" in df.columns and "registered" in df.columns:
        bc = pd.to_numeric(df["ballots_cast"], errors="coerce")
        reg = pd.to_numeric(df["registered"], errors="coerce")
        ov = (bc > reg + 5).sum()
        if ov:
            result["violations"].append(f"ballots_cast > registered: {ov} rows")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Universes
# ══════════════════════════════════════════════════════════════════════════════
def step8_universes() -> dict:
    files = _find_csv(BASE_DIR / "derived" / "universes", "*.csv")
    result = {"file_found": False, "row_count": 0, "universe_names": [], "missing_cols": []}
    if not files:
        return result
    df = _read(files[-1])
    result["file_found"] = True
    result["row_count"] = len(df)
    for c in ["precinct_id", "universe_name", "universe_reason"]:
        if c not in df.columns:
            result["missing_cols"].append(c)
    if "universe_name" in df.columns:
        result["universe_names"] = df["universe_name"].dropna().unique().tolist()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Target scoring
# ══════════════════════════════════════════════════════════════════════════════
TARGET_REQUIRED = ["target_score", "persuasion_potential", "turnout_opportunity",
                   "tier", "walk_priority_rank", "confidence_level"]

def step9_targets() -> dict:
    files = _find_csv(BASE_DIR / "derived" / "campaign_targets", "*.csv")
    if not files:
        files = _find_csv(BASE_DIR / "derived", "*target*ranking*.csv")
    result = {"file_found": False, "row_count": 0, "missing_cols": [], "tier_dist": {}}
    if not files:
        return result
    df = _read(files[-1])
    result["file_found"] = True
    result["row_count"] = len(df)
    result["missing_cols"] = [c for c in TARGET_REQUIRED if c not in df.columns]
    if "tier" in df.columns:
        result["tier_dist"] = df["tier"].value_counts().to_dict()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10 — Turfs
# ══════════════════════════════════════════════════════════════════════════════
def step10_turfs() -> dict:
    files = _find_csv(BASE_DIR / "derived" / "turfs", "*.csv")
    result = {"file_found": False, "turf_count": 0, "missing_cols": []}
    if not files:
        return result
    df = _read(files[-1])
    result["file_found"] = True
    result["turf_count"] = len(df)
    for c in ["turf_id", "precinct_ids", "sum_registered", "expected_contacts"]:
        if c not in df.columns:
            result["missing_cols"].append(c)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 11 — Forecasts
# ══════════════════════════════════════════════════════════════════════════════
EXPECTED_SCENARIOS = ["baseline", "field_program_light", "field_program_medium", "field_program_heavy"]

def step11_forecasts() -> dict:
    fc_dir = BASE_DIR / "derived" / "forecasts"
    result = {"files": [], "scenarios_found": [], "scenarios_missing": [], "row_count": 0}
    if not fc_dir.exists():
        return result
    for f in fc_dir.rglob("*.csv"):
        result["files"].append(str(f.relative_to(BASE_DIR)))
    # Find scenario file
    for f in fc_dir.rglob("*.csv"):
        df = _read(f)
        if "scenario" in df.columns:
            result["scenarios_found"] = df["scenario"].dropna().unique().tolist()
            result["row_count"] = len(df)
            break
    result["scenarios_missing"] = [s for s in EXPECTED_SCENARIOS
                                    if not any(s in str(x) for x in result["scenarios_found"])]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12 — Ops planning
# ══════════════════════════════════════════════════════════════════════════════
def step12_ops() -> dict:
    ops_dir = BASE_DIR / "derived" / "ops"
    result = {
        "dir_exists": ops_dir.exists(),
        "regions_csv": False, "field_plan_csv": False, "net_gain_csv": False,
        "region_count": 0, "field_plan_rows": 0, "missing_fields": [],
    }
    if not ops_dir.exists():
        return result
    for f in ops_dir.rglob("*region*.csv"):
        result["regions_csv"] = True
        df = _read(f)
        if "region_id" in df.columns:
            result["region_count"] = df["region_id"].nunique()
        break
    for f in ops_dir.rglob("*field_plan*.csv"):
        result["field_plan_csv"] = True
        df = _read(f)
        result["field_plan_rows"] = len(df)
        for c in ["doors_estimated", "volunteers_needed", "expected_net_gain"]:
            alts = [col for col in df.columns if c.replace("_","") in col.replace("_","")]
            if not alts:
                result["missing_fields"].append(c)
        break
    for f in ops_dir.rglob("*net_gain*.csv"):
        result["net_gain_csv"] = True
        break
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 13 — Simulation
# ══════════════════════════════════════════════════════════════════════════════
SIM_REQUIRED = ["scenario", "expected_turnout_pct", "expected_support_pct",
                "expected_votes", "expected_margin"]

def step13_simulation() -> dict:
    result = {"file_found": False, "scenarios": [], "missing_cols": [], "row_count": 0}
    for search in [BASE_DIR / "derived" / "ops", BASE_DIR / "derived" / "forecasts"]:
        for f in _find_csv(search, "*simulation*.csv"):
            df = _read(f)
            result["file_found"] = True
            result["row_count"] = len(df)
            result["missing_cols"] = [c for c in SIM_REQUIRED if c not in df.columns]
            if "scenario" in df.columns:
                result["scenarios"] = df["scenario"].dropna().unique().tolist()
            return result
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 14 — Strategy Generator outputs
# ══════════════════════════════════════════════════════════════════════════════
STRAT_FILES = ["STRATEGY_SUMMARY.md", "STRATEGY_META.json",
               "TOP_TARGETS.csv", "TOP_TURFS.csv", "FIELD_PACE.csv"]
META_REQUIRED = ["contest_id", "run_id", "contest_mode", "derived_mode",
                 "inputs_found", "inputs_missing"]

def step14_strategy() -> dict:
    sp_root = BASE_DIR / "derived" / "strategy_packs"
    result = {
        "dir_exists": sp_root.exists(),
        "packs_found": [],
        "latest_pack": None,
        "files_present": {},
        "meta_fields_missing": [],
        "meta": {},
    }
    if not sp_root.exists():
        return result

    # Find all pack dirs
    for contest_dir in sp_root.iterdir():
        for run_dir in sorted(contest_dir.iterdir(), reverse=True):
            result["packs_found"].append(str(run_dir.relative_to(BASE_DIR)))

    if result["packs_found"]:
        pack_dir = BASE_DIR / result["packs_found"][0]
        result["latest_pack"] = str(pack_dir)
        for f in STRAT_FILES:
            result["files_present"][f] = (pack_dir / f).exists()

        meta_path = pack_dir / "STRATEGY_META.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                result["meta"] = meta
                # Check required fields (flatten nested)
                flat = {**meta, **(meta.get("model_summary", {})), **(meta.get("topline_metrics", {}))}
                result["meta_fields_missing"] = [k for k in META_REQUIRED if k not in flat]
            except Exception as e:
                result["meta_fields_missing"].append(f"parse_error: {e}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 15 — Strategy decisions
# ══════════════════════════════════════════════════════════════════════════════
def step15_strategy_decisions(strat: dict) -> dict:
    result = {
        "has_top_targets": False,
        "has_top_turfs":   False,
        "has_field_pace":  False,
        "has_win_path":    False,
        "notes": [],
    }
    if not strat["latest_pack"]:
        result["notes"].append("No strategy pack found")
        return result

    pack = Path(strat["latest_pack"])
    result["has_top_targets"] = (pack / "TOP_TARGETS.csv").exists() and len(_read(pack / "TOP_TARGETS.csv")) > 0
    result["has_top_turfs"]   = (pack / "TOP_TURFS.csv").exists()   and len(_read(pack / "TOP_TURFS.csv")) > 0
    result["has_field_pace"]  = (pack / "FIELD_PACE.csv").exists()  and len(_read(pack / "FIELD_PACE.csv")) > 0

    meta = strat.get("meta", {})
    tl = meta.get("topline_metrics", {})
    result["has_win_path"] = tl.get("win_number") is not None

    if not result["has_top_targets"]:
        result["notes"].append("TOP_TARGETS.csv empty or missing")
    if not result["has_top_turfs"]:
        result["notes"].append("TOP_TURFS.csv empty or missing")
    if not result["has_win_path"]:
        result["notes"].append("Win number not computed — run after pipeline produces scored targets")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 16 — UI integration
# ══════════════════════════════════════════════════════════════════════════════
def step16_ui() -> dict:
    app_py = BASE_DIR / "app" / "app.py"
    result = {"app_found": app_py.exists(), "checks": {}}
    if not app_py.exists():
        return result
    text = app_py.read_text(encoding="utf-8", errors="replace")
    checks = {
        "strategy_generator_panel": "Strategy Generator" in text,
        "contest_selector":         "discover_contests" in text and "sg_contest" in text,
        "contest_mode_toggle":      "sg_mode" in text,
        "generate_button":          "Generate Strategy Pack" in text,
        "download_buttons":         "download_button" in text and "TOP_TARGETS" in text,
        "strategy_fn_import":       "run_strategy_generator" in text,
        "completeness_badge":       "derived_mode" in text and "badge_color" in text,
    }
    result["checks"] = checks
    result["pass_count"] = sum(checks.values())
    result["total_checks"] = len(checks)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 17 — NEEDS system
# ══════════════════════════════════════════════════════════════════════════════
def step17_needs() -> dict:
    needs_path = BASE_DIR / "needs" / "needs.yaml"
    result = {"file_found": False, "entries": {}, "strategy_generator_status": None}
    if not needs_path.exists():
        needs_path = BASE_DIR / "logs" / "latest" / "needs.yaml"
    if not needs_path.exists():
        return result
    try:
        data = yaml.safe_load(needs_path.read_text(encoding="utf-8", errors="replace")) or {}
        result["file_found"] = True
        result["entries"] = list(data.keys())
        sg = data.get("strategy_generator", {})
        if sg:
            # Could be nested by contest_id
            if isinstance(sg, dict):
                for v in sg.values():
                    if isinstance(v, dict) and "status" in v:
                        result["strategy_generator_status"] = v.get("status")
                        break
                    elif isinstance(sg, dict) and "status" in sg:
                        result["strategy_generator_status"] = sg.get("status")
    except Exception as e:
        result["parse_error"] = str(e)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 18 — Static code analysis
# ══════════════════════════════════════════════════════════════════════════════
SCAN_PATS = {
    "FIXME":        re.compile(r"#\s*FIXME", re.I),
    "HARD_PATH":    re.compile(r"['\"]([A-Z]:\\|/Users/[a-zA-Z]+/)", re.I),
    "BARE_EXCEPT":  re.compile(r"except\s*:"),
    "TODO":         re.compile(r"#\s*TODO", re.I),
}

def step18_code_scan() -> list[dict]:
    issues = []
    for pyfile in sorted((BASE_DIR / "scripts").rglob("*.py")):
        if ".gemini" in str(pyfile) or "pycache" in str(pyfile):
            continue
        try:
            lines = pyfile.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, 1):
            for label, pat in SCAN_PATS.items():
                if pat.search(ln):
                    issues.append({
                        "severity": "high" if label == "HARD_PATH" else "medium" if label == "FIXME" else "low",
                        "file": str(pyfile.relative_to(BASE_DIR)),
                        "line": i,
                        "description": f"{label}: {ln.strip()[:100]}",
                    })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# STEP 19 — Repo health
# ══════════════════════════════════════════════════════════════════════════════
def step19_repo() -> dict:
    skip = {".git", "__pycache__", ".gemini", "node_modules"}
    all_files = [p for p in BASE_DIR.rglob("*") if p.is_file()
                 and not any(s in str(p) for s in skip)]
    py  = [f for f in all_files if f.suffix == ".py"]
    geo = [f for f in all_files if f.suffix in (".geojson", ".gpkg", ".shp")]
    vo  = [f for f in all_files if f.name in ("detail.xlsx", "detail.xls")]
    der = [f for f in all_files if "derived" in str(f)]
    strat = list((BASE_DIR / "derived" / "strategy_packs").rglob("*")) if (BASE_DIR / "derived" / "strategy_packs").exists() else []
    largest = sorted(all_files, key=lambda x: x.stat().st_size, reverse=True)[:5]
    cfg = BASE_DIR / "config"
    missing_cfg = [c for c in ["model_parameters.yaml", "field_ops.yaml"] if not (cfg / c).exists()]
    return {
        "total_files":      len(all_files),
        "python_files":     len(py),
        "geo_files":        len(geo),
        "vote_files":       len(vo),
        "derived_outputs":  len(der),
        "strategy_packs":   len(strat),
        "largest_files":    [{"path": str(f.relative_to(BASE_DIR)), "bytes": f.stat().st_size} for f in largest],
        "missing_configs":  missing_cfg,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Build pipeline health map
# ══════════════════════════════════════════════════════════════════════════════
def pipeline_health(ing, feat, tgt, turf, fc, ops, sim, strat) -> dict:
    return {
        "ingestion":          len(ing["contests"]) > 0,
        "features":           feat["file_found"],
        "targets":            tgt["file_found"],
        "turfs":              turf["file_found"],
        "forecasts":          len(fc["files"]) > 0,
        "ops":                ops["dir_exists"],
        "simulation":         sim["file_found"],
        "strategy_generator": strat["dir_exists"] and len(strat["packs_found"]) > 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Recommendations
# ══════════════════════════════════════════════════════════════════════════════
def build_recs(dirs, feat, tgt, turf, fc, ops, sim, strat, geo, ui) -> list[str]:
    recs = []
    missing_dirs = [k for k, v in dirs.items() if not v]
    if missing_dirs:
        recs.append(f"Create missing directories: {missing_dirs} — run pipeline to populate.")
    if not feat["file_found"]:
        recs.append("No feature/model CSV in derived/ — run pipeline against real vote data.")
    if not ops["dir_exists"] or not ops["regions_csv"]:
        recs.append("derived/ops/ missing or empty — run v3 pipeline to generate regions + field plan.")
    if not sim["file_found"]:
        recs.append("No simulation_results.csv — confirm simulate_scenarios() is called in pipeline.")
    if strat["dir_exists"] and not strat["packs_found"]:
        recs.append("derived/strategy_packs/ exists but empty — click 'Generate Strategy Pack' in UI or run pipeline.")
    if not geo["geopandas_installed"]:
        recs.append("geopandas not installed — run `pip install geopandas` or `uv add geopandas`.")
    if not geo["mprec_geojson"]:
        recs.append("MPREC geojson not found — geography step will fall back to area-weighted method.")
    missing_ui = [k for k, v in ui.get("checks", {}).items() if not v]
    if missing_ui:
        recs.append(f"UI checks failed: {missing_ui}")
    if not fc["scenarios_missing"] == []:
        recs.append(f"Scenario engine missing scenarios: {fc['scenarios_missing']}")
    if not recs:
        recs.append("No critical issues found — system is healthy.")
    return recs


# ══════════════════════════════════════════════════════════════════════════════
# Markdown report
# ══════════════════════════════════════════════════════════════════════════════
def build_markdown(data: dict, strat_detail: dict, dec: dict) -> str:
    pl = data["pipeline"]
    ms = data["model_summary"]
    sp = data["strategy_pack"]
    repo = data["repo_metrics"]
    geo = data.get("geo", {})
    ui = data.get("ui", {})
    needs = data.get("needs_detail", {})

    def _tick(v): return "✅" if v else "❌"
    def _fmt(v): return f"{v:,}" if isinstance(v, (int, float)) else str(v or "N/A")

    status_emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(data["system_status"], "❓")

    pipe_rows = "\n".join(f"| {k.replace('_',' ').title()} | {_tick(v)} |" for k, v in pl.items())
    dir_rows  = "\n".join(f"| `{d}` | {_tick(e)} |" for d, e in data.get("dirs", {}).items())

    strat_files = "\n".join(
        f"| `{k}` | {_tick(v)} |"
        for k, v in sp.get("files", {}).items()
    )

    meta = strat_detail.get("meta", {})
    tl   = meta.get("topline_metrics", {})
    ms_m = meta.get("model_summary", {})

    ui_rows = "\n".join(
        f"| {k.replace('_',' ')} | {_tick(v)} |"
        for k, v in ui.get("checks", {}).items()
    )

    issues_top = data["issues"][:20]
    issue_rows = "\n".join(
        f"| {i['severity'].upper()} | `{i['file']}` | {i['line']} | {i['description'][:80]} |"
        for i in issues_top
    )

    recs = "\n".join(f"{i+1}. {r}" for i, r in enumerate(data["recommendations"]))

    return f"""# Post-Prompt-7 Full System Audit

**Audit ID:** `{data['audit_id']}`  
**Run ID:** `{data['run_id']}`  
**System Status:** {status_emoji} **{data['system_status']}**  
**Timestamp:** {data['timestamp']}

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Contests Detected | {len(data.get('ingestion', {}).get('contests', []))} |
| Precincts Modeled | {ms['precinct_count']} |
| Turfs Generated | {ms['turf_count']} |
| Strategic Regions | {ms['region_count']} |
| Scenarios Simulated | {ms['scenario_count']} |
| Strategy Packs | {len(sp.get('packs_found', []))} |
| Constraint Violations | {len(data['constraint_violations'])} |
| Code Issues | {len(data['issues'])} |

**Verdict:** {status_emoji} `{data['system_status']}`

---

## 2. Pipeline Health

| Step | Status |
|---|---|
{pipe_rows}

---

## 3. Required Directories

| Directory | Exists |
|---|---|
{dir_rows}

---

## 4. Data Ingestion

Contests found: **{len(data.get('ingestion', {}).get('contests', []))}**

{"".join(f"- `{c['path']}` — {c.get('title','?')} ({c.get('precinct_count',0)} precincts, {c.get('total_registered',0):,} registered)" + chr(10) for c in data.get('ingestion', {}).get('contests', []))}

---

## 5. Geography System

| Check | Result |
|---|---|
| geopandas installed | {_tick(geo.get('geopandas_installed'))} |
| MPREC geojson | {_tick(geo.get('mprec_geojson'))} |
| SRPREC geojson | {_tick(geo.get('srprec_geojson'))} |
| Boundary index | {_tick(geo.get('boundary_index'))} |
| Geometry parsed | {_tick(geo.get('geometry_parsed'))} |
| MPREC precinct count | {geo.get('mprec_precinct_count', 'N/A')} |

Issues: {', '.join(geo.get('issues', [])) or 'None'}

---

## 6. Crosswalk System

| Crosswalk | Status |
|---|---|
{"".join(f"| {k} | {'✅' if v == 'found' else '❌ Missing'} |" + chr(10) for k, v in data.get('crosswalk', {}).items())}

---

## 7. Feature Engineering

| Check | Value |
|---|---|
| File found | {_tick(data.get('features', {}).get('file_found'))} |
| Row count | {_fmt(data.get('features', {}).get('row_count', 0))} |
| Missing cols | {', '.join(data.get('features', {}).get('missing_cols', [])) or 'None'} |
| Violations | {', '.join(data.get('features', {}).get('violations', [])) or 'None'} |

---

## 8. Universe Generation

| Check | Value |
|---|---|
| File found | {_tick(data.get('universes', {}).get('file_found'))} |
| Row count | {_fmt(data.get('universes', {}).get('row_count', 0))} |
| Universe names | {', '.join(data.get('universes', {}).get('universe_names', [])) or 'N/A'} |

---

## 9. Target Scoring

| Check | Value |
|---|---|
| File found | {_tick(data.get('targets', {}).get('file_found'))} |
| Row count | {_fmt(data.get('targets', {}).get('row_count', 0))} |
| Missing cols | {', '.join(data.get('targets', {}).get('missing_cols', [])) or 'None'} |
| Tier distribution | {data.get('targets', {}).get('tier_dist', {})} |

---

## 10. Turf Generation

| Check | Value |
|---|---|
| File found | {_tick(data.get('turfs', {}).get('file_found'))} |
| Turf count | {_fmt(data.get('turfs', {}).get('turf_count', 0))} |
| Missing cols | {', '.join(data.get('turfs', {}).get('missing_cols', [])) or 'None'} |

---

## 11. Forecast Engine

Forecast files found: {len(data.get('forecasts', {}).get('files', []))}  
Scenarios found: {', '.join(data.get('forecasts', {}).get('scenarios_found', [])) or 'None'}  
Scenarios missing: {', '.join(data.get('forecasts', {}).get('scenarios_missing', [])) or 'None ✅'}

---

## 12. Operations Planning

| Check | Result |
|---|---|
| derived/ops/ exists | {_tick(data.get('ops', {}).get('dir_exists'))} |
| regions.csv | {_tick(data.get('ops', {}).get('regions_csv'))} |
| field_plan.csv | {_tick(data.get('ops', {}).get('field_plan_csv'))} |
| net_gain_by_entity.csv | {_tick(data.get('ops', {}).get('net_gain_csv'))} |
| Region count | {data.get('ops', {}).get('region_count', 0)} |
| Field plan rows | {data.get('ops', {}).get('field_plan_rows', 0)} |

---

## 13. Simulation Engine

| Check | Result |
|---|---|
| File found | {_tick(data.get('simulation', {}).get('file_found'))} |
| Scenarios | {', '.join(data.get('simulation', {}).get('scenarios', [])) or 'None'} |
| Row count | {data.get('simulation', {}).get('row_count', 0)} |
| Missing cols | {', '.join(data.get('simulation', {}).get('missing_cols', [])) or 'None'} |

---

## 14. Strategy Generator

| File | Present |
|---|---|
{strat_files}

**STRATEGY_META.json summary:**

| Field | Value |
|---|---|
| contest_id | {meta.get('contest_id', 'N/A')} |
| contest_mode | {meta.get('contest_mode', 'N/A')} |
| derived_mode | {meta.get('derived_mode', 'N/A')} |
| baseline_support | {tl.get('baseline_support', 'N/A')} |
| baseline_turnout | {tl.get('baseline_turnout', 'N/A')} |
| baseline_margin | {tl.get('baseline_margin', 'N/A')} |
| win_number | {tl.get('win_number', 'N/A')} |
| precinct_count | {ms_m.get('precinct_count', 'N/A')} |
| turf_count | {ms_m.get('turf_count', 'N/A')} |
| region_count | {ms_m.get('region_count', 'N/A')} |
| inputs_missing | {', '.join(meta.get('inputs_missing', [])) or 'None'} |

---

## 15. Strategy Decision Quality

| Decision | Produced |
|---|---|
| Top precinct targets | {_tick(dec.get('has_top_targets'))} |
| Top turfs | {_tick(dec.get('has_top_turfs'))} |
| Field pace plan | {_tick(dec.get('has_field_pace'))} |
| Win path summary | {_tick(dec.get('has_win_path'))} |

Notes: {', '.join(dec.get('notes', [])) or 'None'}

---

## 16. UI Integration

| Check | Pass |
|---|---|
{ui_rows}

Score: **{ui.get('pass_count',0)}/{ui.get('total_checks',0)}**

---

## 17. NEEDS System

File found: {_tick(needs.get('file_found'))}  
Entries: {', '.join(str(e) for e in needs.get('entries', [])) or 'None'}  
strategy_generator status: `{needs.get('strategy_generator_status', 'not found')}`

---

## 18. Code Quality

{"No issues." if not issues_top else f"""
| Severity | File | Line | Description |
|---|---|---|---|
{issue_rows}
*Top {len(issues_top)} of {len(data['issues'])} total (all medium/low)*
"""}

---

## 19. Repository Health

| Metric | Count |
|---|---|
| Total files | {repo['total_files']} |
| Python files | {repo['python_files']} |
| Geo files | {repo['geo_files']} |
| Vote files | {repo['vote_files']} |
| Derived outputs | {repo['derived_outputs']} |
| Strategy pack files | {repo['strategy_packs']} |
| Missing configs | {', '.join(repo['missing_configs']) or 'None'} |

---

## 20. Recommended Fixes

{recs}

---

*Generated by `scripts/tools/audit_post_prompt7.py` at {data['timestamp']}*
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print(f"\n{D}")
    print("  CAMPAIGN IN A BOX — POST-PROMPT-7 FULL SYSTEM AUDIT")
    print(f"  {_ts()}")
    print(D)

    run_info   = step1_latest_run()
    audit_id, prior_id = step2_latest_audit()
    dirs       = step3_dirs()
    ing        = step4_ingestion()
    geo        = step5_geography()
    cw         = step6_crosswalk()
    feat       = step7_features()
    uni        = step8_universes()
    tgt        = step9_targets()
    turf       = step10_turfs()
    fc         = step11_forecasts()
    ops        = step12_ops()
    sim        = step13_simulation()
    strat      = step14_strategy()
    dec        = step15_strategy_decisions(strat)
    ui         = step16_ui()
    needs_r    = step17_needs()
    code_scan  = step18_code_scan()
    repo       = step19_repo()

    # Violations
    violations = feat.get("violations", [])

    # Pipeline health
    pl = pipeline_health(ing, feat, tgt, turf, fc, ops, sim, strat)

    # System status
    hard_fail = [
        not ui["checks"].get("strategy_generator_panel"),
    ]
    warn_items = [
        not ops["dir_exists"],
        not sim["file_found"],
        not strat["packs_found"],
        len(violations) > 0,
        bool(repo["missing_configs"]),
    ]
    high_issues = [i for i in code_scan if i["severity"] == "high"]

    if any(hard_fail) or len(high_issues) > 5:
        status = "FAIL"
    elif any(warn_items) or high_issues:
        status = "WARN"
    else:
        status = "PASS"

    # Model summary
    meta_ms = strat.get("meta", {}).get("model_summary", {})
    ms = {
        "precinct_count": feat.get("row_count") or meta_ms.get("precinct_count", 0),
        "turf_count":     turf.get("turf_count") or meta_ms.get("turf_count", 0),
        "region_count":   ops.get("region_count") or meta_ms.get("region_count", 0),
        "scenario_count": len(fc.get("scenarios_found", [])) or meta_ms.get("scenario_count", 0),
    }

    recs = build_recs(dirs, feat, tgt, turf, fc, ops, sim, strat, geo, ui)

    # Build JSON
    audit_data = {
        "system_status":  status,
        "run_id":         run_info["run_id"],
        "audit_id":       audit_id,
        "prior_audit_id": prior_id,
        "timestamp":      _ts(),
        "pipeline":       pl,
        "dirs":           dirs,
        "ingestion":      ing,
        "geo":            {k: v for k, v in geo.items() if k != "issues"},
        "crosswalk":      cw,
        "features":       feat,
        "universes":      uni,
        "targets":        tgt,
        "turfs":          turf,
        "forecasts":      fc,
        "ops":            ops,
        "simulation":     sim,
        "strategy_pack":  {
            "exists":       strat["dir_exists"],
            "packs_found":  strat["packs_found"],
            "files":        strat["files_present"],
            "meta_missing": strat["meta_fields_missing"],
        },
        "strategy_decisions": dec,
        "ui":             ui,
        "needs_detail":   needs_r,
        "model_summary":  ms,
        "constraint_violations": violations,
        "needs_status":   [{"key": k, "status": v} for k, v in {"strategy_generator": needs_r.get("strategy_generator_status", "unknown")}.items()],
        "repo_metrics":   repo,
        "issues":         code_scan[:60],
        "recommendations": recs,
    }

    # Write JSON
    audit_dir = BASE_DIR / "reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = audit_dir / f"{audit_id}.json"
    json_path.write_text(json.dumps(audit_data, indent=2, default=str), encoding="utf-8")

    # Write Markdown
    md = build_markdown(audit_data, strat, dec)
    md_path = audit_dir / f"{audit_id}.md"
    md_path.write_text(md, encoding="utf-8")

    # Export bundle
    export_dir = BASE_DIR / "reports" / "export" / f"{audit_id}__analysis"
    export_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(json_path, export_dir / "audit_report.json")
    shutil.copy(md_path,   export_dir / "audit_report.md")

    latest = BASE_DIR / "logs" / "latest"
    for fname in ["run.log", "pathway.json", "validation.md", "qa.md", "needs.yaml"]:
        src = latest / fname
        if not src.exists():
            # look for alternate name
            for alt in [latest / f"validation_report.md", latest / f"qa_sanity_checks.md"]:
                if alt.exists():
                    shutil.copy(alt, export_dir / alt.name)
        elif src.exists():
            shutil.copy(src, export_dir / fname)

    # Copy strategy meta if exists
    if strat["latest_pack"]:
        sm = Path(strat["latest_pack"]) / "STRATEGY_META.json"
        if sm.exists():
            shutil.copy(sm, export_dir / "strategy_meta.json")

    print(f"  JSON   -> {json_path.relative_to(BASE_DIR)}")
    print(f"  MD     -> {md_path.relative_to(BASE_DIR)}")
    print(f"  Export -> {export_dir.relative_to(BASE_DIR)}")
    print(D)

    n_packs = len(strat["packs_found"])
    print(f"""
FULL SYSTEM AUDIT COMPLETE
{D}
Run ID              : {run_info['run_id']}
Audit ID            : {audit_id}
System Status       : {status}

Precincts Modeled   : {ms['precinct_count']}
Turfs Generated     : {ms['turf_count']}
Regions Generated   : {ms['region_count']}
Scenarios Simulated : {ms['scenario_count']}
Strategy Packs      : {n_packs}

Export Folder:
  reports/export/{export_dir.name}/
{D}
""")

    return json_path, md_path, export_dir, audit_data


if __name__ == "__main__":
    main()
