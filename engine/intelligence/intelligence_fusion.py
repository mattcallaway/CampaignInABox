"""
engine/intelligence/intelligence_fusion.py — Prompt 17

Combine all intelligence signals into a single support adjustment.

Formula:
    S_adj = S_model + α·P + β·D + γ·R + δ·M

Where:
    P = polling signal  (poll_average - model_support_baseline)
    D = demographic adjustment (from demographics.py)
    R = registration trend signal
    M = macro environment score
    α, β, γ, δ = learned weights (from calibration or priors)

Default weights:
    α (polling)      = 0.60  — polls are the strongest external signal
    β (demographic)  = 0.15  — demographic shifts affect baseline
    γ (registration) = 0.20  — registration momentum is meaningful
    δ (macro)        = 0.05  — national environment is a weak signal for local races

Outputs:
    derived/intelligence/support_adjustment.json
    derived/intelligence/forecast_adjusted.csv
    reports/intelligence/<RUN_ID>__intelligence_signal_summary.md
    reports/qa/<RUN_ID>__intelligence_diagnostics.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

DERIVED   = Path(__file__).resolve().parent.parent.parent / "derived" / "intelligence"
REPORTS   = Path(__file__).resolve().parent.parent.parent / "reports" / "intelligence"
QA_DIR    = Path(__file__).resolve().parent.parent.parent / "reports" / "qa"

# Default fusion weights (α, β, γ, δ)
_DEFAULT_WEIGHTS = {
    "alpha_polling":      0.60,
    "beta_demographic":   0.15,
    "gamma_registration": 0.20,
    "delta_macro":        0.05,
}

# Clamp adjustment to prevent extreme swings
_MAX_ADJUSTMENT =  0.10  # +10pp max
_MIN_ADJUSTMENT = -0.10  # -10pp max


def _load_weights(root: Path) -> dict:
    """Load fusion weights from model_parameters.yaml if calibration section has them."""
    try:
        import yaml
        p = root / "config" / "model_parameters.yaml"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            intel = cfg.get("intelligence", {})
            loaded = {}
            for k, default in _DEFAULT_WEIGHTS.items():
                loaded[k] = float(intel.get(k, default))
            return loaded
    except Exception:
        pass
    return _DEFAULT_WEIGHTS.copy()


def run_intelligence_fusion(
    project_root: Path,
    run_id: str = "",
    model_support_baseline: Optional[float] = None,
    precinct_model: Optional[pd.DataFrame] = None,
    logger=None,
) -> dict:
    """
    Run the full intelligence fusion pipeline.

    Loads derived/ outputs from all 5 signal modules.
    Computes S_adj and writes output files.

    Returns fusion result dict.
    """
    _log = logger or log
    root = Path(project_root)
    now = datetime.utcnow().isoformat()
    DERIVED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    weights = _load_weights(root)

    # ── Load all signal results ───────────────────────────────────────────────
    def _rj(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    poll_avg    = _rj(DERIVED / "poll_average.json")
    reg_summary = _rj(DERIVED / "registration_summary.json")
    macro_env   = _rj(DERIVED / "macro_environment.json")

    # Demographic signal
    demo_df = pd.DataFrame()
    demo_path = DERIVED / "precinct_demographics.csv"
    if demo_path.exists():
        try:
            demo_df = pd.read_csv(demo_path)
        except Exception:
            pass

    from engine.intelligence.demographics import compute_demographic_signal
    demo_signal = compute_demographic_signal(
        demo_df,
        precinct_model if precinct_model is not None else pd.DataFrame()
    )

    # ── Model baseline ────────────────────────────────────────────────────────
    if model_support_baseline is None:
        # Try to read from precinct model
        if precinct_model is not None and not precinct_model.empty:
            for col in ["support_pct", "yes_pct", "support_percent"]:
                if col in precinct_model.columns:
                    model_support_baseline = float(precinct_model[col].mean())
                    break
        if model_support_baseline is None:
            model_support_baseline = 0.50   # neutral fallback

    _log.info(f"[INTEL_FUSION] Model baseline={model_support_baseline:.4f}")

    # ── Compute signal contributions ─────────────────────────────────────────
    contributions: dict = {}
    source_types: list[str] = []

    # α — Polling
    p_signal = 0.0
    p_source = "MISSING"
    if poll_avg.get("poll_average") is not None:
        raw_poll = float(poll_avg["poll_average"])
        p_signal = raw_poll - model_support_baseline
        p_source = poll_avg.get("source_type", "SIMULATED")
        contributions["polling_signal"]    = round(p_signal, 5)
        contributions["poll_average"]      = round(raw_poll, 4)
        contributions["polling_weight"]    = weights["alpha_polling"]
        source_types.append(p_source)
    else:
        contributions["polling_signal"] = 0.0
        contributions["poll_average"]   = None

    # β — Demographic
    d_signal = float(demo_signal.get("education_adjustment", 0.0))
    d_source = demo_signal.get("source_type", "MISSING")
    contributions["demographic_signal"] = round(d_signal, 5)
    contributions["demographic_weight"] = weights["beta_demographic"]
    source_types.append(d_source)

    # γ — Registration
    r_signal = 0.0
    r_source = "MISSING"
    net_partisan = reg_summary.get("net_partisan_score")
    if net_partisan is not None:
        # Positive net_partisan (D > R) is a slight tailwind
        r_signal = float(net_partisan) * 0.05   # scale down: it's a structural, not race-specific signal
        r_source = reg_summary.get("source_type", "ESTIMATED")
        source_types.append(r_source)
    contributions["registration_signal"] = round(r_signal, 5)
    contributions["registration_weight"] = weights["gamma_registration"]
    contributions["net_partisan_score"]  = net_partisan

    # δ — Macro
    m_signal = float(macro_env.get("macro_environment_score", 0.0))
    m_source = macro_env.get("source_type", "SIMULATED")
    contributions["macro_signal"] = round(m_signal, 5)
    contributions["macro_weight"] = weights["delta_macro"]
    source_types.append(m_source)

    # ── Fusion formula: S_adj = S_model + α·P + β·D + γ·R + δ·M ─────────────
    adjustment = (
        weights["alpha_polling"]      * p_signal +
        weights["beta_demographic"]   * d_signal +
        weights["gamma_registration"] * r_signal +
        weights["delta_macro"]        * m_signal
    )
    adjustment = max(min(adjustment, _MAX_ADJUSTMENT), _MIN_ADJUSTMENT)
    adjusted_support = max(min(model_support_baseline + adjustment, 1.0), 0.0)

    # Determine overall provenance
    has_real = any(s in ("EXTERNAL", "REAL") for s in source_types)
    has_estimated = any(s == "ESTIMATED" for s in source_types)
    overall_source = "EXTERNAL" if has_real else ("ESTIMATED" if has_estimated else "SIMULATED")

    # ── Impact assessment ─────────────────────────────────────────────────────
    if abs(adjustment) < 0.005:
        impact = "NEUTRAL"
    elif adjustment > 0:
        impact = "POSITIVE"
    else:
        impact = "NEGATIVE"

    result = {
        "run_id":                run_id,
        "generated_at":          now,
        "model_support_baseline": round(model_support_baseline, 4),
        "intelligence_adjustment": round(adjustment, 5),
        "adjusted_support":       round(adjusted_support, 4),
        "impact":                 impact,
        "source_type":            overall_source,
        "weights":                weights,
        "contributions":          contributions,
        "signal_sources":         list(set(source_types)),
        "has_real_signals":       has_real,
        "poll_average":           poll_avg.get("poll_average"),
        "poll_average_ci_low":    poll_avg.get("confidence_interval_low"),
        "poll_average_ci_high":   poll_avg.get("confidence_interval_high"),
        "n_polls":                poll_avg.get("n_polls", 0),
        "registration_growth":    reg_summary.get("registration_growth"),
        "net_partisan_score":     net_partisan,
        "macro_score":            macro_env.get("macro_environment_score"),
        "demographic_adjustment": d_signal,
    }

    # ── Write support_adjustment.json ─────────────────────────────────────────
    (DERIVED / "support_adjustment.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    _log.info(
        f"[INTEL_FUSION] adjustment={adjustment:+.5f} | "
        f"adjusted={adjusted_support:.4f} | impact={impact} | source={overall_source}"
    )

    # ── Write forecast_adjusted.csv ───────────────────────────────────────────
    _write_forecast_adjusted(precinct_model, adjusted_support, adjustment, run_id)

    # ── Write reports ─────────────────────────────────────────────────────────
    _write_signal_summary(result, run_id, poll_avg, reg_summary, macro_env, demo_signal)
    _write_intelligence_diagnostics(result, run_id)

    return result


# ── Forecast adjusted CSV ─────────────────────────────────────────────────────

def _write_forecast_adjusted(
    precinct_model: Optional[pd.DataFrame],
    adjusted_support: float,
    adjustment: float,
    run_id: str,
) -> None:
    """Write adjusted_support to each precinct in forecast_adjusted.csv."""
    if precinct_model is None or (isinstance(precinct_model, pd.DataFrame) and precinct_model.empty):
        df = pd.DataFrame([{
            "canonical_precinct_id": "aggregate",
            "baseline_support": adjusted_support - adjustment,
            "intelligence_adjustment": adjustment,
            "adjusted_support": adjusted_support,
            "run_id": run_id,
        }])
    else:
        df = precinct_model[["canonical_precinct_id"]].copy()
        for col in ["support_pct", "yes_pct"]:
            if col in precinct_model.columns:
                df["baseline_support"] = precinct_model[col]
                break
        else:
            df["baseline_support"] = adjusted_support - adjustment
        df["intelligence_adjustment"] = adjustment
        df["adjusted_support"] = (df["baseline_support"] + adjustment).clip(0, 1)
        df["run_id"] = run_id

    out_path = DERIVED / "forecast_adjusted.csv"
    df.to_csv(out_path, index=False)
    log.info(f"[INTEL_FUSION] Forecast adjusted → {out_path.name} ({len(df)} rows)")


# ── Signal summary report ─────────────────────────────────────────────────────

def _write_signal_summary(
    result: dict, run_id: str,
    poll_avg: dict, reg_summary: dict, macro_env: dict, demo_signal: dict,
) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Intelligence Signal Summary — Prompt 17",
        f"**Run:** `{run_id}` &nbsp; **Generated:** {now}",
        "",
        "## Fusion Result",
        "",
        f"| Component | Value |",
        f"|-----------|-------|",
        f"| Model Baseline Support | {result['model_support_baseline']:.3%} |",
        f"| Intelligence Adjustment | {result['intelligence_adjustment']:+.4%} |",
        f"| **Adjusted Support** | **{result['adjusted_support']:.3%}** |",
        f"| Impact | {result['impact']} |",
        f"| Overall Provenance | {result['source_type']} |",
        "",
        "## Signal Contributions",
        "",
        f"| Signal | Raw Value | Weighted Contribution | Source |",
        f"|--------|-----------|----------------------|--------|",
        f"| Polling (α={result['weights']['alpha_polling']}) | {result['contributions'].get('poll_average', 'N/A')} | {result['contributions']['polling_signal'] * result['weights']['alpha_polling']:+.5f} | {poll_avg.get('source_type','MISSING')} |",
        f"| Demographic (β={result['weights']['beta_demographic']}) | edu_adj={result['contributions']['demographic_signal']:.5f} | {result['contributions']['demographic_signal'] * result['weights']['beta_demographic']:+.5f} | {demo_signal.get('source_type','MISSING')} |",
        f"| Registration (γ={result['weights']['gamma_registration']}) | partisan={result['contributions']['net_partisan_score']} | {result['contributions']['registration_signal'] * result['weights']['gamma_registration']:+.5f} | {reg_summary.get('source_type','MISSING')} |",
        f"| Macro (δ={result['weights']['delta_macro']}) | score={result['macro_score']} | {result['contributions']['macro_signal'] * result['weights']['delta_macro']:+.5f} | {macro_env.get('source_type','SIMULATED')} |",
        "",
        "## Polling Detail",
        "",
    ]

    pa = poll_avg.get("poll_average")
    if pa is not None:
        lines += [
            f"**Poll Average:** {pa:.3%} ({poll_avg.get('n_polls',0)} polls)",
            f"**95% CI:** [{poll_avg.get('confidence_interval_low', 0):.3%}, {poll_avg.get('confidence_interval_high', 1):.3%}]",
            f"**Latest Poll:** {poll_avg.get('latest_poll_date', '—')}",
            "",
        ]
    else:
        lines += ["*No polling data loaded. Add files to `data/intelligence/polling/`.*", ""]

    lines += [
        "## Strategy Implications",
        "",
    ]
    adj = result["intelligence_adjustment"]
    base = result["model_support_baseline"]
    adj_sup = result["adjusted_support"]

    if abs(adj) < 0.005:
        lines.append("- ✅ Intelligence signals confirm the model baseline — no major strategy adjustment needed.")
    elif adj > 0:
        lines += [
            f"- 📈 Intelligence signals are **positive** (+{adj:.1%}) — conditions favor your side.",
            "- Consider shifting some GOTV budget toward persuasion to pick up soft supporters.",
            "- Maintain current field plan; do not reduce resources.",
        ]
    else:
        lines += [
            f"- 📉 Intelligence signals are **negative** ({adj:+.1%}) — headwinds present.",
            "- Shift strategy toward your strongest GOTV precincts.",
            "- Increase persuasion contacts in highest swing-index precincts.",
            "- Review ballot return pace — if returns are lagging, surge late GOTV.",
        ]

    if adj_sup < 0.50:
        lines.append("- ⚠️ **Adjusted support below 50%** — you are currently below the win threshold. Significant strategy change required.")
    elif adj_sup >= 0.55:
        lines.append("- 🎯 Adjusted support comfortably above threshold — protect your base and run efficient GOTV.")

    lines += ["", "---", "*Intelligence Signal Summary by engine/intelligence/intelligence_fusion.py — Prompt 17*"]

    fname = f"{run_id}__intelligence_signal_summary.md" if run_id else "intelligence_signal_summary.md"
    (REPORTS / fname).write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[INTEL_FUSION] Signal summary → {fname}")


def _write_intelligence_diagnostics(result: dict, run_id: str) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    c = result["contributions"]
    lines = [
        f"# Intelligence Diagnostics — Prompt 17",
        f"**Run:** `{run_id}` &nbsp; **Generated:** {now}",
        "",
        "## Signal Coverage",
        "",
        f"| Signal | Status | Provenance |",
        f"|--------|--------|------------|",
        f"| Polling | {'✅ Available (' + str(result.get('n_polls', 0)) + ' polls)' if result.get('n_polls', 0) > 0 else '❌ No polling data'} | {result['contributions'].get('poll_average') and 'EXTERNAL' or 'MISSING'} |",
        f"| Demographics | {'✅ Available' if result['contributions']['demographic_signal'] != 0 else '⚠️ Neutral/Missing'} | {'EXTERNAL' if result['has_real_signals'] else 'MISSING'} |",
        f"| Registration | {'✅ ' + str(result.get('registration_growth', '')) if result.get('net_partisan_score') is not None else '❌ No registration data'} | {'EXTERNAL' if result.get('net_partisan_score') is not None else 'MISSING'} |",
        f"| Ballot Returns | *(see ballot_returns_summary.json)* | — |",
        f"| Macro Environment | {'✅ Score=' + str(result.get('macro_score', '0')) if result.get('macro_score') is not None else '⚠️ Defaults only'} | {'EXTERNAL' if result.get('has_real_signals') else 'SIMULATED'} |",
        "",
        "## Recommendations to Improve Intelligence Coverage",
        "",
    ]
    if result.get("n_polls", 0) == 0:
        lines.append("- ❌ Add polling files to `data/intelligence/polling/` (CSV/XLSX/JSON)")
    if result["contributions"]["demographic_signal"] == 0:
        lines.append("- ❌ Add Census ACS data to `data/intelligence/demographics/`")
    if result.get("net_partisan_score") is None:
        lines.append("- ❌ Add registration snapshots to `data/intelligence/registration/`")
    if result.get("macro_score", 0) == 0:
        lines.append("- ⚠️ Add macro signal file to `data/intelligence/macro/` (presidential approval, generic ballot)")

    if all(result["contributions"][k] == 0 for k in ["polling_signal", "demographic_signal", "registration_signal", "macro_signal"]):
        lines.append("\n> [!WARNING]")
        lines.append("> All signals are at zero/default. The intelligence layer is producing no adjustment.")
        lines.append("> Add real data to `data/intelligence/` to activate this layer.")
    else:
        lines.append("- ✅ At least one intelligence signal is contributing to the adjusted forecast.")

    lines += ["", "---", "*Intelligence Diagnostics by engine/intelligence/intelligence_fusion.py — Prompt 17*"]

    fname = f"{run_id}__intelligence_diagnostics.md" if run_id else "intelligence_diagnostics.md"
    (QA_DIR / fname).write_text("\n".join(lines), encoding="utf-8")


def load_support_adjustment() -> dict:
    path = DERIVED / "support_adjustment.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}
