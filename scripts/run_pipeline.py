#!/usr/bin/env python3
"""
scripts/run_pipeline.py  — Campaign In A Box v2

CLI entry point for the full election modeling pipeline.

Usage examples:
  # Check directory structure
  python scripts/run_pipeline.py --check-structure

  # Ingest staging data only
  python scripts/run_pipeline.py --ingest-only --staging-dir "C:/path/to/Campaign In A Box Data"

  # Full run with votes
  python scripts/run_pipeline.py \\
      --state CA \\
      --county Sonoma \\
      --year 2024 \\
      --contest-slug nov2024_general \\
      --membership-method auto \\
      --log-level verbose

  # Full run with explicit detail path
  python scripts/run_pipeline.py \\
      --state CA --county Sonoma --year 2024 --contest-slug nov2024_general \\
      --detail-path "votes/2024/CA/Sonoma/nov2024_general/detail.xlsx"
"""

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

import yaml

# ── Bootstrap ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent   # Campaign In A Box/
SCRIPTS_DIR = BASE_DIR / "scripts"
for p in [str(BASE_DIR), str(SCRIPTS_DIR.parent)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Imports ───────────────────────────────────────────────────────────────────
from scripts.lib.run_id import generate_run_id
from scripts.lib.hashing import sha256_file, file_info
from scripts.lib.ca_fips import fips_to_county, county_to_fips
from scripts.lib.deps import gate as dep_gate, update_needs_available
from scripts.lib.integrity import enforce_precinct_constraints, write_integrity_report
from scripts.lib.crosswalks import (
    discover_crosswalks, write_crosswalk_validation, update_needs_crosswalks
)
from scripts.geo.kepler_export import export_kepler_geojson as kepler_geojson_export
from app.lib.state_manager import clear_stale
from scripts.loaders.logger import RunLogger
from scripts.ingest import run_ingestion
from scripts.validation.geography_validator import (
    validate_county_geography,
    validate_votes_present,
)
from scripts.validation.boundary_index import (
    scaffold_boundary_index,
    refresh_boundary_index,
)
from scripts.geography.boundary_loader import load_canonical_geometry
from scripts.geography.crosswalk_resolver import load_crosswalk_from_category
from scripts.aggregation.vote_allocator import (
    parse_contest_workbook,
    allocate_votes_crosswalk,
    area_weighted_fallback,
    run_sanity_checks,
)
from scripts.modeling.precinct_model import build_precinct_model
from scripts.lib.schema import canonicalize_df, validate_schema
from scripts.features.feature_builder import build_precinct_base_features
from scripts.features.voter_features import aggregate_voter_file
from scripts.universes.universe_builder import apply_universe_rules
from scripts.modeling.scoring_engine_v2 import run_scoring_v2
from scripts.forecasts.forecast_engine import run_forecasts
from scripts.turfs.turf_generator import generate_turfs
from scripts.tests.diagnostics import run_diagnostics, run_ops_diagnostics, generate_diagnostic_summary
from scripts.ops.region_builder import build_strategic_regions, generate_region_summary
from scripts.ops.field_plan_engine import compute_field_plan, summarize_field_plan
from scripts.ops.simulation_engine import run_net_gain_simulation, simulate_scenarios
from scripts.turfs.turf_packer import generate_turf_packs
from scripts.strategy.strategy_generator import run_strategy_generator

from scripts.exports.exporter import (
    export_precinct_model,
    export_targeting_list,
    export_district_aggregates,
    export_kepler_geojson,
    export_universes,
    export_turfs,
    export_forecasts,
    export_ops_artifact,
)
from scripts.universes.voter_universe_exporter import export_voter_universes
from scripts.loaders.contest_registry import scaffold_contest_json, update_contest_from_parse

import pandas as pd


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config(key: str) -> dict:
    path = BASE_DIR / "config" / f"{key}.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _git_commit(message: str, paths: list[Path]):
    try:
        str_paths = [str(p) for p in paths if p and Path(p).exists()]
        if not str_paths:
            return
        subprocess.run(["git", "add"] + str_paths, cwd=str(BASE_DIR),
                       capture_output=True, check=False)
        subprocess.run(["git", "commit", "-m", message, "--allow-empty"],
                       cwd=str(BASE_DIR), capture_output=True, check=False)
    except Exception:
        pass


# ── Structure check ───────────────────────────────────────────────────────────

REQUIRED_DIRS = [
    "Campaign In A Box Data",
    "staging/extracted",
    "data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_GeoJSON",
    "data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_GeoPackage",
    "data/CA/counties/Sonoma/geography/precinct_shapes/MPREC_Shapefile",
    "data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_GeoJSON",
    "data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_GeoPackage",
    "data/CA/counties/Sonoma/geography/precinct_shapes/SRPREC_Shapefile",
    "data/CA/counties/Sonoma/geography/crosswalks",
    "data/CA/counties/Sonoma/geography/boundary_index",
    "votes",
    "voters",
    "derived/features",
    "derived/universes",
    "derived/forecasts",
    "derived/turfs",
    "derived/diagnostics",
    "derived/campaign_targets",
    "derived/maps",
    "derived/reports",
    "derived/ops",
    "derived/simulation",
    "derived/strategy_packs",
    "logs/runs",
    "logs/latest",
    "reports/validation",
    "reports/qa",
    "needs/history",
    "config",
    "scripts/features",
    "scripts/universes",
    "scripts/forecasts",
    "scripts/turfs",
    "scripts/tests",
]


def check_structure() -> bool:
    missing = [d for d in REQUIRED_DIRS if not (BASE_DIR / d).is_dir()]
    if missing:
        print(f"[STRUCTURE CHECK] FAIL -- {len(missing)} directories missing:")
        for m in missing:
            print(f"  missing: {m}")
        return False
    print(f"[STRUCTURE CHECK] OK -- all {len(REQUIRED_DIRS)} required directories present.")
    return True


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    state: str,
    county: str,
    year: str,
    contest_slug: str,
    detail_path_override: str | None = None,
    membership_method: str = "auto",
    staging_dir: str | None = None,
    log_level: str = "verbose",
    commit: bool = True,
    rebuild_memberships_only: bool = False,
    rebuild_maps_only: bool = False,
    rebuild_targets_only: bool = False,
    target_candidate: str | None = None,
    contest_mode: str = "auto",
) -> str:
    """Execute the full pipeline. Returns RUN_ID on success."""
    context_key = f"{state}/{county}/{year}/{contest_slug}"

    # ── Step 0: RUN_ID + logger ───────────────────────────────────────────
    run_id = generate_run_id(repo_dir=BASE_DIR)
    logger = RunLogger(run_id, BASE_DIR)
    logger.info(f"Pipeline v2 starting")
    logger.info(f"  state={state}  county={county}  year={year}  contest_slug={contest_slug}")
    logger.info(f"  membership_method={membership_method}  log_level={log_level}")

    config    = load_config("model_parameters")
    ops_config = load_config("field_ops")
    data_root = BASE_DIR / "data"
    votes_root = BASE_DIR / "votes"
    all_artifacts: list[Path] = []

    # ── Step 1: Ingestion (if staging_dir provided) ───────────────────────
    if staging_dir:
        logger.step_start("INGEST_STAGING", expected=[f"Files from: {staging_dir}"])
        try:
            result = run_ingestion(
                staging_dir=staging_dir,
                data_root=data_root,
                dry_run=False,
                log=logger,
            )
            county_count = len(result)
            file_count = sum(len(v) for v in result.values())
            logger.step_done(
                "INGEST_STAGING",
                notes=[f"{file_count} files across {county_count} counties"],
            )
        except Exception as e:
            logger.warn(f"Ingestion error (non-fatal): {e}")
            logger.step_skip("INGEST_STAGING", reason=str(e))
    else:
        logger.step_skip("INGEST_STAGING", reason="No --staging-dir provided; skipping ingestion")

    # ── Step 2: Scaffold boundary index ──────────────────────────────────
    if not (rebuild_maps_only or rebuild_targets_only):
        logger.step_start("SCAFFOLD_BOUNDARY_INDEX")
        bi_path = scaffold_boundary_index(data_root, county, log=logger)
        bi_refresh = refresh_boundary_index(data_root, county, log=logger)
        logger.step_done("SCAFFOLD_BOUNDARY_INDEX", outputs=[bi_path])
        all_artifacts.append(bi_path)
    else:
        logger.step_skip("SCAFFOLD_BOUNDARY_INDEX", reason="Skipped due to targeted rebuild flag")

    # ── Step 3: Validate geography ────────────────────────────────────────
    logger.step_start("VALIDATE_GEOGRAPHY", expected=[
        f"data/CA/counties/{county}/geography/precinct_shapes/",
        f"data/CA/counties/{county}/geography/crosswalks/",
    ])
    geo_validation = validate_county_geography(data_root, county, log=logger)
    for need in geo_validation["needs_entries"]:
        logger.register_need(
            need["category"], need["status"], need["blocks"],
            path=need.get("expected_path"),
        )
    logger.set_coverage("canonical_geometry", geo_validation["canonical_geometry"])
    logger.set_coverage("categories_present", len(geo_validation["present"]))
    logger.set_coverage("categories_missing", len(geo_validation["missing"]))
    logger.step_done("VALIDATE_GEOGRAPHY")

    # ── Step 4: Validate votes ────────────────────────────────────────────
    logger.step_start("VALIDATE_VOTES", expected=[
        f"votes/{year}/CA/{county}/{contest_slug}/detail.xlsx"
    ])

    if detail_path_override:
        detail_path = Path(detail_path_override)
        if not detail_path.is_absolute():
            detail_path = BASE_DIR / detail_path_override
        votes_valid = detail_path.exists()
        votes_need  = None
    else:
        votes_result = validate_votes_present(votes_root, year, county, contest_slug, log=logger)
        votes_valid  = votes_result["valid"]
        detail_path  = votes_result.get("path")
        votes_need   = votes_result.get("needs_entry")

    if not votes_valid:
        if votes_need:
            logger.register_need(
                votes_need["category"], votes_need["status"],
                votes_need["blocks"], path=votes_need.get("expected_path"),
            )
        logger.step_skip("VALIDATE_VOTES", reason="blocked: missing votes — detail.xlsx not found")
        # Still run ingestion/validation; just skip modeling steps
        logger.finalize(state, county, contest_slug, run_status="partial")
        if commit:
            _git_commit(
                f"reports: ingestion+validation run {run_id} -- {state}/{county} (no votes)",
                [logger.log_path, logger.pathway_path, logger.validation_path,
                 logger.qa_path, logger.needs_path, logger.needs_snapshot_path],
            )
        _print_summary(run_id, all_artifacts, no_votes=True)
        return run_id
    else:
        logger.register_input("detail.xlsx", detail_path)
        logger.step_done("VALIDATE_VOTES")

    # ── Step 5: Load geometry ─────────────────────────────────────────────
    logger.step_start("LOAD_GEOMETRY", expected=["MPREC preferred; SRPREC fallback"])
    gdf, geo_level, geo_id_col = load_canonical_geometry(
        data_root / "CA" / "counties",  # boundary_loader expects county parent
        state,
        county,
        logger=logger,
    )

    if gdf is None or (isinstance(gdf, dict) and gdf.get("_stub")):
        logger.step_skip("LOAD_GEOMETRY", reason="No usable geometry (geopandas unavailable or files missing)")
        if isinstance(gdf, dict):
            logger.register_need("geopandas_library", "missing", ["geometry_load", "kepler_export"])
        gdf = None
        geo_level = geo_validation["canonical_geometry"]
    else:
        logger.set_coverage("geometry_features", len(gdf))
        logger.step_done("LOAD_GEOMETRY")

    # ── Step 6: Load crosswalks ───────────────────────────────────────────
    logger.step_start("LOAD_CROSSWALKS")
    county_geo_dir = data_root / "CA" / "counties" / county / "geography"
    crosswalks: dict = {}
    crosswalk_categories = {
        "MPREC_to_SRPREC":          county_geo_dir / "crosswalks",
        "RG_to_RR_to_SR_to_SVPREC": county_geo_dir / "crosswalks",
    }
    for cat_label, cat_dir in crosswalk_categories.items():
        xwalk, ok = load_crosswalk_from_category(county_geo_dir, "crosswalks", logger=logger)
        if ok:
            crosswalks[cat_label] = xwalk
            break  # use first available crosswalk

    # Prompt 8.5: enhanced crosswalk discovery + validation
    _county_fips = county_to_fips(county) or county
    _contest_id_for_diag = f"{year}_{state}_{county.lower().replace(chr(32), chr(95))}_{contest_slug}"
    _xwalk_full = discover_crosswalks(BASE_DIR, state, _county_fips)
    write_crosswalk_validation(_xwalk_full, _contest_id_for_diag, run_id, BASE_DIR)
    update_needs_crosswalks(_xwalk_full, BASE_DIR)
    _n_xw_found = sum(1 for v in _xwalk_full.values() if v.get("status") in ("found", "fallback"))
    logger.info(f"  [CROSSWALKS] Discovered {_n_xw_found}/{len(_xwalk_full)} crosswalks")

    if not crosswalks:
        logger.step_skip("LOAD_CROSSWALKS", reason="No crosswalk files; using identity mapping")
    else:
        logger.step_done("LOAD_CROSSWALKS", notes=[f"{len(crosswalks)} crosswalk(s) loaded"])

    # ── Step 7: Scaffold contest.json ─────────────────────────────────────
    if not (rebuild_maps_only or rebuild_memberships_only):
        logger.step_start("SCAFFOLD_CONTEST_JSON")
        contest_json_path = scaffold_contest_json(
            votes_root, year=year, state=state, county=county, contest_slug=contest_slug,
        )
        logger.step_done("SCAFFOLD_CONTEST_JSON", outputs=[contest_json_path])
        all_artifacts.append(contest_json_path)
    else:
        # Just grab the path for later commits
        contest_json_path = votes_root / year / state / county / contest_slug / "contest.json"
        logger.step_skip("SCAFFOLD_CONTEST_JSON", reason="Skipped due to targeted rebuild flag")

    # ── Step 8: Parse contest workbook ────────────────────────────────────
    logger.step_start("PARSE_CONTEST", expected=["Detect sheet types; aggregate vote methods"])
    parsed_sheets = parse_contest_workbook(
        detail_path,
        contest_json_path=contest_json_path,
        config=config,
        logger=logger,
    )
    detected_types = [p["contest_type"] for p in parsed_sheets]
    logger.set_coverage("sheets_parsed", len(parsed_sheets))
    logger.step_done("PARSE_CONTEST")

    # ── Step 8.5: Determine Contest Mode ──────────────────────────────────
    final_mode = contest_mode.lower()
    if final_mode == "auto":
        # Heuristic: if any sheet is candidate_race, the whole run is candidate
        if "candidate_race" in detected_types:
            final_mode = "candidate"
            reason = "Inferred CANDIDATE (found candidate_race headers)"
        else:
            final_mode = "measure"
            reason = "Inferred MEASURE (found YES/NO headers)"
    else:
        reason = f"Explicit override: {final_mode.upper()}"

    logger.info(f"Contest Mode: {final_mode.upper()} ({reason})")
    # Store in pathway via the logger's step mechanism (cannot dict-index a list)
    logger.info(f"[PATHWAY] contest_mode={final_mode}  contest_mode_reason={reason}")

    # ── Steps 9-12: Allocate → Sanity → Model → Export (per sheet) ───────
    logger.step_start("ALLOCATE_VOTES")
    all_model_dfs: list[pd.DataFrame] = []

    for parsed in parsed_sheets:
        sheet_name   = parsed["sheet_name"]
        contest_type = parsed["contest_type"]
        totals_df    = parsed["totals_df"]

        if totals_df.empty:
            logger.step_skip(f"SHEET/{sheet_name}", reason="No data rows")
            continue

        logger.info(f"  Sheet {sheet_name!r}: {len(totals_df)} precincts, type={contest_type}")

        # Allocation
        xwalk = next(iter(crosswalks.values()), None) if crosswalks else None
        if xwalk and membership_method != "area_weighted":
            allocated_df = allocate_votes_crosswalk(
                totals_df, xwalk, src_id_col="PrecinctID", tgt_id_col="MPREC_ID"
            )
            method_used = "crosswalk"
        else:
            allocated_df = area_weighted_fallback(totals_df, src_id_col="PrecinctID")
            method_used = "area_weighted_fallback"

        logger.info(f"    Allocation: {method_used}, {len(allocated_df)} target precincts")

        # Sanity checks
        logger.step_start(f"SANITY/{sheet_name}")
        passed, violations = run_sanity_checks(allocated_df, config, logger=logger)
        if not passed:
            logger.hard_fail(f"SANITY/{sheet_name}", "; ".join(violations))
        logger.step_done(f"SANITY/{sheet_name}")

        # Build model
        logger.step_start(f"BUILD_MODEL/{sheet_name}")
        id_col = "MPREC_ID" if "MPREC_ID" in allocated_df.columns else allocated_df.columns[0]
        
        # Merge target candidate into config
        run_config = config.copy()
        if target_candidate:
            run_config["target_candidate"] = target_candidate
        run_config["contest_type"] = contest_type

        model_df = build_precinct_model(
            allocated_df, canvas_id_col=id_col,
            geography_level=geo_level, gdf=gdf, geo_id_col=geo_id_col, config=run_config,
        )
        model_df["SheetName"]   = sheet_name
        model_df["ContestType"] = contest_type
        all_model_dfs.append(model_df)
        logger.set_coverage(f"rows_{sheet_name}", len(model_df))
        logger.step_done(f"BUILD_MODEL/{sheet_name}")

    logger.step_done("ALLOCATE_VOTES")

    if not all_model_dfs:
        logger.hard_fail("ALLOCATE_VOTES", "No model DataFrames produced")

    # Prompt 8.5: INTEGRITY_ENFORCEMENT step
    logger.step_start("INTEGRITY_ENFORCEMENT")
    _all_repair_reports: list[dict] = []
    _repaired_model_dfs: list = []
    for _mdf in all_model_dfs:
        _sheet = _mdf["SheetName"].iloc[0] if "SheetName" in _mdf.columns else "unknown"
        _mdf_repaired, _repair_report = enforce_precinct_constraints(
            _mdf,
            id_col="canonical_precinct_id",
            registered_col="registered",
            ballots_col="ballots_cast",
            yes_col="yes_votes" if "yes_votes" in _mdf.columns else None,
            no_col="no_votes"   if "no_votes"  in _mdf.columns else None,
            log_ctx=_sheet,
            logger=logger,
        )
        _all_repair_reports.append(_repair_report)
        _repaired_model_dfs.append(_mdf_repaired)
    all_model_dfs = _repaired_model_dfs
    # Use _contest_id_for_diag if already defined, else build it
    if "_contest_id_for_diag" not in dir():
        _contest_id_for_diag = f"{year}_{state}_{county.lower().replace(chr(32), chr(95))}_{contest_slug}"
    _primary_repair = _all_repair_reports[0] if _all_repair_reports else {}
    write_integrity_report(_primary_repair, _contest_id_for_diag, run_id)
    _n_repaired = _primary_repair.get("repaired_rows", 0)
    logger.step_done("INTEGRITY_ENFORCEMENT", notes=[f"{_n_repaired} precinct(s) repaired"])

    # ── Step 13: Feature Engineering ─────────────────────────────────────
    logger.step_start("FEATURE_ENGINEERING")
    all_combined_features = []
    
    # Voter file check
    voter_file_path = BASE_DIR / "voters" / state / county / "voters.csv" # Standard path
    voter_features_df = aggregate_voter_file(voter_file_path, county, logger=logger)
    
    for model_df in all_model_dfs:
        sname = model_df["SheetName"].iloc[0]
        # Base contest features
        base_features = build_precinct_base_features(model_df, f"{contest_slug}__{sname}")
        
        # Merge with voter file if present
        if not voter_features_df.empty:
            merged = pd.merge(base_features, voter_features_df, on="canonical_precinct_id", how="left")
            logger.info(f"  Merged voter features for sheet {sname}")
        else:
            merged = base_features
            
        all_combined_features.append((sname, merged))
        
    logger.step_done("FEATURE_ENGINEERING")

    # ── Step 14: Universe Building ────────────────────────────────────────
    logger.step_start("UNIVERSE_BUILDING")
    all_universes = []
    for sname, feat_df in all_combined_features:
        uni_df = apply_universe_rules(feat_df)
        all_universes.append((sname, uni_df))
    logger.step_done("UNIVERSE_BUILDING")

    # ── Step 15: Scoring (v2) ─────────────────────────────────────────────
    logger.step_start("SCORING_V2")
    all_scored_dfs = []
    for sname, feat_df in all_combined_features:
        scored_df = run_scoring_v2(feat_df, logger=logger)
        # Attach universe info
        uni_df = next(u[1] for u in all_universes if u[0] == sname)
        scored_df = pd.merge(scored_df, uni_df, on="canonical_precinct_id", how="left")
        
        # Re-attach geometry
        m_df = next(m for m in all_model_dfs if m["SheetName"].iloc[0] == sname)
        if "geometry" in m_df.columns:
            scored_df = pd.merge(scored_df, m_df[["canonical_precinct_id", "geometry"]], on="canonical_precinct_id", how="left")
            
        all_scored_dfs.append((sname, scored_df))
    logger.step_done("SCORING_V2")

    # ── Step 17: Strategic Region Clustering (v3) ─────────────────────────
    logger.step_start("REGION_CLUSTERING")
    all_regions = []
    for sname, scored_df in all_scored_dfs:
        r_df = build_strategic_regions(scored_df, n_regions=10, logger=logger)
        all_regions.append((sname, r_df))
    logger.step_done("REGION_CLUSTERING")

    # ── Step 18: Field Operations Planning (v3) ───────────────────────────
    logger.step_start("FIELD_PLANNING")
    all_field_plans = []
    for sname, scored_df in all_scored_dfs:
        # Merge region_id
        r_df = next(r[1] for r in all_regions if r[0] == sname)
        merged = pd.merge(scored_df, r_df, on="canonical_precinct_id", how="left")
        
        # Compute plan
        plan_df = compute_field_plan(merged, ops_config)
        
        # Net Gain Modeling
        plan_df = run_net_gain_simulation(plan_df, ops_config, contest_mode=final_mode)
        
        all_field_plans.append((sname, plan_df))
    logger.step_done("FIELD_PLANNING")

    # ── Step 19: Scenario Simulation (v3) ─────────────────────────────────
    logger.step_start("SIMULATION")
    all_sim_results = []
    for sname, plan_df in all_field_plans:
        results_df = simulate_scenarios(plan_df, ops_config)
        all_sim_results.append((sname, results_df))
    logger.step_done("SIMULATION")

    # ── Step 20: Voter Universe Export (v3) ───────────────────────────────
    logger.step_start("VOTER_UNIVERSE_EXPORT")
    if not voter_features_df.empty and voter_file_path.exists():
        try:
            # Re-load raw voters for individual export
            voter_df = pd.read_csv(voter_file_path)
            for sname, plan_df in all_field_plans:
                out_dir = BASE_DIR / "derived" / "universes" / state / county / contest_slug / f"{sname}__voter_lists"
                export_voter_universes(voter_df, plan_df, out_dir, run_id, logger=logger)
            logger.step_done("VOTER_UNIVERSE_EXPORT")
        except Exception as e:
            logger.warn(f"Voter universe export failed: {e}")
            logger.step_skip("VOTER_UNIVERSE_EXPORT", reason=str(e))
    else:
        logger.step_skip("VOTER_UNIVERSE_EXPORT", reason="No voter file present")

    # ── Step 16: Forecasting ──────────────────────────────────────────────
    logger.step_start("FORECAST_GENERATION")
    all_forecasts = []
    for sname, scored_df in all_scored_dfs:
        try:
            forecast_df = run_forecasts(scored_df, logger=logger)
        except Exception as _fe:
            logger.warn(f"  Forecasting failed for {sname}: {_fe}")
            forecast_df = scored_df[["canonical_precinct_id"]].copy()
        all_forecasts.append((sname, forecast_df))
    logger.step_done("FORECAST_GENERATION")

    # ── Step 21: Turf Generation ──────────────────────────────────────────
    logger.step_start("TURF_GENERATION")
    all_turfs = []
    for sname, plan_df in all_field_plans:
        # We pass plan_df because it has region_id and target metrics
        t_df = generate_turfs(plan_df)
        all_turfs.append((sname, t_df))
    logger.step_done("TURF_GENERATION")

    # ── Step 22: Exporting (v3) ───────────────────────────────────────────
    logger.step_start("EXPORT_V2_OUTPUTS")
    for sname, plan_df in all_field_plans:
        slug_out = f"{county}_{year}_{contest_slug}" if len(all_field_plans) == 1 else f"{county}_{year}_{contest_slug}__{sname}"

        # Ensure region_id column exists (may be absent if clustering returned empty)
        if "region_id" not in plan_df.columns:
            plan_df = plan_df.copy()
            plan_df["region_id"] = "R01"

        # 1. Scored Model (with Regions/Ops)
        path = export_precinct_model(plan_df, BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(path)
        
        # 2. Kepler (v2 exporter) + Kepler GeoJSON (Prompt 8.5 geopandas-gated)
        k_path = export_kepler_geojson(plan_df, BASE_DIR, run_id, state, county, slug_out, id_col="canonical_precinct_id")
        if k_path: all_artifacts.append(k_path)
        # Kepler GeoJSON via geopandas (new, gracefully skipped if unavailable)
        _kepler_geo_root = BASE_DIR / "data" / state / "counties"
        _kj_path = kepler_geojson_export(
            plan_df, _kepler_geo_root, slug_out, run_id, logger=logger
        )
        if _kj_path: all_artifacts.append(_kj_path)
        
        # 3. Universes Summary
        uni_sum_path = export_universes(plan_df[["canonical_precinct_id", "universe_name", "universe_reason", "key_metrics_snapshot"]], BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(uni_sum_path)
        
        # 4. Forecasts
        f_path = export_forecasts(next(f[1] for f in all_forecasts if f[0] == sname), BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(f_path)
        logger.register_artifact(f_path, "scenario_forecasts.csv")
        
        # 5. Turfs
        t_path = export_turfs(next(t[1] for t in all_turfs if t[0] == sname), BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(t_path)

        # 6. Turf Packs (v3)
        tp_dir = BASE_DIR / "derived" / "turfs" / state / county / slug_out / f"{run_id}__turf_packs"
        generate_turf_packs(plan_df, next(t[1] for t in all_turfs if t[0] == sname), tp_dir, run_id)
        # We don't append individual turf packs to all_artifacts as they are many, but we note the directory exists
        logger.info(f"  Generated turf packs in {tp_dir}")

        # ── v3 Ops ──
        # Regions Artifact
        r_df = next(r[1] for r in all_regions if r[0] == sname)
        r_path = export_ops_artifact(r_df, "regions", BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(r_path)
        
        # Region Summary (Markdown)
        r_sum_md = generate_region_summary(plan_df, r_df)
        r_sum_path = BASE_DIR / "derived" / "ops" / state / county / slug_out / f"{run_id}__region_summary.md"
        r_sum_path.parent.mkdir(parents=True, exist_ok=True)
        r_sum_path.write_text(r_sum_md)
        all_artifacts.append(r_sum_path)

        # Field Plan
        fp_path = export_ops_artifact(plan_df, "field_plan", BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(fp_path)
        
        # Simulation
        sim_df = next(s[1] for s in all_sim_results if s[0] == sname)
        sim_path = export_ops_artifact(sim_df, "simulation_results", BASE_DIR, run_id, state, county, slug_out)
        all_artifacts.append(sim_path)
        logger.register_artifact(sim_path, "simulation_results.csv")
        
    logger.step_done("EXPORT_V2_OUTPUTS")

    # ── Step 23: Diagnostics ─────────────────────────────────────────────
    logger.step_start("DIAGNOSTICS")
    for sname, plan_df in all_field_plans:
        # Regular diagnostics
        anom_df = run_diagnostics(plan_df, f"{contest_slug}__{sname}", logger=logger)
        
        # Ops diagnostics (v3)
        ops_anom_df = run_ops_diagnostics(plan_df, next(t[1] for t in all_turfs if t[0] == sname), logger=logger)
        
        # Combine
        combined_anom = pd.concat([anom_df, ops_anom_df], ignore_index=True)
        
        if not combined_anom.empty:
            anom_path = BASE_DIR / "derived" / "diagnostics" / f"{run_id}__{sname}__anomalies.csv"
            combined_anom.to_csv(anom_path, index=False)
            all_artifacts.append(anom_path)
            
        diag_report = generate_diagnostic_summary(combined_anom, {"contest_slug": contest_slug})
        diag_path = BASE_DIR / "reports" / "qa" / f"{run_id}__{sname}__model_diagnostics.md"
        with open(diag_path, "w", encoding="utf-8") as f:
            f.write(diag_report)
        all_artifacts.append(diag_path)
        logger.register_artifact(diag_path, "model_diagnostics.md")
    logger.step_done("DIAGNOSTICS")

    # ── Step 24: Strategy Generator ───────────────────────────────────────────
    logger.step_start("STRATEGY_GENERATOR")
    # Build a contest_id to pass — matches what the generator uses for discovery
    _strategy_contest_id = f"{year}_CA_{county.lower().replace(' ', '_')}_{contest_slug}"
    try:
        pack_dir = run_strategy_generator(
            contest_id=_strategy_contest_id,
            run_id=run_id,
            contest_mode=final_mode,
            forecast_mode="both",
            state=state,
            county=county,
            contest_slug=contest_slug,
            logger=logger,
        )
        if pack_dir:
            all_artifacts.append(pack_dir / "STRATEGY_SUMMARY.md")
            logger.register_artifact(pack_dir / "STRATEGY_META.json", "strategy_meta.json")
            logger.step_done("STRATEGY_GENERATOR")
        else:
            logger.step_skip("STRATEGY_GENERATOR", reason="Insufficient derived inputs (degraded/blocked)")
    except Exception as e:
        logger.warn(f"Strategy generator failed (non-fatal): {e}")
        logger.step_skip("STRATEGY_GENERATOR", reason=str(e))

    # ── Step 14: Finalize + commit ────────────────────────────────────────
    logger.finalize(state, county, contest_slug, run_status="success")

    # Clear staleness flags upon success
    cleared_domains = []
    if rebuild_memberships_only:
        cleared_domains = ["memberships", "precinct_models", "district_aggregates", "campaign_targets", "maps"]
    elif rebuild_targets_only:
        cleared_domains = ["campaign_targets"]
    elif rebuild_maps_only:
        cleared_domains = ["maps"]
    else:
        # full rebuild
        cleared_domains = ["memberships", "precinct_models", "district_aggregates", "campaign_targets", "maps"]
        
    clear_stale(context_key, cleared_domains)

    if commit:
        _git_commit(
            f"derived: run {run_id} -- {state}/{county}/{year}/{contest_slug}",
            all_artifacts + [contest_json_path],
        )
        _git_commit(
            f"reports: logs+needs for run {run_id}",
            [logger.log_path, logger.pathway_path, logger.validation_path,
             logger.qa_path, logger.needs_path, logger.needs_snapshot_path]
            + list(logger.latest_dir.iterdir()),
        )

    _print_summary(run_id, all_artifacts)
    return run_id


def _print_summary(run_id: str, artifacts: list, no_votes: bool = False):
    print(f"\n{'='*60}")
    print(f"  RUN_ID : {run_id}")
    if no_votes:
        print(f"  STATUS : partial (votes not yet provided)")
    else:
        print(f"  STATUS : success")
        print(f"  Artifacts: {len(artifacts)}")
    print(f"  Logs   : logs/latest/run.log")
    print(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Campaign In A Box v2 — Election Modeling Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--check-structure", action="store_true",
                        help="Verify directory tree and exit")
    parser.add_argument("--ingest-only", action="store_true",
                        help="Run ingestion from --staging-dir and exit")
    parser.add_argument("--state",         default="CA")
    parser.add_argument("--county",        default="Sonoma",
                        help="County name (e.g. Sonoma)")
    parser.add_argument("--year",          default="2024",
                        help="Election year (e.g. 2024)")
    parser.add_argument("--contest-slug",  dest="contest_slug", default="general",
                        help="Contest slug (e.g. nov2024_general)")
    parser.add_argument("--detail-path",   dest="detail_path", default=None,
                        help="Override path to detail.xlsx (relative to project root)")
    parser.add_argument("--staging-dir",   dest="staging_dir", default=None,
                        help="Path to STAGING_DIR (Campaign In A Box Data folder)")
    parser.add_argument("--membership-method", dest="membership_method",
                        choices=["crosswalk", "area_weighted", "auto"], default="auto")
    parser.add_argument("--log-level",     dest="log_level",
                        choices=["verbose", "summary"], default="verbose")
    parser.add_argument("--no-commit",     dest="commit", action="store_false")
    parser.add_argument("--rebuild-memberships", action="store_true", help="Rebuild memberships and all downstream")
    parser.add_argument("--rebuild-maps-only", action="store_true", help="Only rebuild maps")
    parser.add_argument("--rebuild-targets-only", action="store_true", help="Only rebuild campaign targets")
    parser.add_argument("--target-candidate", dest="target_candidate", default=None,
                        help="Select target candidate for scoring (candidate races only)")
    parser.add_argument("--contest-mode", dest="contest_mode",
                        choices=["auto", "measure", "candidate"], default="auto",
                        help="Specify contest mode (default: auto)")
    parser.set_defaults(commit=True)

    args = parser.parse_args()

    if args.check_structure:
        sys.exit(0 if check_structure() else 1)

    if args.ingest_only:
        if not args.staging_dir:
            parser.error("--ingest-only requires --staging-dir")
        run_ingestion(staging_dir=args.staging_dir)
        sys.exit(0)

    try:
        from scripts.lib.county_registry import normalize_county_input
        c_record = normalize_county_input(args.county)
        resolved_county = c_record["county_name"]
    except ValueError as e:
        print(f"\n[CLI ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    try:
        run_pipeline(
            state=args.state,
            county=resolved_county,
            year=args.year,
            contest_slug=args.contest_slug,
            detail_path_override=args.detail_path,
            membership_method=args.membership_method,
            staging_dir=args.staging_dir,
            log_level=args.log_level,
            commit=args.commit,
            rebuild_memberships_only=args.rebuild_memberships,
            rebuild_maps_only=args.rebuild_maps_only,
            rebuild_targets_only=args.rebuild_targets_only,
            target_candidate=args.target_candidate,
            contest_mode=args.contest_mode,
        )
    except RuntimeError as e:
        print(f"\n[PIPELINE HARD FAIL] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[PIPELINE ERROR] {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
