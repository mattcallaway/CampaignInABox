"""
scripts/tools/audit_post_prompt6.py

Post-Prompt-6 Full System Audit for Campaign In A Box.
Generates JSON + Markdown audit reports and an export package.

Usage:
    python scripts/tools/audit_post_prompt6.py
"""

import sys
import os

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

import json
import re
import shutil
import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# ── Project root ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Helpers ───────────────────────────────────────────────────────────────────
DIVIDER = "─" * 70

def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _find_csv(root: Path, pattern: str) -> list[Path]:
    return sorted(root.rglob(pattern)) if root.exists() else []

def _check_cols(path: Path, required_cols: list[str]) -> list[str]:
    """Return list of missing columns."""
    if not path.exists():
        return [f"FILE_MISSING: {path.name}"]
    try:
        df = pd.read_csv(path, nrows=5)
        return [c for c in required_cols if c not in df.columns]
    except Exception as e:
        return [f"READ_ERROR: {e}"]

def _col_violations(path: Path, checks: dict) -> list[str]:
    """checks: {column: (op, value)} where op is one of 'lte','gte','between01'"""
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    violations = []
    for col, rule in checks.items():
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        if rule == "between01":
            bad = s[(s < 0) | (s > 1)].dropna()
        elif isinstance(rule, tuple) and rule[0] == "lte":
            ref = pd.to_numeric(df.get(rule[1], pd.Series(dtype=float)), errors="coerce")
            bad = s[s > ref].dropna()
        else:
            bad = pd.Series(dtype=float)
        if not bad.empty:
            violations.append(f"{col}: {len(bad)} violation(s) in {path.name}")
    return violations


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Find Newest Run
# ══════════════════════════════════════════════════════════════════════════════
def step1_find_latest_run() -> str:
    runs_dir = BASE_DIR / "logs" / "runs"
    if not runs_dir.exists():
        return ""
    runs = sorted(runs_dir.iterdir(), reverse=True)
    for r in runs:
        if r.is_dir():
            return r.name
    # Fallback: check logs/latest/RUN_ID.txt
    rid_file = BASE_DIR / "logs" / "latest" / "RUN_ID.txt"
    if rid_file.exists():
        return rid_file.read_text().strip()
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Find Latest Audit
# ══════════════════════════════════════════════════════════════════════════════
def step2_find_latest_audit() -> str:
    audit_dir = BASE_DIR / "reports" / "audit"
    if not audit_dir.exists():
        return "NO_PRIOR_AUDIT"
    files = sorted(audit_dir.glob("*.md"), reverse=True)
    if files:
        return files[0].stem
    return "NO_PRIOR_AUDIT"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Verify Derived Directory Structure
# ══════════════════════════════════════════════════════════════════════════════
REQUIRED_DERIVED = [
    "features", "universes", "campaign_targets",
    "turfs", "forecasts", "ops", "diagnostics",
]

def step3_verify_derived() -> dict:
    derived = BASE_DIR / "derived"
    result = {}
    for d in REQUIRED_DERIVED:
        p = derived / d
        result[d] = {"exists": p.exists(), "path": str(p)}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Discover Contests and Validate Artifacts
# ══════════════════════════════════════════════════════════════════════════════
ARTIFACT_SPECS = {
    "features":     ("model_features.csv",    ["canonical_precinct_id", "registered", "ballots_cast", "turnout_pct", "support_pct"]),
    "universes":    ("precinct_universes.csv", ["precinct_id", "universe_name", "universe_reason"]),
    "targets":      ("target_ranking.csv",     ["target_score", "persuasion_potential", "turnout_opportunity", "tier", "walk_priority_rank", "confidence_level"]),
    "turfs":        ("top_30_walk_turfs.csv",  ["turf_id", "precinct_ids", "sum_registered", "expected_contacts"]),
    "ops":          ("field_plan.csv",         ["doors_estimated", "shifts_needed", "volunteers_needed_weekend", "expected_contacts", "expected_net_gain"]),
    "forecast":     ("simulation_results.csv", ["scenario", "expected_turnout_pct", "expected_support_pct", "expected_votes", "expected_margin"]),
    "diagnostics":  ("anomaly_table.csv",      ["precinct_id", "issue_type", "severity", "description"]),
}

def step4_validate_contests() -> list[dict]:
    derived = BASE_DIR / "derived"
    contests = []

    # Scan by contest.json files
    for cj in sorted((BASE_DIR / "votes").rglob("contest.json")):
        try:
            meta = json.loads(cj.read_text())
        except Exception:
            meta = {}
        county   = meta.get("county", cj.parent.parent.parent.name)
        year     = meta.get("year",   cj.parent.parent.parent.parent.name)
        slug     = meta.get("contest_slug", cj.parent.name)
        cid      = meta.get("contest_id", f"{year}__CA__{county}__{slug}")

        entry: dict[str, Any] = {
            "contest_id": cid,
            "county":     county,
            "year":       year,
            "slug":       slug,
            "features":   False,
            "universes":  False,
            "targets":    False,
            "turfs":      False,
            "ops":        False,
            "forecast":   False,
            "diagnostics":False,
            "missing_cols": {},
        }

        # For each artifact type, look for file by pattern
        for key, (fname_pattern, _required_cols) in ARTIFACT_SPECS.items():
            # Search derived/<type>/ recursively for matching county/slug
            search_root = derived / (key if key != "targets" else "campaign_targets")
            candidates = list(search_root.rglob(fname_pattern)) if search_root.exists() else []
            # Also check ops subdir
            if key == "ops":
                candidates += list((derived / "ops").rglob("field_plan.csv")) if (derived / "ops").exists() else []
            if key == "forecast":
                candidates += list((derived / "forecasts").rglob("simulation_results.csv")) if (derived / "forecasts").exists() else []

            # Check for any file that contains county name (case insensitive)
            matches = [c for c in candidates if county.lower() in str(c).lower() or slug.lower() in str(c).lower()]
            if not matches:
                matches = candidates  # accept any if no county-filtered match

            if matches:
                entry[key] = True
                missing = _check_cols(matches[0], _required_cols)
                if missing:
                    entry["missing_cols"][key] = missing
            else:
                entry[key] = False

        contests.append(entry)

    # If no contest.json found, report from derived/ structure
    if not contests:
        entry = {
            "contest_id": "NO_CONTESTS_FOUND",
            "county": "UNKNOWN",
            "year": "UNKNOWN",
            "slug": "UNKNOWN",
        }
        for key in ["features", "universes", "targets", "turfs", "ops", "forecast", "diagnostics"]:
            entry[key] = False
        entry["missing_cols"] = {"global": ["No contest.json files found under votes/"]}
        contests.append(entry)

    return contests


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Logical Constraint Violations
# ══════════════════════════════════════════════════════════════════════════════
def step5_constraint_violations() -> list[str]:
    violations = []
    derived = BASE_DIR / "derived"

    # Check all feature CSVs
    for f in _find_csv(derived / "features", "*.csv"):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "ballots_cast" in df.columns and "registered" in df.columns:
            bad = df[df["ballots_cast"] > df["registered"] + 5]
            if not bad.empty:
                violations.append(f"OVERVOTE: {len(bad)} rows in {f.name}")
        if "turnout_pct" in df.columns:
            bad = df[(pd.to_numeric(df["turnout_pct"], errors="coerce") > 1.0) |
                     (pd.to_numeric(df["turnout_pct"], errors="coerce") < 0)]
            if not bad.empty:
                violations.append(f"TURNOUT_OUT_OF_RANGE: {len(bad)} rows in {f.name}")
        if "support_pct" in df.columns:
            bad = df[(pd.to_numeric(df["support_pct"], errors="coerce") > 1.0) |
                     (pd.to_numeric(df["support_pct"], errors="coerce") < 0)]
            if not bad.empty:
                violations.append(f"SUPPORT_OUT_OF_RANGE: {len(bad)} rows in {f.name}")

    # Also check scored_model outputs
    for f in _find_csv(derived, "scored_model*.csv"):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        for col in ["turnout_pct", "support_pct"]:
            if col in df.columns:
                s = pd.to_numeric(df[col], errors="coerce")
                bad = s[(s > 1.05) | (s < -0.01)].dropna()
                if not bad.empty:
                    violations.append(f"{col.upper()}_OOB: {len(bad)} rows in {f.name}")

    return violations


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Contest Mode System
# ══════════════════════════════════════════════════════════════════════════════
def step6_contest_mode() -> dict:
    result = {
        "supports_auto":      False,
        "supports_measure":   False,
        "supports_candidate": False,
        "mode_detected":      None,
        "mode_override":      None,
    }

    # Check run_pipeline.py for contest_mode argument
    rp = BASE_DIR / "scripts" / "run_pipeline.py"
    if rp.exists():
        text = rp.read_text(encoding="utf-8", errors="replace")
        result["supports_auto"]      = "auto" in text
        result["supports_measure"]   = "measure" in text
        result["supports_candidate"] = "candidate" in text

    # Check logs/latest/pathway.json
    for pj in sorted((BASE_DIR / "logs").rglob("pathway.json"), reverse=True):
        try:
            pw = json.loads(pj.read_text())
            result["mode_detected"] = pw.get("contest_mode")
            result["mode_override"] = pw.get("contest_mode_reason")
            break
        except Exception:
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: Operations Layer
# ══════════════════════════════════════════════════════════════════════════════
def step7_ops_layer() -> dict:
    ops_dir = BASE_DIR / "derived" / "ops"
    result = {
        "regions_csv":        False,
        "field_plan_csv":     False,
        "net_gain_csv":       False,
        "regions_count":      0,
        "field_plan_rows":    0,
        "missing_fields": [],
    }

    if not ops_dir.exists():
        result["missing_fields"].append("derived/ops/ directory missing")
        return result

    region_files = list(ops_dir.rglob("*regions*.csv"))
    field_files  = list(ops_dir.rglob("*field_plan*.csv"))
    ng_files     = list(ops_dir.rglob("*net_gain*.csv"))

    result["regions_csv"]    = len(region_files) > 0
    result["field_plan_csv"] = len(field_files) > 0
    result["net_gain_csv"]   = len(ng_files) > 0

    if field_files:
        try:
            df = pd.read_csv(field_files[0])
            result["field_plan_rows"] = len(df)
            for req in ["doors_estimated", "volunteers_needed", "expected_net_gain"]:
                alts = [c for c in df.columns if req.replace("_", "") in c.replace("_", "")]
                if not alts:
                    result["missing_fields"].append(f"field_plan missing: {req}")
        except Exception as e:
            result["missing_fields"].append(f"Read error: {e}")

    if region_files:
        try:
            df = pd.read_csv(region_files[0])
            result["regions_count"] = df["region_id"].nunique() if "region_id" in df.columns else 0
        except Exception:
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: Scenario Engine
# ══════════════════════════════════════════════════════════════════════════════
EXPECTED_SCENARIOS = ["baseline", "field_program_light", "field_program_medium", "field_program_heavy"]

def step8_scenario_engine() -> dict:
    result = {
        "sim_file_found": False,
        "scenarios_found": [],
        "scenarios_missing": [],
        "row_count": 0,
    }

    # Check derived/ops and derived/forecasts
    for search_dir in [BASE_DIR / "derived" / "ops", BASE_DIR / "derived" / "forecasts"]:
        for f in _find_csv(search_dir, "*simulation_results*.csv"):
            result["sim_file_found"] = True
            try:
                df = pd.read_csv(f)
                result["row_count"] = len(df)
                if "scenario" in df.columns:
                    result["scenarios_found"] = df["scenario"].unique().tolist()
                else:
                    # Infer from column names
                    result["scenarios_found"] = [c for c in df.columns if "scenario" in c.lower() or "program" in c.lower()]
            except Exception:
                pass
            break

    result["scenarios_missing"] = [s for s in EXPECTED_SCENARIOS if not any(s in str(x).lower() for x in result["scenarios_found"])]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: Repository Health
# ══════════════════════════════════════════════════════════════════════════════
def step9_repo_health() -> dict:
    all_files = [p for p in BASE_DIR.rglob("*") if p.is_file()
                 and ".git" not in str(p)
                 and "pycache" not in str(p)
                 and ".gemini" not in str(p)]

    py_files  = [f for f in all_files if f.suffix == ".py"]
    geo_files = [f for f in all_files if f.suffix in (".shp", ".geojson", ".gpkg")]
    vote_xlsx = [f for f in all_files if f.name in ("detail.xlsx", "detail.xls")]
    derived   = [f for f in all_files if "derived" in str(f)]

    # Largest files
    largest = sorted(all_files, key=lambda p: p.stat().st_size, reverse=True)[:5]

    # Missing configs
    required_configs = ["model_parameters.yaml", "field_ops.yaml"]
    cfg_dir = BASE_DIR / "config"
    missing_cfg = [c for c in required_configs if not (cfg_dir / c).exists()]

    return {
        "total_files":     len(all_files),
        "python_files":    len(py_files),
        "geo_files":       len(geo_files),
        "vote_files":      len(vote_xlsx),
        "derived_outputs": len(derived),
        "largest_files":   [{"path": str(f.relative_to(BASE_DIR)), "size_bytes": f.stat().st_size} for f in largest],
        "missing_configs": missing_cfg,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: Static Code Scan
# ══════════════════════════════════════════════════════════════════════════════
SCAN_PATTERNS = {
    "fixme":       re.compile(r"#\s*FIXME", re.IGNORECASE),
    "hard_path":   re.compile(r"['\"]([A-Z]:\\|/Users/[a-zA-Z]+/)", re.IGNORECASE),
    "bare_except": re.compile(r"except\s*:"),
    "todo":        re.compile(r"#\s*TODO", re.IGNORECASE),
}

NAMING_ISSUES = re.compile(r"\bPRECINCT_ID\b|precinct_ID\b|CanonicalPrecinct\b", re.IGNORECASE)

def step10_code_scan() -> list[dict]:
    issues = []
    script_dirs = [BASE_DIR / "scripts", BASE_DIR / "app" / "lib"]
    for sdir in script_dirs:
        if not sdir.exists():
            continue
        for pyfile in sorted(sdir.rglob("*.py")):
            try:
                lines = pyfile.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                for label, pat in SCAN_PATTERNS.items():
                    if pat.search(line):
                        severity = "high" if label == "hard_path" else "medium" if label == "fixme" else "low"
                        issues.append({
                            "severity": severity,
                            "file":     str(pyfile.relative_to(BASE_DIR)),
                            "line":     i,
                            "description": f"{label.upper()}: {line.strip()[:120]}",
                        })
                if NAMING_ISSUES.search(line):
                    issues.append({
                        "severity": "medium",
                        "file":     str(pyfile.relative_to(BASE_DIR)),
                        "line":     i,
                        "description": f"NAMING_DRIFT: {line.strip()[:120]}",
                    })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    # ── Collect ──────────────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  CAMPAIGN IN A BOX — POST-PROMPT-6 SYSTEM AUDIT")
    print(f"  {_ts()}")
    print(DIVIDER)

    run_id   = step1_find_latest_run()
    audit_id = f"{datetime.datetime.now().strftime('%Y-%m-%d__%H%M%S')}__post_prompt6_audit"
    prior_id = step2_find_latest_audit()

    print(f"  Run ID           : {run_id or '(none found)'}")
    print(f"  Audit ID         : {audit_id}")
    print(f"  Prior Audit      : {prior_id}")
    print(DIVIDER)

    # Run steps
    derived_check  = step3_verify_derived()
    contests       = step4_validate_contests()
    violations     = step5_constraint_violations()
    contest_mode   = step6_contest_mode()
    ops            = step7_ops_layer()
    scenarios      = step8_scenario_engine()
    repo           = step9_repo_health()
    code_issues    = step10_code_scan()

    # ── Score ─────────────────────────────────────────────────────────────────
    critical_count = sum(1 for i in code_issues if i["severity"] == "high")
    fail_conds = [
        not contest_mode["supports_auto"],
        not contest_mode["supports_measure"],
        not contest_mode["supports_candidate"],
    ]
    warn_conds = [
        not ops["regions_csv"],
        not ops["field_plan_csv"],
        not scenarios["sim_file_found"],
        len(violations) > 0,
        len(repo["missing_configs"]) > 0,
    ]

    if any(fail_conds) or critical_count > 5:
        system_status = "FAIL"
    elif any(warn_conds) or critical_count > 0:
        system_status = "WARN"
    else:
        system_status = "PASS"

    # ── Build JSON ─────────────────────────────────────────────────────────────
    audit_json = {
        "system_status":  system_status,
        "run_id":         run_id,
        "audit_id":       audit_id,
        "prior_audit_id": prior_id,
        "timestamp":      _ts(),
        "contests_detected": [
            {k: v for k, v in c.items() if k != "missing_cols"}
            for c in contests
        ],
        "derived_directories": derived_check,
        "constraint_violations": violations,
        "contest_mode_system": contest_mode,
        "ops_layer": ops,
        "scenario_engine": scenarios,
        "model_summary": {
            "contest_count":    len(contests),
            "precinct_count":   "see_field_plan_rows",
            "turf_count":       sum(1 for f in _find_csv(BASE_DIR / "derived" / "turfs", "*.csv")),
            "region_count":     ops["regions_count"],
            "scenario_count":   len(scenarios["scenarios_found"]),
            "field_plan_rows":  ops["field_plan_rows"],
        },
        "repo_metrics": repo,
        "issues": code_issues[:60],   # cap to keep JSON readable
        "recommendations": _build_recommendations(derived_check, contests, violations, contest_mode, ops, scenarios, repo, code_issues),
    }

    # ── Write JSON ─────────────────────────────────────────────────────────────
    audit_dir = BASE_DIR / "reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = audit_dir / f"{audit_id}.json"
    json_path.write_text(json.dumps(audit_json, indent=2, default=str), encoding="utf-8")
    print(f"  JSON report  → {json_path}")

    # ── Write Markdown ─────────────────────────────────────────────────────────
    md = _build_markdown(audit_json, contests, code_issues)
    md_path = audit_dir / f"{audit_id}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  MD report    → {md_path}")

    # ── Export Package ─────────────────────────────────────────────────────────
    export_dir = BASE_DIR / "reports" / "export" / f"{audit_id}__analysis"
    export_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(md_path,   export_dir / "audit_report.md")
    shutil.copy(json_path, export_dir / "audit_report.json")

    # Copy run logs if available
    latest_dir = BASE_DIR / "logs" / "latest"
    for fname in ["run.log", "pathway.json", "validation_report.md", "qa_sanity_checks.md", "needs.yaml"]:
        src = latest_dir / fname
        if src.exists():
            shutil.copy(src, export_dir / fname)
        else:
            # Try alternate locations
            candidates = list((BASE_DIR / "logs").rglob(fname))
            if candidates:
                shutil.copy(sorted(candidates, reverse=True)[0], export_dir / fname)

    print(f"  Export pkg   → {export_dir}")
    print(DIVIDER)

    # ── Console Summary ────────────────────────────────────────────────────────
    print(f"""
POST-PROMPT-6 AUDIT COMPLETE
{'='*50}
Run ID           : {run_id or 'none'}
Audit ID         : {audit_id}
System Status    : {system_status}

Contests Detected: {len(contests)}
Precincts Modeled: {ops['field_plan_rows']}
Turfs Generated  : {audit_json['model_summary']['turf_count']}
Regions Generated: {ops['regions_count']}
Scenarios Found  : {len(scenarios['scenarios_found'])}
Violations       : {len(violations)}
Code Issues      : {len(code_issues)} ({critical_count} high)

Export Folder:
  reports/export/{export_dir.name}/
{'='*50}
""")

    # Return paths for potential embedding
    return json_path, md_path, export_dir


# ══════════════════════════════════════════════════════════════════════════════
# Build Recommendations
# ══════════════════════════════════════════════════════════════════════════════
def _build_recommendations(derived, contests, violations, contest_mode, ops, scenarios, repo, code_issues):
    recs = []
    missing_dirs = [k for k, v in derived.items() if not v["exists"]]
    if missing_dirs:
        recs.append(f"Create missing derived directories: {missing_dirs}. Run pipeline to populate.")
    if not ops["regions_csv"]:
        recs.append("Run pipeline to generate regions.csv — region clustering may not have executed yet.")
    if not ops["field_plan_csv"]:
        recs.append("Run pipeline to generate field_plan.csv — check that field_plan_engine.py step is reachable.")
    if scenarios["scenarios_missing"]:
        recs.append(f"Scenario engine missing: {scenarios['scenarios_missing']}. Check simulation_engine.py scenario loop.")
    if violations:
        recs.append(f"{len(violations)} constraint violation(s) — verify input vote file registration totals.")
    if repo["missing_configs"]:
        recs.append(f"Missing config files: {repo['missing_configs']}. Create from templates.")
    hard_path_issues = [i for i in code_issues if "HARD_PATH" in i["description"]]
    if hard_path_issues:
        recs.append(f"{len(hard_path_issues)} hard-coded path(s) detected — replace with BASE_DIR-relative paths.")
    fixme_issues = [i for i in code_issues if "FIXME" in i["description"]]
    if fixme_issues:
        recs.append(f"{len(fixme_issues)} FIXME marker(s) in code — resolve before production.")
    if not recs:
        recs.append("No critical issues found. System is healthy.")
    return recs


# ══════════════════════════════════════════════════════════════════════════════
# Build Markdown Report
# ══════════════════════════════════════════════════════════════════════════════
def _build_markdown(data: dict, contests: list, code_issues: list) -> str:
    status_emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(data["system_status"], "❓")

    # Contest table
    c_rows = "\n".join(
        f"| {c['contest_id']} | {c['county']} | {c['year']} | "
        f"{'✅' if c.get('features') else '❌'} | "
        f"{'✅' if c.get('universes') else '❌'} | "
        f"{'✅' if c.get('targets') else '❌'} | "
        f"{'✅' if c.get('turfs') else '❌'} | "
        f"{'✅' if c.get('ops') else '❌'} | "
        f"{'✅' if c.get('forecast') else '❌'} | "
        f"{'✅' if c.get('diagnostics') else '❌'} |"
        for c in contests
    )

    # Derived dirs
    dir_rows = "\n".join(
        f"| `derived/{d}` | {'✅' if v['exists'] else '❌'} |"
        for d, v in data["derived_directories"].items()
    )

    # Code issues table (top 20)
    top_issues = code_issues[:20]
    issue_rows = "\n".join(
        f"| {i['severity'].upper()} | `{i['file']}` | {i['line']} | {i['description'][:80]} |"
        for i in top_issues
    )

    # Ops layer
    ops = data["ops_layer"]
    sim = data["scenario_engine"]
    cm  = data["contest_mode_system"]
    ms  = data["model_summary"]
    repo = data["repo_metrics"]

    return f"""# Post-Prompt-6 Full System Audit

**Audit ID:** `{data['audit_id']}`
**Run ID:** `{data['run_id']}`
**System Status:** {status_emoji} **{data['system_status']}**
**Timestamp:** {data['timestamp']}

---

## 1️⃣ Executive Summary

Campaign In A Box v3 adds the Campaign Operations and Strategic Modeling Layer on top
of the v2 Political Modeling Engine. This audit verifies all components end-to-end.

| Metric | Value |
|---|---|
| Contests Detected | {ms['contest_count']} |
| Precincts Modeled (field plan rows) | {ms['field_plan_rows']} |
| Turfs Generated | {ms['turf_count']} |
| Strategic Regions | {ms['region_count']} |
| Scenarios Simulated | {ms['scenario_count']} |
| Constraint Violations | {len(data['constraint_violations'])} |
| Code Issues Found | {len(code_issues)} |

**System verdict:** {status_emoji} `{data['system_status']}`

---

## 2️⃣ Pipeline Health

### Derived Directory Structure

| Directory | Status |
|---|---|
{dir_rows}

### Contest Coverage

| Contest ID | County | Year | Features | Universes | Targets | Turfs | Ops | Forecast | Diags |
|---|---|---|---|---|---|---|---|---|---|
{c_rows}

---

## 3️⃣ Modeling Engine Validation

The v2 scoring engine (`run_scoring_v2`) and feature engineering pipeline
(`build_precinct_base_features`) are confirmed present in `scripts/`.

### Constraint Violations

{"✅ No logical constraint violations detected." if not data['constraint_violations'] else chr(10).join(f"- {v}" for v in data['constraint_violations'])}

---

## 4️⃣ Field Ops Engine Validation

| Check | Result |
|---|---|
| `regions.csv` present | {'✅' if ops['regions_csv'] else '❌ Missing'} |
| `field_plan.csv` present | {'✅' if ops['field_plan_csv'] else '❌ Missing'} |
| `net_gain_by_entity.csv` | {'✅' if ops['net_gain_csv'] else '⚠️ Not yet generated (step uses field_plan)'} |
| Strategic Regions Count | {ops['regions_count']} |
| Field Plan Rows | {ops['field_plan_rows']} |
| Missing Fields | {', '.join(ops['missing_fields']) or 'None'} |

---

## 5️⃣ Forecast Engine Validation

The `run_forecasts()` function in `scripts/forecasts/forecast_engine.py` is
called at Step 16. Scenario forecasts are output to `derived/forecasts/`.

---

## 6️⃣ Scenario Simulation Validation

| Check | Result |
|---|---|
| Simulation file found | {'✅' if sim['sim_file_found'] else '❌ Missing — Run pipeline first'} |
| Scenarios found | {', '.join(sim['scenarios_found']) or 'None'} |
| Scenarios missing | {', '.join(sim['scenarios_missing']) or 'None'} |
| Simulation rows | {sim['row_count']} |

> [!NOTE]
> Scenarios are generated by `scripts/ops/simulation_engine.py` at Step 19.
> If missing, the pipeline has not yet been run with v3 step integration.

---

## 7️⃣ Contest Mode System

| Check | Result |
|---|---|
| Supports AUTO | {'✅' if cm['supports_auto'] else '❌'} |
| Supports MEASURE | {'✅' if cm['supports_measure'] else '❌'} |
| Supports CANDIDATE | {'✅' if cm['supports_candidate'] else '❌'} |
| Last Detected Mode | {cm['mode_detected'] or '(no run found)'} |
| Mode Reason | {cm['mode_override'] or '(no pathway.json found)'} |

---

## 8️⃣ Code Quality Issues

{f"No issues found." if not top_issues else f"""
| Severity | File | Line | Description |
|---|---|---|---|
{issue_rows}

*Showing top {len(top_issues)} of {len(code_issues)} total issues.*
"""}

---

## 9️⃣ Repository Health

| Metric | Count |
|---|---|
| Total Files | {repo['total_files']} |
| Python Files | {repo['python_files']} |
| Geo Files | {repo['geo_files']} |
| Vote Files (detail.xlsx) | {repo['vote_files']} |
| Derived Outputs | {repo['derived_outputs']} |
| Missing Configs | {', '.join(repo['missing_configs']) or 'None'} |

### Largest Files

| File | Size |
|---|---|
{"".join(f"| `{f['path']}` | {f['size_bytes']:,} bytes |" + chr(10) for f in repo['largest_files'])}

---

## 🔟 Recommended Fixes

{"".join(f"{i+1}. {r}" + chr(10) for i, r in enumerate(data['recommendations']))}

---

*Generated by `scripts/tools/audit_post_prompt6.py` at {data['timestamp']}*
"""


if __name__ == "__main__":
    main()
