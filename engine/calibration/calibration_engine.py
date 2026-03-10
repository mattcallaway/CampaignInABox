"""
engine/calibration/calibration_engine.py — Prompt 15

Master orchestrator for the Campaign Calibration & Learning Engine.

Entry point:
    run_calibration(project_root, contest_id, run_id, logger=None)

Coordinates:
  1. Historical election parsing (reuses historical_parser.py from Prompt 11)
  2. Voter intelligence summaries (from Prompt 12 derived outputs)
  3. Campaign runtime data (from Prompt 14 War Room)
  4. Turnout calibrator
  5. Persuasion calibrator
  6. Turnout lift calibrator
  7. Forecast accuracy tracker
  8. Model parameter registry update
  9. Calibration report generation
  10. State store update

Security: Never reads or writes voter-level raw records.
Only precinct-level aggregates are used.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

log = logging.getLogger(__name__)


def _g(d: Any, *keys, default=None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _latest_file(root: Path, pattern: str) -> Optional[Path]:
    try:
        hits = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return next((h for h in hits if ".gitkeep" not in h.name), None)
    except Exception:
        return None


def _read_csv(path: Optional[Path]) -> pd.DataFrame:
    if path and path.exists():
        try:
            return pd.read_csv(path)
        except Exception as e:
            log.warning(f"Could not read {path}: {e}")
    return pd.DataFrame()


def _read_json(path: Optional[Path]) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Could not read JSON {path}: {e}")
    return {}


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_historical_results(root: Path, logger) -> pd.DataFrame:
    """Load or parse historical precinct results."""
    # Check if already parsed
    cached = root / "derived" / "calibration" / "historical_precinct_results.csv"
    if cached.exists():
        df = _read_csv(cached)
        logger.info(f"[CALIB_ENGINE] Loaded {len(df)} historical precinct-year records from cache")
        return df

    # Parse fresh
    try:
        from engine.calibration.historical_parser import parse_all_historical
        df = parse_all_historical(logger=logger)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.warning(f"[CALIB_ENGINE] Historical parsing failed: {e}")
        return pd.DataFrame()


def _load_voter_intelligence_summary(root: Path) -> dict:
    """Load precinct-level voter intelligence (Prompt 12 outputs). No individual records."""
    summary = {}
    # Precinct persuasion scores (aggregated)
    ps_path = _latest_file(root / "derived" / "voter_models", "*precinct_persuasion*.csv")
    tps_path = _latest_file(root / "derived" / "voter_models", "*precinct_tps*.csv")
    if ps_path:
        summary["precinct_persuasion_df"] = _read_csv(ps_path)
    if tps_path:
        summary["precinct_tps_df"] = _read_csv(tps_path)
    # Universe sizes from voter_universes (aggregate counts only)
    gotv_path = _latest_file(root / "derived" / "voter_universes", "*gotv*.csv")
    pers_path = _latest_file(root / "derived" / "voter_universes", "*persuasion*.csv")
    summary["gotv_universe_size"] = len(_read_csv(gotv_path)) if gotv_path else 0
    summary["persuasion_universe_size"] = len(_read_csv(pers_path)) if pers_path else 0
    return summary


def _load_runtime_data(root: Path, cfg: dict) -> dict:
    """Load War Room runtime data (Prompt 14). Returns precinct-aggregated summary."""
    runtime = {}
    try:
        from engine.war_room.runtime_loader import get_runtime_summary
        runtime = get_runtime_summary(cfg)
    except Exception as e:
        log.debug(f"[CALIB_ENGINE] Runtime data not available: {e}")
    return runtime


def _load_campaign_config(root: Path) -> dict:
    try:
        import yaml
        p = root / "config" / "campaign_config.yaml"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_calibration(
    project_root: Path,
    contest_id: str = "",
    run_id: str = "",
    logger=None,
) -> dict:
    """
    Run the full calibration pipeline.

    Returns a calibration result dict.
    Writes derived/calibration/ outputs and calibration report.
    """
    _log = logger or log
    root = Path(project_root)
    now = datetime.utcnow().isoformat()

    calib_dir = root / "derived" / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)
    report_dir = root / "reports" / "calibration"
    report_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = root / "reports" / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    _log.info(f"[CALIB_ENGINE] Starting calibration | run_id={run_id} | contest={contest_id}")

    # ── Load all data sources ─────────────────────────────────────────────────
    cfg = _load_campaign_config(root)
    hist_df     = _load_historical_results(root, _log)
    vi_summary  = _load_voter_intelligence_summary(root)
    runtime     = _load_runtime_data(root, cfg)

    # Load precinct model for enrichment
    pm_path = _latest_file(root / "derived" / "precinct_models", "*.csv")
    precinct_model = _read_csv(pm_path)

    sources_used = []
    if not hist_df.empty:
        sources_used.append("historical_elections")
    if vi_summary.get("gotv_universe_size", 0) > 0:
        sources_used.append("voter_turnout_history")
    if runtime.get("has_any"):
        sources_used.append("campaign_runtime_data")

    _log.info(f"[CALIB_ENGINE] Data sources: {sources_used}")

    # ── Turnout calibration ───────────────────────────────────────────────────
    from engine.calibration.turnout_calibrator import calibrate_turnout
    turnout_params = calibrate_turnout(
        hist_df=hist_df,
        precinct_model=precinct_model,
        vi_summary=vi_summary,
        root=root,
        logger=_log,
    )

    # ── Persuasion calibration ────────────────────────────────────────────────
    from engine.calibration.persuasion_calibrator import calibrate_persuasion
    persuasion_params = calibrate_persuasion(
        hist_df=hist_df,
        runtime=runtime,
        vi_summary=vi_summary,
        root=root,
        logger=_log,
    )

    # ── Turnout lift calibration ──────────────────────────────────────────────
    from engine.calibration.turnout_lift_calibrator import calibrate_turnout_lift
    turnout_lift_params = calibrate_turnout_lift(
        hist_df=hist_df,
        runtime=runtime,
        precinct_model=precinct_model,
        root=root,
        logger=_log,
    )

    # ── Forecast accuracy tracking ────────────────────────────────────────────
    from engine.calibration.forecast_accuracy import track_forecast_accuracy
    accuracy_result = track_forecast_accuracy(
        hist_df=hist_df,
        precinct_model=precinct_model,
        root=root,
        run_id=run_id,
        logger=_log,
    )

    # ── Reuse existing model_calibrator for combined parameter estimation ─────
    from engine.calibration.model_calibrator import calibrate, load_calibrated_params
    combined_params = calibrate(
        hist_df=hist_df if not hist_df.empty else None,
        precinct_model=precinct_model if not precinct_model.empty else None,
        logger=_log,
    )

    # ── Build parameter registry ──────────────────────────────────────────────
    _update_model_parameters_yaml(root, combined_params, turnout_params, persuasion_params, turnout_lift_params)

    # ── Forecast comparison ───────────────────────────────────────────────────
    _write_forecast_comparison(
        root=root, run_id=run_id, combined_params=combined_params,
        turnout_params=turnout_params, persuasion_params=persuasion_params,
        turnout_lift_params=turnout_lift_params, calib_dir=calib_dir,
    )

    # ── Assemble result ───────────────────────────────────────────────────────
    calibration_status = "active" if sources_used else "prior_only"
    confidence = combined_params.get("calibration_confidence", "none")

    result = {
        "run_id":              run_id,
        "contest_id":          contest_id,
        "generated_at":        now,
        "calibration_status":  calibration_status,
        "calibration_confidence": confidence,
        "calibration_sources": sources_used,
        "n_historical_records": len(hist_df),
        "n_historical_elections": hist_df["year"].nunique() if not hist_df.empty else 0,
        "n_precincts_historical": hist_df["canonical_precinct_id"].nunique() if not hist_df.empty else 0,
        "gotv_universe_size":   vi_summary.get("gotv_universe_size", 0),
        "persuasion_universe_size": vi_summary.get("persuasion_universe_size", 0),
        "runtime_has_data":     runtime.get("has_any", False),
        "turnout_parameters":   turnout_params,
        "persuasion_parameters": persuasion_params,
        "turnout_lift_parameters": turnout_lift_params,
        "combined_parameters":  combined_params,
        "forecast_accuracy":    accuracy_result,
    }

    # Write calibration summary JSON
    summary_path = calib_dir / f"{run_id}__calibration_summary.json" if run_id else calib_dir / "calibration_summary.json"
    summary_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    # Also stable latest pointer
    (calib_dir / "calibration_summary.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    _log.info(f"[CALIB_ENGINE] Calibration summary written → {summary_path.name}")

    # ── Reports ───────────────────────────────────────────────────────────────
    _write_calibration_report(result, run_id, report_dir)
    _write_calibration_diagnostics(result, hist_df, precinct_model, run_id, qa_dir)

    # ── State store update ────────────────────────────────────────────────────
    _update_state_store(root, result)

    _log.info(
        f"[CALIB_ENGINE] Done | status={calibration_status} | "
        f"confidence={confidence} | sources={sources_used}"
    )
    return result


# ── Model parameter registry update ──────────────────────────────────────────

def _update_model_parameters_yaml(
    root: Path, combined: dict, turnout: dict, persuasion: dict, lift: dict
) -> None:
    """Append calibration section to config/model_parameters.yaml."""
    try:
        import yaml
        cfg_path = root / "config" / "model_parameters.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        cfg["calibration"] = {
            "calibration_status": combined.get("calibration_status", "prior_only"),
            "calibration_confidence": combined.get("calibration_confidence", "none"),
            "turnout_lift_per_contact": lift.get("turnout_lift_per_contact", 0.06),
            "turnout_lift_variance": lift.get("turnout_lift_variance", 0.02),
            "persuasion_lift_per_contact": persuasion.get("persuasion_lift_per_contact", 0.06),
            "persuasion_variance": persuasion.get("persuasion_variance", 0.025),
            "baseline_turnout_probability": turnout.get("baseline_turnout_probability", 0.45),
            "turnout_variance": turnout.get("turnout_variance", 0.08),
            "calibrated_at": datetime.utcnow().isoformat(),
        }

        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        log.info("[CALIB_ENGINE] model_parameters.yaml updated with calibration section")
    except Exception as e:
        log.warning(f"[CALIB_ENGINE] Could not update model_parameters.yaml: {e}")


# ── Forecast comparison ───────────────────────────────────────────────────────

def _write_forecast_comparison(
    root: Path, run_id: str, combined_params: dict,
    turnout_params: dict, persuasion_params: dict, turnout_lift_params: dict,
    calib_dir: Path,
) -> None:
    """Write forecast comparison CSV — baseline vs calibrated forecast."""
    try:
        import pandas as pd
        prior_turnout_lift = 0.06
        prior_persuasion_lift = 0.06
        prior_baseline_turnout = 0.45

        cal_turnout_lift = turnout_lift_params.get("turnout_lift_per_contact", prior_turnout_lift)
        cal_persuasion_lift = persuasion_params.get("persuasion_lift_per_contact", prior_persuasion_lift)
        cal_baseline_turnout = turnout_params.get("baseline_turnout_probability", prior_baseline_turnout)

        rows = [
            {
                "metric": "baseline_turnout_probability",
                "baseline_forecast": prior_baseline_turnout,
                "calibrated_forecast": cal_baseline_turnout,
                "difference": round(cal_baseline_turnout - prior_baseline_turnout, 5),
                "source": turnout_params.get("method", "prior"),
            },
            {
                "metric": "turnout_lift_per_contact",
                "baseline_forecast": prior_turnout_lift,
                "calibrated_forecast": cal_turnout_lift,
                "difference": round(cal_turnout_lift - prior_turnout_lift, 5),
                "source": turnout_lift_params.get("method", "prior"),
            },
            {
                "metric": "persuasion_lift_per_contact",
                "baseline_forecast": prior_persuasion_lift,
                "calibrated_forecast": cal_persuasion_lift,
                "difference": round(cal_persuasion_lift - prior_persuasion_lift, 5),
                "source": persuasion_params.get("method", "prior"),
            },
        ]
        df = pd.DataFrame(rows)
        fname = f"{run_id}__forecast_comparison.csv" if run_id else "forecast_comparison.csv"
        path = calib_dir / fname
        df.to_csv(path, index=False)
        log.info(f"[CALIB_ENGINE] Forecast comparison → {path.name}")
    except Exception as e:
        log.warning(f"[CALIB_ENGINE] Could not write forecast comparison: {e}")


# ── State store update ────────────────────────────────────────────────────────

def _update_state_store(root: Path, result: dict) -> None:
    """Patch derived/state/latest/campaign_state.json with calibration fields."""
    latest_state_path = root / "derived" / "state" / "latest" / "campaign_state.json"
    if not latest_state_path.exists():
        return
    try:
        state = json.loads(latest_state_path.read_text(encoding="utf-8"))
        # Add calibration_status top-level
        state["calibration_status"] = result.get("calibration_status", "prior_only")
        state["calibration_sources"] = result.get("calibration_sources", [])
        # Enrich model_summary
        ms = state.setdefault("model_summary", {})
        ms["calibration_used"] = result.get("calibration_status") == "active"
        ms["calibration_confidence"] = result.get("calibration_confidence", "none")
        ms["calibration_sources"] = result.get("calibration_sources", [])
        ms["calibrated_turnout_lift"] = _g(result, "turnout_lift_parameters", "turnout_lift_per_contact")
        ms["calibrated_persuasion_lift"] = _g(result, "persuasion_parameters", "persuasion_lift_per_contact")
        ms["calibrated_baseline_turnout"] = _g(result, "turnout_parameters", "baseline_turnout_probability")
        state["model_summary"] = ms
        latest_state_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        log.info("[CALIB_ENGINE] Campaign state store updated with calibration fields")
    except Exception as e:
        log.warning(f"[CALIB_ENGINE] Could not update state store: {e}")


# ── Report writers ────────────────────────────────────────────────────────────

def _write_calibration_report(result: dict, run_id: str, report_dir: Path) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    tp = result.get("turnout_parameters", {})
    pp = result.get("persuasion_parameters", {})
    lp = result.get("turnout_lift_parameters", {})
    acc = result.get("forecast_accuracy", {})

    lines = [
        f"# Calibration Report — Prompt 15",
        f"**Run:** `{run_id}`  **Generated:** {now}",
        f"**Status:** {result.get('calibration_status','—')} | **Confidence:** {result.get('calibration_confidence','—')}",
        "",
        "## Data Sources Used",
        "",
        f"| Source | Available |",
        f"|--------|-----------|",
        f"| Historical Elections | {'✅ ' + str(result.get('n_historical_elections', 0)) + ' election(s), ' + str(result.get('n_historical_records', 0)) + ' records' if 'historical_elections' in result.get('calibration_sources', []) else '❌ None found'} |",
        f"| Voter Turnout History | {'✅ ' + str(result.get('gotv_universe_size', 0)) + ' GOTV / ' + str(result.get('persuasion_universe_size', 0)) + ' persuasion' if 'voter_turnout_history' in result.get('calibration_sources', []) else '❌ Not available'} |",
        f"| Campaign Runtime Data | {'✅ Real field/volunteer/budget data' if result.get('runtime_has_data') else '❌ No runtime data yet'} |",
        "",
        "## Parameter Estimates",
        "",
        f"| Parameter | Estimate | Confidence | Method |",
        f"|-----------|----------|------------|--------|",
        f"| Baseline Turnout Probability | {tp.get('baseline_turnout_probability', 0.45):.3f} | {tp.get('confidence', 'none')} | {tp.get('method', 'prior')} |",
        f"| Turnout Lift per Contact | {lp.get('turnout_lift_per_contact', 0.06):.4f} | {lp.get('confidence', 'none')} | {lp.get('method', 'prior')} |",
        f"| Turnout Lift Variance | {lp.get('turnout_lift_variance', 0.02):.4f} | — | — |",
        f"| Persuasion Lift per Contact | {pp.get('persuasion_lift_per_contact', 0.06):.4f} | {pp.get('confidence', 'none')} | {pp.get('method', 'prior')} |",
        f"| Persuasion Variance | {pp.get('persuasion_variance', 0.025):.4f} | — | — |",
        "",
        "## Forecast Comparison",
        "",
        "Calibrated parameters vs. prior assumptions:",
        "",
        f"| Metric | Prior | Calibrated | Δ |",
        f"|--------|-------|------------|---|",
        f"| Baseline Turnout | 0.450 | {tp.get('baseline_turnout_probability', 0.45):.3f} | {tp.get('baseline_turnout_probability', 0.45) - 0.45:+.3f} |",
        f"| Turnout Lift/Contact | 0.0600 | {lp.get('turnout_lift_per_contact', 0.06):.4f} | {lp.get('turnout_lift_per_contact', 0.06) - 0.06:+.4f} |",
        f"| Persuasion Lift/Contact | 0.0600 | {pp.get('persuasion_lift_per_contact', 0.06):.4f} | {pp.get('persuasion_lift_per_contact', 0.06) - 0.06:+.4f} |",
        "",
    ]

    if acc.get("records"):
        lines += [
            "## Forecast Accuracy (Historical vs Actual)",
            "",
            f"| Contest | Predicted | Actual | Error |",
            f"|---------|-----------|--------|-------|",
        ]
        for rec in acc["records"][:10]:
            lines.append(
                f"| {rec.get('contest', '')} | {rec.get('predicted', 'N/A')} | "
                f"{rec.get('actual', 'N/A')} | {rec.get('error', 'N/A')} |"
            )
        lines.append("")

    lines += [
        "---",
        "> [!NOTE]",
        "> Confidence improves with more historical elections and real field data.",
        "> Enter canvassing results in the War Room to upgrade from ESTIMATED → REAL.",
    ]

    fname = f"{run_id}__calibration_report.md" if run_id else "calibration_report.md"
    (report_dir / fname).write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[CALIB_ENGINE] Calibration report written → {fname}")


def _write_calibration_diagnostics(
    result: dict, hist_df: pd.DataFrame, precinct_model: pd.DataFrame,
    run_id: str, qa_dir: Path
) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    n_hist_prec = hist_df["canonical_precinct_id"].nunique() if not hist_df.empty else 0
    n_model_prec = len(precinct_model) if not precinct_model.empty else 0
    match_rate = (n_hist_prec / n_model_prec) if n_model_prec > 0 and n_hist_prec > 0 else 0.0

    lines = [
        f"# Calibration Diagnostics — Prompt 15",
        f"**Run:** `{run_id}`  **Generated:** {now}",
        "",
        "## Data Coverage",
        "",
        f"| Check | Value |",
        f"|-------|-------|",
        f"| Historical contests | {result.get('n_historical_elections', 0)} |",
        f"| Historical precinct-year records | {result.get('n_historical_records', 0)} |",
        f"| Precincts in historical data | {n_hist_prec} |",
        f"| Precincts in precinct model | {n_model_prec} |",
        f"| Historical precinct match rate | {match_rate:.1%} |",
        f"| GOTV universe size | {result.get('gotv_universe_size', 0):,} |",
        f"| Persuasion universe size | {result.get('persuasion_universe_size', 0):,} |",
        f"| Runtime data available | {'✅ Yes' if result.get('runtime_has_data') else '❌ No'} |",
        "",
        "## Confidence Assessment",
        "",
        f"**Calibration Status:** {result.get('calibration_status', '—')}",
        f"**Confidence Level:** {result.get('calibration_confidence', '—')}",
        "",
        "| Level | Requirement |",
        "|-------|-------------|",
        "| high | ≥5 elections, ≥100 precincts |",
        "| medium | ≥3 elections, ≥50 precincts |",
        "| low | ≥1 election |",
        "| none | No historical data |",
        "",
        "## Recommendations",
        "",
    ]

    if result.get("n_historical_elections", 0) == 0:
        lines.append("- ❌ Add historical election files to `data/elections/CA/<county>/<year>/detail.xls`")
    elif result.get("n_historical_elections", 0) < 3:
        lines.append(f"- ⚠️ Only {result.get('n_historical_elections')} election(s) — add more history for medium confidence")

    if not result.get("runtime_has_data"):
        lines.append("- ⚠️ No campaign runtime data — enter field results in War Room to calibrate turnout lift")

    if match_rate < 0.5 and n_hist_prec > 0:
        lines.append(f"- ⚠️ Low precinct match rate ({match_rate:.0%}) — check canonical precinct IDs match between model and historical data")

    if result.get("calibration_status") == "active":
        lines.append("- ✅ Calibration is active and feeding into model parameters")

    lines += ["", "---", "*Calibration diagnostics by engine/calibration/calibration_engine.py — Prompt 15*"]

    fname = f"{run_id}__calibration_diagnostics.md" if run_id else "calibration_diagnostics.md"
    (qa_dir / fname).write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[CALIB_ENGINE] Calibration diagnostics written → {fname}")
