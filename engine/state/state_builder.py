"""
engine/state/state_builder.py — Prompt 14.5

Builds the canonical CampaignState from all latest derived outputs.

Entry point:
    build_campaign_state(project_root, run_id=None, contest_id=None)

Writes:
    derived/state/history/<RUN_ID>__campaign_state.json
    derived/state/latest/campaign_state.json   (stable pointer)
    derived/state/latest/campaign_metrics.csv  (one-row summary)
    derived/state/latest/data_requests.json    (stable pointer)
    derived/state/latest/recommendations.json  (top-5 feed)

Never writes voter-level records.
"""
from __future__ import annotations

import csv
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _g(d: Any, *keys, default=None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _latest_file(root: Path, pattern: str) -> Optional[Path]:
    try:
        hits = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        hits = [h for h in hits if ".gitkeep" not in h.name]
        return hits[0] if hits else None
    except Exception:
        return None


def _read_json(path: Optional[Path]) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Could not read JSON {path}: {e}")
    return {}


def _read_csv_dicts(path: Optional[Path]) -> list[dict]:
    if path and path.exists():
        try:
            import pandas as pd
            return pd.read_csv(path).to_dict("records")
        except Exception as e:
            log.warning(f"Could not read CSV {path}: {e}")
    return []


def _str_path(p: Optional[Path], root: Path) -> Optional[str]:
    if p and p.exists():
        try:
            return str(p.relative_to(root))
        except ValueError:
            return str(p)
    return None


# ── Main builder ──────────────────────────────────────────────────────────────

def build_campaign_state(
    project_root: Path,
    run_id: Optional[str] = None,
    contest_id: Optional[str] = None,
) -> dict:
    """
    Aggregate all latest derived outputs into one canonical state dict.

    Args:
        project_root: absolute path to the CampaignInABox project root
        run_id:       override the run to use (default: auto-detect latest)
        contest_id:   override contest (default: infer from latest run)

    Returns: the complete state dict (also written to disk)
    """
    from engine.state.state_schema import (
        make_empty_state, state_to_csv_row,
        empty_campaign_setup, empty_model_summary, empty_strategy_summary,
        empty_war_room_summary, empty_voter_intelligence_summary,
        empty_provenance_summary, empty_artifact_index,
    )

    root = Path(project_root)
    now  = datetime.utcnow().isoformat()

    # ── Detect run_id ─────────────────────────────────────────────────────────
    if not run_id:
        rid_file = root / "logs" / "latest" / "RUN_ID.txt"
        if rid_file.exists():
            run_id = rid_file.read_text(encoding="utf-8").strip()
        else:
            pw = _latest_file(root / "logs" / "runs", "*pathway*.json")
            run_id = pw.stem.split("__pathway")[0] if pw else "unknown"

    # ── Detect contest_id ─────────────────────────────────────────────────────
    if not contest_id:
        pw_path = _latest_file(root / "logs" / "runs", "*pathway*.json")
        if pw_path:
            pw_data = _read_json(pw_path)
            contest_id = pw_data.get("contest_id", "")
        if not contest_id:
            contest_id = ""

    # ── Load campaign config ──────────────────────────────────────────────────
    cfg: dict = {}
    try:
        import yaml
        cfg_path = root / "config" / "campaign_config.yaml"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
    except Exception as e:
        log.warning(f"Could not load campaign_config: {e}")

    _state_val  = cfg.get("campaign", {}).get("state", "")
    _county_val = cfg.get("campaign", {}).get("county", "")

    state = make_empty_state()
    state["run_id"]       = run_id
    state["contest_id"]   = contest_id
    state["state"]        = _state_val
    state["county"]       = _county_val
    state["generated_at"] = now

    # ── Section A: campaign_setup ─────────────────────────────────────────────
    cs = empty_campaign_setup()
    c  = cfg.get("campaign", {})
    b  = cfg.get("budget", {})
    t  = cfg.get("targets", {})
    v  = cfg.get("volunteers", {})
    f  = cfg.get("field", {})
    cs["contest_name"]       = c.get("contest_name")
    cs["contest_type"]       = c.get("contest_type")
    cs["election_date"]      = c.get("election_date")
    cs["target_vote_share"]  = t.get("target_vote_share")
    cs["total_budget"]       = b.get("total_budget")
    cs["field_budget"]       = b.get("field_budget")
    cs["mail_budget"]        = b.get("mail_budget")
    cs["digital_budget"]     = b.get("digital_budget")
    cs["volunteers_per_week"] = v.get("volunteers_per_week")
    cs["contact_rate"]       = f.get("contact_rate")
    cs["turnout_lift"]       = f.get("turnout_lift_per_contact")
    cs["strategy_priorities"] = cfg.get("strategy", {}).get("priorities", [])
    state["campaign_setup"] = cs

    # ── Section B: model_summary ──────────────────────────────────────────────
    ms = empty_model_summary()
    # From strategy packs
    sp_meta_path = _latest_file(root / "derived" / "strategy_packs", "STRATEGY_META.json")
    sp_meta      = _read_json(sp_meta_path)
    # From precinct model CSV
    pm_path      = _latest_file(root / "derived" / "precinct_models", "*.csv")
    precinct_count = 0
    baseline_support = None
    baseline_turnout = None
    if pm_path:
        try:
            import pandas as pd
            pm_df = pd.read_csv(pm_path)
            precinct_count   = len(pm_df)
            if "support_pct" in pm_df.columns:
                baseline_support = round(float(pm_df["support_pct"].mean()), 4)
            if "turnout_pct" in pm_df.columns:
                baseline_turnout = round(float(pm_df["turnout_pct"].mean()), 4)
        except Exception:
            pass

    # Top turfs and targets
    top_turfs_path   = _latest_file(root / "derived" / "turfs", "*.csv")
    top_targets_path = _latest_file(root / "derived" / "campaign_targets", "*.csv")
    turf_count       = len(_read_csv_dicts(top_turfs_path)) if top_turfs_path else None
    target_count     = len(_read_csv_dicts(top_targets_path)) if top_targets_path else None

    # Regions
    ops_path     = _latest_file(root / "derived" / "ops", "*region*.csv")
    region_count = len(_read_csv_dicts(ops_path)) if ops_path else None

    # Scenarios
    sim_path     = _latest_file(root / "derived" / "simulation", "*.csv")
    scenario_count = len(_read_csv_dicts(sim_path)) if sim_path else None

    ms["precinct_count"]       = precinct_count
    ms["turf_count"]           = turf_count
    ms["region_count"]         = region_count
    ms["scenario_count"]       = scenario_count
    ms["baseline_support"]     = baseline_support
    ms["baseline_turnout"]     = baseline_turnout
    ms["win_probability"]      = sp_meta.get("win_probability")
    ms["expected_margin"]      = sp_meta.get("expected_margin")
    ms["advanced_modeling_used"] = sp_meta.get("advanced_modeling_used", False)
    state["model_summary"] = ms

    # ── Section C: strategy_summary ───────────────────────────────────────────
    ss = empty_strategy_summary()
    # From Prompt 13 strategy outputs
    vote_path_path  = _latest_file(root / "derived" / "strategy", "*vote_path*.csv")
    field_strat_path = _latest_file(root / "derived" / "strategy", "*field_strategy*.csv")
    budget_alloc_path = _latest_file(root / "derived" / "strategy", "*budget_allocation*.csv")
    strategy_meta_path = _latest_file(root / "derived" / "strategy", "*STRATEGY_META*.json")

    # Also check Prompt 14 STRATEGY_META
    if strategy_meta_path:
        s14_meta = _read_json(strategy_meta_path)
        ss["win_number"]              = _g(s14_meta, "vote_path", "win_number")
        ss["base_votes"]              = _g(s14_meta, "vote_path", "base_votes")
        ss["persuasion_votes_needed"] = _g(s14_meta, "vote_path", "persuasion_votes_needed")
        ss["gotv_votes_needed"]       = _g(s14_meta, "vote_path", "gotv_votes_needed")
        ss["vote_path_coverage"]      = _g(s14_meta, "vote_path", "coverage_rate")
        ss["total_budget"]            = s14_meta.get("total_budget")
    elif vote_path_path:
        vp_rows = _read_csv_dicts(vote_path_path)
        if vp_rows:
            vp = vp_rows[0]
            ss["win_number"]              = vp.get("win_number")
            ss["persuasion_votes_needed"] = vp.get("persuasion_votes_needed")
            ss["gotv_votes_needed"]       = vp.get("gotv_votes_needed")

    if field_strat_path:
        fs_rows = _read_csv_dicts(field_strat_path)
        if fs_rows:
            ss["field_pace_doors_per_week"] = fs_rows[0].get("doors_per_week")

    ss["top_target_precinct_count"] = target_count
    ss["top_turf_count"]            = turf_count

    # Strategy recommendation text from sp_meta or strategy_summary
    sp_summary_md = root / "derived" / "strategy_packs"
    sp_summ_path  = _latest_file(sp_summary_md, "STRATEGY_SUMMARY.md")
    ss["recommended_strategy"] = "See strategy report." if sp_summ_path else None

    state["strategy_summary"] = ss

    # ── Section D: war_room_summary ────────────────────────────────────────────
    wr = empty_war_room_summary()
    daily_status_path   = _latest_file(root / "derived" / "war_room", "*daily_status.json")
    data_req_path       = _latest_file(root / "derived" / "war_room", "*data_requests.json")
    prov_path           = _latest_file(root / "derived" / "provenance", "*metric_provenance.json")
    runtime_summary     = {}
    try:
        import yaml
        rt_cfg = cfg
        from engine.war_room.runtime_loader import get_runtime_summary
        runtime_summary = get_runtime_summary(rt_cfg)
    except Exception:
        pass

    ds_data = _read_json(daily_status_path)
    dr_data = _read_json(data_req_path)
    pv_data = _read_json(prov_path)

    prov_sum = pv_data.get("summary", {})
    wr["real_metrics_count"]    = prov_sum.get("REAL", 0)
    wr["simulated_metrics_count"] = prov_sum.get("SIMULATED", 0)
    wr["estimated_metrics_count"] = prov_sum.get("ESTIMATED", 0)
    wr["missing_metrics_count"] = prov_sum.get("MISSING", 0)
    wr["war_room_ready"]        = pv_data.get("war_room_ready", False)
    wr["daily_status_available"] = bool(ds_data)
    wr["data_requests_count"]   = dr_data.get("total_requests", 0)
    wr["critical_requests"]     = dr_data.get("critical_count", 0)
    wr["high_priority_requests"] = dr_data.get("high_count", 0)

    rt_metrics = runtime_summary.get("metrics", {})
    wr["actual_field_doors"]    = rt_metrics.get("total_doors_knocked", 0)
    wr["actual_volunteer_count"] = rt_metrics.get("avg_volunteers_per_week", 0)
    wr["actual_spend"]          = rt_metrics.get("total_actual_spend", 0)

    # Risk level from top risks
    top_risks = ds_data.get("top_risks", [])
    if wr["critical_requests"] > 0:
        wr["current_risk_level"] = "HIGH"
    elif wr["high_priority_requests"] > 0 or len(top_risks) >= 3:
        wr["current_risk_level"] = "MEDIUM"
    else:
        wr["current_risk_level"] = "LOW"

    state["war_room_summary"] = wr

    # ── Section E: voter_intelligence_summary ─────────────────────────────────
    vi = empty_voter_intelligence_summary()
    voter_dir = root / "data" / "voters"
    vi["voter_file_loaded"] = bool(list(voter_dir.rglob("*.csv")) if voter_dir.exists() else [])

    # Precinct voter metrics
    pvm_path = _latest_file(root / "derived" / "voter_models", "*precinct*metrics*.csv")
    if pvm_path:
        pvm_rows = _read_csv_dicts(pvm_path)
        if pvm_rows:
            total_precincts = len(pvm_rows)
            matched = sum(1 for r in pvm_rows if r.get("voter_count", 0) > 0)
            vi["precinct_match_rate"] = round(matched / total_precincts, 4) if total_precincts else None

    # Universe sizes from target file
    tgt_path = _latest_file(root / "derived" / "voter_universes", "*gotv*.csv")
    if tgt_path:
        gotv_rows = _read_csv_dicts(tgt_path)
        vi["gotv_universe_size"] = len(gotv_rows)

    pers_path = _latest_file(root / "derived" / "voter_universes", "*persuasion*.csv")
    if pers_path:
        pers_rows = _read_csv_dicts(pers_path)
        vi["persuasion_universe_size"] = len(pers_rows)

    state["voter_intelligence_summary"] = vi

    # ── Section F: provenance_summary ─────────────────────────────────────────
    ps_out = empty_provenance_summary()
    ps_out["REAL"]      = prov_sum.get("REAL", 0)
    ps_out["SIMULATED"] = prov_sum.get("SIMULATED", 0)
    ps_out["ESTIMATED"] = prov_sum.get("ESTIMATED", 0)
    ps_out["MISSING"]   = prov_sum.get("MISSING", 0)
    ps_out["total"]     = sum(prov_sum.values()) if prov_sum else 0
    ps_out["war_room_ready"] = pv_data.get("war_room_ready", False)
    state["provenance_summary"] = ps_out

    # ── Section G: data_requests ──────────────────────────────────────────────
    state["data_requests"] = dr_data.get("requests", [])

    # ── Section H: risks ─────────────────────────────────────────────────────
    risk_path = _latest_file(root / "derived" / "strategy", "*risk_analysis*.csv")
    risk_rows = _read_csv_dicts(risk_path)
    risks = []
    for i, r in enumerate(risk_rows):
        risks.append({
            "risk_id":     f"RISK_{i+1:02d}",
            "severity":    r.get("level", "MEDIUM"),
            "description": r.get("risk", ""),
            "source":      "strategy_generator",
            "mitigation":  r.get("mitigation", ""),
        })
    # Add war room live risks
    for i, risk_text in enumerate(top_risks):
        risks.append({
            "risk_id":     f"WR_{i+1:02d}",
            "severity":    "HIGH" if "no real" in risk_text.lower() or "0%" in risk_text else "MEDIUM",
            "description": risk_text,
            "source":      "war_room_status_engine",
            "mitigation":  "Enter real data in War Room to update forecasts.",
        })
    state["risks"] = risks

    # ── Section I: recommendations ────────────────────────────────────────────
    recommendations = _build_recommendations(state, ds_data, dr_data, sp_meta, cfg)
    state["recommendations"] = recommendations

    # ── Section J: artifact_index ─────────────────────────────────────────────
    ai = empty_artifact_index()
    ai["strategy_meta"]      = _str_path(strategy_meta_path or sp_meta_path, root)
    ai["precinct_model"]     = _str_path(pm_path, root)
    ai["targeting_list"]     = _str_path(top_targets_path, root)
    ai["simulation_results"] = _str_path(sim_path, root)
    ai["field_plan"]         = _str_path(field_strat_path, root)
    ai["voter_universes"]    = _str_path(tgt_path or pers_path, root)
    ai["audit_report"]       = _str_path(
        _latest_file(root / "reports" / "audit", "*post_prompt86_audit.json"), root)
    ai["daily_status"]       = _str_path(daily_status_path, root)
    ai["metric_provenance"]  = _str_path(prov_path, root)
    ai["forecast_comparison"] = _str_path(
        _latest_file(root / "derived" / "war_room", "*forecast_update_comparison.csv"), root)
    state["artifact_index"] = ai

    # ── Section K: intelligence_summary (Prompt 17) ───────────────────────────
    intel_dir = root / "derived" / "intelligence"
    intel_adj  = _read_json(intel_dir / "support_adjustment.json")
    intel_poll = _read_json(intel_dir / "poll_average.json")
    intel_reg  = _read_json(intel_dir / "registration_summary.json")
    intel_br   = _read_json(intel_dir / "ballot_returns_summary.json")
    intel_mac  = _read_json(intel_dir / "macro_environment.json")

    state["intelligence_summary"] = {
        "poll_average":             intel_poll.get("poll_average"),
        "n_polls":                  intel_poll.get("n_polls", 0),
        "poll_ci_low":              intel_poll.get("confidence_interval_low"),
        "poll_ci_high":             intel_poll.get("confidence_interval_high"),
        "registration_growth":      intel_reg.get("registration_growth"),
        "net_partisan_score":       intel_reg.get("net_partisan_score"),
        "ballot_return_rate":       intel_br.get("return_rate"),
        "dem_return_advantage":     intel_br.get("partisan_advantage"),
        "projected_turnout":        intel_br.get("projected_turnout"),
        "macro_environment_score":  intel_mac.get("macro_environment_score"),
        "intelligence_adjustment":  intel_adj.get("intelligence_adjustment"),
        "adjusted_support":         intel_adj.get("adjusted_support"),
        "intelligence_impact":      intel_adj.get("impact"),
        "intelligence_source_type": intel_adj.get("source_type", "MISSING"),
        "has_real_signals":         intel_adj.get("has_real_signals", False),
    }

    # ── Section L: file_inventory (Prompt 17.5) ───────────────────────────────
    registry_path = root / "derived" / "file_registry" / "latest" / "file_registry.json"
    req_path = root / "derived" / "file_registry" / "latest" / "missing_data_requests.json"
    rec_path = root / "derived" / "file_registry" / "latest" / "source_finder_recommendations.json"

    reg_data = _read_json(registry_path) if registry_path.exists() else []
    missing_data = _read_json(req_path)
    sources = _read_json(rec_path)

    active_count = sum(1 for r in reg_data if r.get("status") in ("ACTIVE", "REGISTERED"))
    archived_count = sum(1 for r in reg_data if r.get("status") == "ARCHIVED")

    reqs = missing_data.get("requests", [])
    missing_crit = sum(1 for r in reqs if r.get("priority") in ("critical", "high"))
    missing_opt  = sum(1 for r in reqs if r.get("priority") not in ("critical", "high"))

    state["file_inventory_summary"] = {
        "active_files": active_count,
        "archived_files": archived_count,
        "missing_critical_files": missing_crit,
        "missing_optional_files": missing_opt
    }
    state["missing_data_requests_intake"] = reqs
    state["source_recommendations_available"] = bool(sources.get("recommendations"))

    # ── Section M: performance_summary (Prompt 18) ────────────────────────────
    perf_health = _read_json(root / "derived" / "performance" / f"{run_id}__campaign_health.json")
    state["performance_summary"] = {
        "chi_score":     perf_health.get("chi_score", 0.0),
        "health_status": perf_health.get("status", "UNKNOWN"),
        "doors_health":  perf_health.get("doors_health", "UNKNOWN"),
        "calls_health":  perf_health.get("calls_health", "UNKNOWN")
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    _write_state(state, root, run_id, recommendations)
    return state


# ── Recommendations builder ────────────────────────────────────────────────────

def _build_recommendations(
    state: dict, ds_data: dict, dr_data: dict, sp_meta: dict, cfg: dict
) -> list[dict]:
    recs: list[dict] = []

    # From data requests (highest priority operational recs)
    for req in dr_data.get("requests", [])[:3]:
        recs.append({
            "type":             "DATA_INPUT",
            "priority":         req.get("priority", "medium").upper(),
            "description":      req.get("title", ""),
            "action":           req.get("recommended_ui_action", ""),
            "provenance_basis": "MISSING",
            "source":           "data_request_engine",
        })

    # From war room next 72h priorities
    for p72 in ds_data.get("next_72h_priorities", [])[:2]:
        recs.append({
            "type":             "OPERATIONAL",
            "priority":         "HIGH",
            "description":      p72,
            "action":           "Execute immediately",
            "provenance_basis": "SIMULATED",
            "source":           "war_room_status_engine",
        })

    # Strategy-level: field pace
    fp = ds_data.get("field_pace", {})
    pace = fp.get("pace_pct")
    if pace is not None and pace < 80:
        recs.append({
            "type":             "FIELD_STRATEGY",
            "priority":         "HIGH",
            "description":      f"Field pace is {pace:.0f}% of target — increase canvassing capacity",
            "action":           "Recruit additional canvassers or increase shift hours",
            "provenance_basis": "ESTIMATED",
            "source":           "strategy_summary",
        })

    # Budget alert
    bs = ds_data.get("budget_status", {})
    burn = bs.get("burn_pct", 0)
    expected = bs.get("expected_burn_pct", 0)
    if burn is not None and expected and burn > expected * 1.15:
        recs.append({
            "type":             "BUDGET",
            "priority":         "MEDIUM",
            "description":      f"Budget burning {burn:.0f}% vs expected {expected:.0f}% — review allocations",
            "action":           "Review budget actuals in War Room → Resources tab",
            "provenance_basis": "ESTIMATED",
            "source":           "war_room_status_engine",
        })

    # Top-5 only
    return recs[:5]


# ── File writers ──────────────────────────────────────────────────────────────

def _write_state(state: dict, root: Path, run_id: str, recommendations: list) -> None:
    from engine.state.state_schema import state_to_csv_row
    import pandas as pd

    # Directories
    hist_dir   = root / "derived" / "state" / "history"
    latest_dir = root / "derived" / "state" / "latest"
    hist_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    state_json = json.dumps(state, indent=2, default=str)

    # History copy
    hist_path = hist_dir / f"{run_id}__campaign_state.json"
    hist_path.write_text(state_json, encoding="utf-8")
    log.info(f"State written → {hist_path.name}")

    # Stable latest pointer
    latest_state = latest_dir / "campaign_state.json"
    latest_state.write_text(state_json, encoding="utf-8")

    # campaign_metrics.csv
    csv_row = state_to_csv_row(state)
    metrics_path = latest_dir / "campaign_metrics.csv"
    try:
        if metrics_path.exists():
            existing = pd.read_csv(metrics_path)
            new_row  = pd.DataFrame([csv_row])
            combined = pd.concat([existing, new_row], ignore_index=True)
            combined.to_csv(metrics_path, index=False)
        else:
            pd.DataFrame([csv_row]).to_csv(metrics_path, index=False)
    except Exception as e:
        log.warning(f"Could not write campaign_metrics.csv: {e}")

    # data_requests.json stable pointer
    dr_payload = {
        "run_id":         state["run_id"],
        "generated_at":   state["generated_at"],
        "total_requests": len(state["data_requests"]),
        "requests":       state["data_requests"],
    }
    (latest_dir / "data_requests.json").write_text(
        json.dumps(dr_payload, indent=2, default=str), encoding="utf-8")

    # recommendations.json stable pointer
    rec_payload = {
        "run_id":          state["run_id"],
        "generated_at":    state["generated_at"],
        "top_recommendations": recommendations,
    }
    (latest_dir / "recommendations.json").write_text(
        json.dumps(rec_payload, indent=2, default=str), encoding="utf-8")
    log.info(f"State latest pointers written to {latest_dir}")
