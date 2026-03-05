"""
scripts/strategy/strategy_generator.py

Campaign Strategy Generator (Prompt 8) — loads derived pipeline outputs
and produces a campaign-ready Strategy Pack with 7 artifacts.

Design principles:
- Runs simulation + ops inline if pipeline outputs not already present.
- forecast_mode: deterministic | monte_carlo | both.
- Deterministic: stable sorting + fixed seeds.
- Graceful degradation: runs with only targets + turfs; marks gaps.
- Logging contract: updates pathway.json and needs.yaml.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_TOP_N_TARGETS  = 100
DEFAULT_TOP_N_TURFS    = 30
DEFAULT_WEEKS          = 4


# ══════════════════════════════════════════════════════════════════════════════
# Input Loader
# ══════════════════════════════════════════════════════════════════════════════
def _find_latest(root: Path, pattern: str) -> Optional[Path]:
    """Return the most-recently-modified file matching glob pattern."""
    matches = sorted(root.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _sha256(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return "unknown"


def load_inputs(contest_id: str, run_id: Optional[str] = None) -> dict:
    """
    Load derived artifacts for contest_id.
    Returns dict with keys: dataframes + meta about what was found/missing.
    """
    derived = BASE_DIR / "derived"

    def try_load(search_root: Path, *patterns: str):
        for pat in patterns:
            f = _find_latest(search_root, pat)
            if f:
                try:
                    return pd.read_csv(f), f
                except Exception:
                    pass
        return pd.DataFrame(), None

    # ── Required inputs ───────────────────────────────────────────────────────
    # Try campaign_targets first, then precinct_models (which is where the pipeline actually writes)
    targets_df, targets_path = try_load(
        derived / "campaign_targets",
        f"*{contest_id}*target_ranking*.csv",
        "*target_ranking*.csv",
        "*scored_model*.csv",
    )
    if targets_df.empty:
        # Fallback: pipeline writes scored models to derived/precinct_models/
        targets_df, targets_path = try_load(
            derived / "precinct_models",
            "*precinct_model*.csv",
            "*.csv",
        )
    turfs_df, turfs_path = try_load(
        derived / "turfs",
        f"*{contest_id}*turfs*.csv",
        "*top_30_walk_turfs*.csv",
        f"*{contest_id}*.csv",
    )
    forecasts_df, forecasts_path = try_load(
        derived / "forecasts",
        f"*{contest_id}*forecast*.csv",
        "*scenario_forecasts*.csv",
    )
    universes_df, universes_path = try_load(
        derived / "universes",
        f"*{contest_id}*universe*.csv",
        "*precinct_universes*.csv",
    )

    # ── Optional (v3) inputs ──────────────────────────────────────────────────
    regions_df, regions_path = try_load(
        derived / "ops",
        f"*{contest_id}*region*.csv",
        "*regions*.csv",
    )
    field_plan_df, field_plan_path = try_load(
        derived / "ops",
        f"*{contest_id}*field_plan*.csv",
        "*field_plan*.csv",
    )
    sim_df, sim_path = try_load(
        derived / "ops",
        f"*{contest_id}*simulation*.csv",
        "*simulation_results*.csv",
    )
    # Also try forecasts dir for simulation
    if sim_df.empty:
        sim_df, sim_path = try_load(
            derived / "forecasts",
            f"*{contest_id}*simulation*.csv",
        )

    # ── Build hash map ────────────────────────────────────────────────────────
    found, missing = {}, []
    def _register(key, path):
        if path:
            found[key] = {"path": str(path), "hash": _sha256(path)}
        else:
            missing.append(key)

    _register("target_ranking", targets_path)
    _register("walk_turfs",     turfs_path)
    _register("scenario_forecasts", forecasts_path)
    _register("precinct_universes", universes_path)
    _register("regions",        regions_path)
    _register("field_plan",     field_plan_path)
    _register("simulation_results", sim_path)

    # ── Determine derived_mode ────────────────────────────────────────────────
    has_required = not targets_df.empty
    has_ops      = not field_plan_df.empty and not regions_df.empty
    has_voter    = universes_path is not None

    if has_required and has_ops and has_voter:
        derived_mode = "full"
    elif has_required and has_ops:
        derived_mode = "partial"
    elif has_required:
        derived_mode = "degraded"
    else:
        derived_mode = "blocked"

    return {
        "targets":    targets_df,
        "turfs":      turfs_df,
        "forecasts":  forecasts_df,
        "universes":  universes_df,
        "regions":    regions_df,
        "field_plan": field_plan_df,
        "simulations": sim_df,
        "inputs_found":   found,
        "inputs_missing": missing,
        "derived_mode":   derived_mode,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Contest Mode Inference
# ══════════════════════════════════════════════════════════════════════════════
def infer_contest_mode(targets: pd.DataFrame, contest_mode: str = "auto") -> tuple[str, str]:
    """Returns (final_mode, reason)."""
    if contest_mode.lower() != "auto":
        return contest_mode.lower(), f"explicit override: {contest_mode}"

    cols = set(targets.columns)
    if "yes_pct" in cols or "YesPct" in str(cols):
        return "measure", "inferred MEASURE (yes_pct column present)"
    if "target_choice_pct" in cols or any("choice" in c.lower() for c in cols):
        return "candidate", "inferred CANDIDATE (target_choice_pct/choice column)"
    if "support_pct" in cols:
        # Default to measure since support_pct is generic
        return "measure", "defaulted to MEASURE (support_pct only)"
    return "measure", "defaulted to MEASURE (no mode indicators found)"


# ══════════════════════════════════════════════════════════════════════════════
# Win Path
# ══════════════════════════════════════════════════════════════════════════════
def compute_win_path(targets: pd.DataFrame, forecasts: pd.DataFrame,
                     simulations: pd.DataFrame, contest_mode: str) -> dict:
    result = {
        "baseline_turnout":    None,
        "baseline_support":    None,
        "baseline_margin":     None,
        "best_case_margin":    None,
        "worst_case_margin":   None,
        "win_number":          None,
        "win_probability":     None, # Added for Prompt 8
        "notes":               [],
    }

    # Aggregate from targets
    if not targets.empty:
        registered = pd.to_numeric(targets.get("registered", pd.Series(dtype=float)), errors="coerce").sum()
        ballots    = pd.to_numeric(targets.get("ballots_cast", pd.Series(dtype=float)), errors="coerce").sum()
        support    = pd.to_numeric(targets.get("support_pct", pd.Series(dtype=float)), errors="coerce")

        if ballots > 0:
            result["baseline_turnout"] = round(float(ballots / registered), 4) if registered > 0 else None
            result["baseline_support"] = round(float(support.mean()), 4) if not support.empty else None
            est_support_votes = ballots * (result["baseline_support"] or 0)
            est_oppose_votes  = ballots - est_support_votes
            result["baseline_margin"]  = round(float(est_support_votes - est_oppose_votes), 0)

            # Win number
            if contest_mode == "measure":
                result["win_number"] = round(float(ballots * 0.5 + 1), 0)
            else:
                result["win_number"] = round(float(ballots * 0.5 + 1), 0)
                result["notes"].append("Win number for candidate: may need min-votes heuristic if multi-candidate")

    # Scenario range from simulations or forecasts
    for sdf in [simulations, forecasts]:
        if sdf.empty:
            continue
        margin_col = next((c for c in sdf.columns if "margin" in c.lower()), None)
        if margin_col:
            margins = pd.to_numeric(sdf[margin_col], errors="coerce").dropna()
            if not margins.empty:
                result["best_case_margin"]  = round(float(margins.max()), 0)
                result["worst_case_margin"] = round(float(margins.min()), 0)
        # If simulations has a win_probability column, use it
        if "win_probability" in sdf.columns and not sdf["win_probability"].empty:
            result["win_probability"] = sdf["win_probability"].iloc[0] # Assuming it's a single value
        break

    if result["baseline_turnout"] is None:
        result["notes"].append("Insufficient data for turnout estimate")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Focus Areas
# ══════════════════════════════════════════════════════════════════════════════
def compute_focus(targets: pd.DataFrame, regions: pd.DataFrame) -> dict:
    """Stable top-N selection by multiple criteria."""
    result = {
        "top_persuasion": pd.DataFrame(),
        "top_turnout":    pd.DataFrame(),
        "top_target":     pd.DataFrame(),
        "top_regions":    [],
    }
    if targets.empty:
        return result

    df = targets.copy()

    # Attach region_id if available
    if not regions.empty and "canonical_precinct_id" in df.columns and "canonical_precinct_id" in regions.columns:
        df = df.merge(regions[["canonical_precinct_id", "region_id"]], on="canonical_precinct_id", how="left")

    # Sort stably (then by id as tiebreaker)
    id_col = "canonical_precinct_id" if "canonical_precinct_id" in df.columns else df.columns[0]

    if "target_score" in df.columns:
        result["top_target"] = (df.sort_values(["target_score", id_col], ascending=[False, True])
                                   .head(DEFAULT_TOP_N_TARGETS))
    else:
        result["top_target"] = df.head(DEFAULT_TOP_N_TARGETS)

    if "persuasion_potential" in df.columns:
        result["top_persuasion"] = (df.sort_values(["persuasion_potential", id_col], ascending=[False, True])
                                       .head(30))

    if "turnout_opportunity" in df.columns:
        result["top_turnout"] = (df.sort_values(["turnout_opportunity", id_col], ascending=[False, True])
                                    .head(30))

    # Top regions by support concentration
    if "region_id" in df.columns and not df["region_id"].isna().all():
        agg_cols = {}
        if "target_score" in df.columns:
            agg_cols["avg_target_score"] = ("target_score", "mean")
        if "registered" in df.columns:
            agg_cols["total_registered"] = ("registered", "sum")
        if agg_cols:
            rg = df.groupby("region_id").agg(**agg_cols).reset_index()
            sort_col = "avg_target_score" if "avg_target_score" in rg.columns else rg.columns[1]
            rg = rg.sort_values(sort_col, ascending=False)
            result["top_regions"] = rg.head(7).to_dict("records")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Turf Assignment
# ══════════════════════════════════════════════════════════════════════════════
def assign_turf_purpose(turfs: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Assign a turf_purpose (persuasion|turnout|mixed) to each turf."""
    if turfs.empty:
        return turfs
    df = turfs.copy()
    if "turf_purpose" not in df.columns:
        # Simple heuristic from avg_target_score
        if "avg_target_score" in df.columns:
            score = pd.to_numeric(df["avg_target_score"], errors="coerce")
            df["turf_purpose"] = score.apply(
                lambda s: "persuasion" if s >= 0.6 else ("turnout" if s <= 0.35 else "mixed")
                if pd.notna(s) else "mixed"
            )
        else:
            df["turf_purpose"] = "mixed"
    return df


# ══════════════════════════════════════════════════════════════════════════════
# Field Pace
# ══════════════════════════════════════════════════════════════════════════════
def compute_field_pace(field_plan: pd.DataFrame, ops_config: dict, weeks: int = DEFAULT_WEEKS,
                       start_date: Optional[datetime.date] = None) -> pd.DataFrame:
    """Produce a weekly field pace table."""
    if start_date is None:
        start_date = datetime.date.today()

    # Derive totals
    if not field_plan.empty:
        shifts_total = pd.to_numeric(field_plan.get("shifts_needed", pd.Series(dtype=float)),
                                     errors="coerce").sum()
        vols_total   = pd.to_numeric(field_plan.get("volunteers_needed", pd.Series(dtype=float)),
                                     errors="coerce").sum()
        contacts_total = pd.to_numeric(field_plan.get("expected_contacts", pd.Series(dtype=float)),
                                       errors="coerce").sum()
        net_gain_total = pd.to_numeric(field_plan.get("expected_net_gain", pd.Series(dtype=float)),
                                       errors="coerce").sum()
        source = "ops"
    else:
        # Estimated from config
        doors_per_shift  = ops_config.get("doors_per_hour", 15) * ops_config.get("hours_per_shift", 3)
        contact_rate     = ops_config.get("contact_rate", 0.25)
        shifts_total     = ops_config.get("target_shift_count_per_weekend", 5) * weeks
        vols_total       = ops_config.get("volunteers_per_turf_per_weekend", 2) * 10 * weeks
        contacts_total   = shifts_total * doors_per_shift * contact_rate
        net_gain_total   = 0
        source = "estimated"

    rows = []
    for i in range(weeks):
        wstart = start_date + datetime.timedelta(weeks=i)
        frac   = 1.0 / weeks
        rows.append({
            "week": i + 1,
            "week_start":              wstart.isoformat(),
            "doors_goal":              round(shifts_total * ops_config.get("doors_per_hour", 15)
                                              * ops_config.get("hours_per_shift", 3) * frac),
            "shifts_goal":             round(shifts_total * frac),
            "volunteers_goal":         max(1, round(vols_total * frac)),
            "contacts_goal":           round(contacts_total * frac),
            "expected_net_gain_votes": round(net_gain_total * frac, 1) if net_gain_total else "N/A",
            "notes":                   source if i == 0 else "",
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Universe Guidance
# ══════════════════════════════════════════════════════════════════════════════
def universe_guidance(universes: pd.DataFrame, voter_exports_present: bool) -> str:
    if universes.empty:
        return "Universe data not available — run pipeline with voter file to unlock segment-specific guidance."

    lines = ["**Messaging & Universe Guidance**\n"]
    if "universe_name" in universes.columns:
        counts = universes["universe_name"].value_counts()
        for uni, cnt in counts.items():
            if "persuasion" in str(uni).lower():
                lines.append(f"- **{uni}** ({cnt} precincts): talk to persuadables; focus on top issues and shared values.")
            elif "turnout" in str(uni).lower() or "mobilization" in str(uni).lower():
                lines.append(f"- **{uni}** ({cnt} precincts): supporters; focus on making a plan to vote.")
            else:
                lines.append(f"- **{uni}** ({cnt} precincts): mixed contact approach.")
    if voter_exports_present:
        lines.append("\n✅ Voter-level universe exports available — see `derived/universes/` for walk lists.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Output Writers
# ══════════════════════════════════════════════════════════════════════════════
def _recommended_strategy(win_path: dict, simulations: pd.DataFrame) -> str:
    """Determine a recommended strategy based on win path and simulation results."""
    wp = win_path
    win_prob = wp.get("win_probability")
    baseline_margin = wp.get("baseline_margin")
    best_case_margin = wp.get("best_case_margin")
    worst_case_margin = wp.get("worst_case_margin")

    if win_prob is not None:
        if win_prob >= 0.75:
            return "Strong position. Focus on turnout and protecting the lead."
        elif win_prob >= 0.55:
            return "Competitive race. Balanced approach: persuasion for undecideds, turnout for supporters."
        elif win_prob >= 0.35:
            return "Uphill battle. Aggressive persuasion needed, identify and mobilize every supporter."
        else:
            return "Challenging. Re-evaluate strategy, focus on high-impact persuasion and targeted turnout."
    elif baseline_margin is not None:
        if baseline_margin > 0 and best_case_margin > 0:
            return "Leading. Focus on turnout and maintaining momentum."
        elif baseline_margin < 0 and worst_case_margin < 0:
            return "Trailing. Aggressive persuasion and voter registration efforts are critical."
        else:
            return "Tight race. Balanced approach: persuasion for undecideds, turnout for supporters."
    return "Strategy recommendation not available due to insufficient data."


def _build_strategy_summary(
    contest_id: str, contest_mode: str, mode_reason: str, derived_mode: str,
    win_path: dict, top15_md: str, turfs_md: str, reg_lines: str, cap_text: str,
    uni_guidance: str, gaps: list, pace_df: pd.DataFrame,
    win_probability: Optional[float] = None, median_margin: Optional[float] = None,
) -> str:
    """Builds the full 9-section STRATEGY_SUMMARY.md content."""
    mode_badge = {"full": "✅ Full", "partial": "⚠️ Partial", "degraded": "🔴 Degraded", "blocked": "❌ Blocked"}
    completeness = mode_badge.get(derived_mode, "?")

    def _fmt(v):
        return f"{v:,.0f}" if isinstance(v, (int, float)) and v is not None else str(v or "N/A")

    def _pct(v):
        return f"{v:.2%}" if v is not None else "N/A"

    summary_lines = [
        f"# Campaign Strategy Pack: {contest_id}",
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Contest Mode:** `{contest_mode.upper()}` ({mode_reason})",
        f"**Data Completeness:** {completeness} (Derived Mode: `{derived_mode}`)",
        "",
        "## 1. Executive Summary",
        _recommended_strategy(win_path, pd.DataFrame()), # Pass empty df as simulations are not directly used here
        "",
        "## 2. Win Path & Forecasts",
        f"- **Baseline Turnout:** {_pct(win_path['baseline_turnout'])} (estimated)",
        f"- **Baseline Support:** {_pct(win_path['baseline_support'])} (estimated)",
        f"- **Baseline Margin:** {_fmt(win_path['baseline_margin'])} votes",
        f"- **Win Number:** {_fmt(win_path['win_number'])} votes needed to win",
    ]

    if win_probability is not None:
        summary_lines.append(f"- **Win Probability:** {win_probability:.1%} (from simulation)")
    if median_margin is not None:
        summary_lines.append(f"- **Median Margin:** {_fmt(median_margin)} votes (from simulation)")

    summary_lines.extend([
        f"- **Best Case Margin:** {_fmt(win_path['best_case_margin'])} votes",
        f"- **Worst Case Margin:** {_fmt(win_path['worst_case_margin'])} votes",
        "",
        "## 3. Top Target Precincts",
        "These precincts have the highest overall target scores, indicating a strong combination of persuasion potential and turnout opportunity.",
        top15_md,
        "",
        "## 4. Top Walk Turfs",
        "These turfs are recommended for field operations, prioritized by expected impact.",
        turfs_md,
        "",
        "## 5. Focus Regions",
        "Key regions identified for strategic focus based on target concentration.",
        reg_lines,
        "",
        "## 6. Field Capacity & Pace",
        "Recommended weekly pace for field operations to meet campaign goals.",
        cap_text,
        "",
        "## 7. Messaging & Universe Guidance",
        uni_guidance,
        "",
        "## 8. Data Gaps & Recommendations",
        "The following inputs were not found, potentially limiting the completeness of this strategy pack:",
        "\n".join(f"- `{g}`" for g in gaps) if gaps else "- None ✅",
        "",
        "## 9. Strategy Pack Contents",
        "This pack includes the following files:",
        "- `STRATEGY_SUMMARY.md`: This document.",
        "- `STRATEGY_META.json`: Machine-readable metadata about this pack.",
        "- `TOP_TARGETS.csv`: Detailed list of top target precincts.",
        "- `TOP_TURFS.csv`: Detailed list of top walk turfs.",
        "- `FIELD_PACE.csv`: Weekly breakdown of field goals.",
        "- `FIELD_PLAN.csv`: Detailed field plan from operations planner.",
        "- `SIMULATION_RESULTS.csv`: Raw Monte Carlo simulation results.",
    ])

    return "\n".join(summary_lines)


def write_strategy_pack(
    contest_id: str,
    run_id: str,
    contest_mode: str,
    mode_reason: str,
    inputs: dict,
    win_path: dict,
    focus: dict,
    pace_df: pd.DataFrame,
    uni_guidance: str,
    ops_config: dict,
    logger=None,
    integrity_meta: dict | None = None,
) -> Path:
    """Write all 5 Strategy Pack artifacts. Returns pack_dir."""
    out_root = BASE_DIR / "derived" / "strategy_packs" / contest_id / run_id
    out_root.mkdir(parents=True, exist_ok=True)

    derived_mode = inputs["derived_mode"]
    targets   = inputs["targets"]
    turfs     = assign_turf_purpose(inputs["turfs"], targets)
    top_t     = focus["top_target"]
    top_regions = focus["top_regions"]

    # ── 4.2 TOP_TARGETS.csv ───────────────────────────────────────────────────
    if not top_t.empty:
        target_cols = [c for c in [
            "canonical_precinct_id", "registered", "ballots_cast",
            "turnout_pct", "support_pct", "persuasion_potential",
            "turnout_opportunity", "target_score", "tier",
            "walk_priority_rank", "region_id",
        ] if c in top_t.columns]
        top_t[target_cols].to_csv(out_root / "TOP_TARGETS.csv", index=False)

    # ── 4.3 TOP_TURFS.csv ─────────────────────────────────────────────────────
    if not turfs.empty:
        turf_cols = [c for c in [
            "turf_id", "precinct_ids", "sum_registered", "expected_contacts",
            "expected_net_gain", "region_id", "turf_purpose",
        ] if c in turfs.columns]
        turfs.head(DEFAULT_TOP_N_TURFS)[turf_cols].to_csv(out_root / "TOP_TURFS.csv", index=False)

    # ── 4.5a Extra Prompt-8 artifacts ────────────────────────────────────────
    # SIMULATION_RESULTS.csv
    sim_export = inputs.get("simulations", pd.DataFrame())
    if not sim_export.empty:
        sim_export.to_csv(out_root / "SIMULATION_RESULTS.csv", index=False)

    # FIELD_PLAN.csv (ops planner output, or fallback from field_plan)
    field_plan_export = inputs.get("field_plan", pd.DataFrame())
    if not field_plan_export.empty:
        # Rename to match Prompt 8 spec
        fp_cols = [c for c in [
            "region_id", "region_name", "registered_total",
            "doors_to_knock", "expected_contacts", "volunteers_needed", "weeks_required",
        ] if c in field_plan_export.columns]
        if not fp_cols:
            fp_cols = list(field_plan_export.columns)
        field_plan_export[fp_cols].to_csv(out_root / "FIELD_PLAN.csv", index=False)

    # ── 4.4 FIELD_PACE.csv ────────────────────────────────────────────────────
    pace_df.to_csv(out_root / "FIELD_PACE.csv", index=False)

    # ── 4.5 STRATEGY_META.json ────────────────────────────────────────────────
    _scenario_count = (
        len(inputs["simulations"]["scenario"].unique())
        if not inputs["simulations"].empty and "scenario" in inputs["simulations"].columns
        else (4 if not inputs["simulations"].empty else 0)
    )

    # integrity_meta is optionally passed in via run_strategy_generator kwargs
    _integrity = integrity_meta or {}

    meta = {
        "contest_id":    contest_id,
        "run_id":        run_id,
        "generated_at":  datetime.datetime.now().isoformat(),
        "contest_mode":  contest_mode,
        "mode_reason":   mode_reason,
        "derived_mode":  derived_mode,
        "forecast_mode": inputs.get("forecast_mode", "both"),
        # Prompt 8.6: top-level counts (audit-accessible)
        "precinct_count":  len(targets),
        "turf_count":      len(turfs),
        "region_count":    len(top_regions),
        "scenario_count":  _scenario_count,
        # Prompt 8.6: data quality flags
        "constraint_violations_count": _integrity.get("constraint_violations_count", 0),
        "integrity_repairs_count":     _integrity.get("integrity_repairs_count", 0),
        "join_guard_critical":         _integrity.get("join_guard_critical", False),
        "inputs_found":  inputs["inputs_found"],
        "inputs_missing":inputs["inputs_missing"],
        "model_summary": {
            "precinct_count": len(targets),
            "turf_count":     len(turfs),
            "region_count":   len(top_regions),
            "scenario_count": _scenario_count,
        },
        "topline_metrics": {
            "baseline_turnout":  win_path["baseline_turnout"],
            "baseline_support":  win_path["baseline_support"],
            "baseline_margin":   win_path["baseline_margin"],
            "win_number":        win_path["win_number"],
            "best_case_margin":  win_path["best_case_margin"],
            "worst_case_margin": win_path["worst_case_margin"],
            "win_probability":   win_path.get("win_probability"),
        },
        "recommended_strategy": _recommended_strategy(
            win_path, inputs["simulations"]
        ),
    }
    (out_root / "STRATEGY_META.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    # ── 4.1 STRATEGY_SUMMARY.md ───────────────────────────────────────────────
    mode_badge = {"full": "✅ Full", "partial": "⚠️ Partial", "degraded": "🔴 Degraded", "blocked": "❌ Blocked"}
    completeness = mode_badge.get(derived_mode, "?")

    # Top 15 precincts table
    top15 = top_t.head(15)
    if not top15.empty and "canonical_precinct_id" in top15.columns:
        t_cols = ["canonical_precinct_id"]
        for c in ["registered", "support_pct", "target_score", "tier"]:
            if c in top15.columns:
                t_cols.append(c)
        top15_md = top15[t_cols].to_markdown(index=False)
    else:
        top15_md = "_No target data available._"

    # Top 10 turfs
    top10_turfs = turfs.head(10)
    if not top10_turfs.empty and "turf_id" in top10_turfs.columns:
        tc = ["turf_id"]
        for c in ["sum_registered", "expected_contacts", "turf_purpose"]:
            if c in top10_turfs.columns:
                tc.append(c)
        turfs_md = top10_turfs[tc].to_markdown(index=False)
    else:
        turfs_md = "_No turf data available._"

    # Focus regions
    if top_regions:
        reg_lines = "\n".join(
            f"- Region **{r.get('region_id')}** — avg target score: "
            f"{r.get('avg_target_score', 'N/A'):.2f}, "
            f"total registered: {int(r.get('total_registered', 0)):,}" for r in top_regions
        )
    else:
        reg_lines = "_No region data — run pipeline or upgrade to v3 ops layer._"

    # Win path block
    wp = win_path
    def _fmt(v):
        return f"{v:,.0f}" if isinstance(v, (int, float)) and v is not None else str(v or "N/A")

    # Capacity summary
    if not pace_df.empty:
        first_wk = pace_df.iloc[0]
        cap_text = (f"- **Week 1 pace:** {_fmt(first_wk.get('doors_goal'))} doors, "
                    f"{_fmt(first_wk.get('shifts_goal'))} shifts, "
                    f"{_fmt(first_wk.get('volunteers_goal'))} volunteers\n"
                    f"- See `FIELD_PACE.csv` for full {len(pace_df)}-week schedule")
    else:
        cap_text = "_Field pace unavailable._"

    # Data gaps
    gaps = inputs["inputs_missing"]
    gap_text = "\n".join(f"- `{g}`" for g in gaps) if gaps else "- None ✅"

    (out_root / "STRATEGY_SUMMARY.md").write_text(
        _build_strategy_summary(contest_id, contest_mode, mode_reason, derived_mode,
                                win_path, top15_md, turfs_md, reg_lines, cap_text,
                                uni_guidance, gaps, pace_df),
        encoding="utf-8"
    )


    if logger:
        logger.info(f"  Strategy pack written to {out_root}")

    return out_root


# ══════════════════════════════════════════════════════════════════════════════
# NEEDS + Pathway Update Helpers
# ══════════════════════════════════════════════════════════════════════════════
def update_needs(contest_id: str, run_id: str, derived_mode: str, missing: list):
    needs_path = BASE_DIR / "needs" / "needs.yaml"
    if not needs_path.parent.exists():
        needs_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = yaml.safe_load(needs_path.read_text()) or {} if needs_path.exists() else {}
    except Exception:
        existing = {}

    existing.setdefault("strategy_generator", {})[contest_id] = {
        "status":       "complete" if derived_mode in ("full", "partial") else "degraded",
        "derived_mode": derived_mode,
        "missing_inputs": missing,
        "last_run_id":  run_id,
        "notes":        f"Generated at {datetime.datetime.now().isoformat()}",
    }

    needs_path.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")


def update_pathway(logger, contest_mode: str, pack_dir: Path, top_regions: list,
                   baseline_scenario: str = ""):
    if logger is None:
        return
    try:
        logger._pathway["strategy_generator"] = {
            "contest_mode":   contest_mode,
            "baseline_scenario": baseline_scenario,
            "outputs_written": [str(p.name) for p in pack_dir.iterdir()],
            "top_regions":    top_regions,
            "pack_dir":       str(pack_dir),
        }
    except Exception:
        pass  # Non-critical


# ══════════════════════════════════════════════════════════════════════════════
# Public Entry Point
# ══════════════════════════════════════════════════════════════════════════════
def run_strategy_generator(
    contest_id: str,
    run_id: str,
    contest_mode: str = "auto",
    forecast_mode: str = "both",
    weeks: int = DEFAULT_WEEKS,
    state: str = "CA",
    county: str = "",
    contest_slug: str = "",
    logger=None,
    integrity_meta: dict | None = None,
) -> Optional[Path]:
    """
    Main entry point. Returns path to strategy pack folder, or None on error.
    forecast_mode: deterministic | monte_carlo | both
    """
    if logger: logger.info(f"[STRATEGY] Loading inputs for contest_id={contest_id}")

    # Load ops config
    ops_cfg_path = BASE_DIR / "config" / "field_ops.yaml"
    ops_config: dict = {}
    if ops_cfg_path.exists():
        try:
            ops_config = yaml.safe_load(ops_cfg_path.read_text()) or {}
        except Exception:
            pass

    # Load inputs
    inputs = load_inputs(contest_id, run_id)
    inputs["forecast_mode"] = forecast_mode
    derived_mode = inputs["derived_mode"]

    # ── Inline simulation if not already present ──────────────────────────
    if inputs["simulations"].empty and not inputs["targets"].empty:
        try:
            from scripts.simulation.simulation_engine import run_simulation
            _cslug = contest_slug or contest_id
            _county = county or "unknown"
            sim_result = run_simulation(
                model_df=inputs["targets"],
                state=state or "CA",
                county=_county,
                contest=_cslug,
                run_id=run_id,
                mode=forecast_mode,
                logger=logger,
            )
            inputs["simulations"] = sim_result["simulation_results"]
            if sim_result["win_probability"] is not None:
                inputs["win_probability"] = sim_result["win_probability"]
                inputs["median_margin"]   = sim_result["median_margin"]
            if logger: logger.info(f"[STRATEGY] Inline simulation complete, win_prob={sim_result['win_probability']}")
        except Exception as e:
            if logger: logger.warn(f"[STRATEGY] Inline simulation failed (non-fatal): {e}")

    # ── Inline ops planner if not already present ───────────────────────
    if inputs["field_plan"].empty and not inputs["targets"].empty:
        try:
            from scripts.ops.operations_planner import run_operations_planner
            _cslug = contest_slug or contest_id
            _county = county or "unknown"
            ops_result = run_operations_planner(
                model_df=inputs["targets"],
                state=state or "CA",
                county=_county,
                contest=_cslug,
                run_id=run_id,
                logger=logger,
            )
            inputs["field_plan"] = ops_result["field_plan"]
            inputs["regions"]    = ops_result["regions"]
            if logger: logger.info(f"[STRATEGY] Inline ops planner: {ops_result['region_count']} regions")
        except Exception as e:
            if logger: logger.warn(f"[STRATEGY] Inline ops planner failed (non-fatal): {e}")

    if logger:
        logger.info(f"[STRATEGY]  derived_mode={derived_mode}")
        logger.info(f"[STRATEGY]  found={list(inputs['inputs_found'].keys())}")
        logger.info(f"[STRATEGY]  missing={inputs['inputs_missing']}")

    if derived_mode == "blocked":
        if logger: logger.warn("[STRATEGY] Blocked — required inputs missing. Cannot generate strategy.")
        update_needs(contest_id, run_id, "blocked", inputs["inputs_missing"])
        return None

    # Contest mode
    final_mode, mode_reason = infer_contest_mode(inputs["targets"], contest_mode)
    if logger: logger.info(f"[STRATEGY]  contest_mode={final_mode} ({mode_reason})")

    # Win path (merge inline simulation results)
    win_path = compute_win_path(inputs["targets"], inputs["forecasts"],
                                inputs["simulations"], final_mode)
    if "win_probability" in inputs:
        win_path["win_probability"] = inputs["win_probability"]
    if "median_margin" in inputs and win_path["baseline_margin"] is None:
        win_path["baseline_margin"] = inputs["median_margin"]

    # Focus areas
    focus = compute_focus(inputs["targets"], inputs["regions"])

    # Field pace
    pace_df = compute_field_pace(inputs["field_plan"], ops_config, weeks=weeks)

    # Universe guidance
    voter_exports = any("voter_list" in str(p) for p in (BASE_DIR / "derived" / "universes").rglob("*.csv")) \
        if (BASE_DIR / "derived" / "universes").exists() else False
    uni_text = universe_guidance(inputs["universes"], voter_exports)

    # Write pack
    try:
        pack_dir = write_strategy_pack(
            contest_id=contest_id,
            run_id=run_id,
            contest_mode=final_mode,
            mode_reason=mode_reason,
            inputs=inputs,
            win_path=win_path,
            focus=focus,
            pace_df=pace_df,
            uni_guidance=uni_text,
            ops_config=ops_config,
            logger=logger,
            integrity_meta=integrity_meta or {},
        )
    except Exception as e:
        if logger: logger.error(f"[STRATEGY] Write failed: {e}")
        update_needs(contest_id, run_id, "blocked", [f"write_error: {e}"])
        return None

    # Update NEEDS + pathway
    update_needs(contest_id, run_id, derived_mode, inputs["inputs_missing"])
    update_pathway(logger, final_mode, pack_dir, focus["top_regions"])

    if logger: logger.info(f"[STRATEGY] Pack written → {pack_dir}")
    return pack_dir


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Campaign Strategy Generator")
    parser.add_argument("--contest-id", required=True)
    parser.add_argument("--run-id",     default="manual")
    parser.add_argument("--contest-mode", default="auto", choices=["auto", "measure", "candidate"])
    parser.add_argument("--weeks",      type=int, default=DEFAULT_WEEKS)
    args = parser.parse_args()

    pack = run_strategy_generator(
        contest_id=args.contest_id,
        run_id=args.run_id,
        contest_mode=args.contest_mode,
        forecast_mode=args.forecast_mode if hasattr(args, "forecast_mode") else "both",
        weeks=args.weeks,
    )
    if pack:
        print(f"\nStrategy Pack generated: {pack}")
    else:
        print("\nFailed to generate strategy pack.")
        sys.exit(1)
