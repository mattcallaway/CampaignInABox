"""
engine/provenance/data_provenance.py — Prompt 14

First-class data provenance system for Campaign In A Box.

Classifies every major campaign metric as:
  REAL       — sourced from actual campaign runtime data
  SIMULATED  — produced by Monte Carlo / model simulation
  ESTIMATED  — computed from heuristics / prior assumptions
  MISSING    — data required but not present

Outputs derived/provenance/<run_id>__metric_provenance.json
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROVENANCE_DIR = BASE_DIR / "derived" / "provenance"

log = logging.getLogger(__name__)

# Source type constants
REAL      = "REAL"
SIMULATED = "SIMULATED"
ESTIMATED = "ESTIMATED"
MISSING   = "MISSING"

CONFIDENCE_HIERARCHY = {REAL: 4, SIMULATED: 3, ESTIMATED: 2, MISSING: 1}


@dataclass
class ProvenanceRecord:
    """A single metric's provenance record."""
    metric_name: str
    value: Any
    source_type: str        # REAL | SIMULATED | ESTIMATED | MISSING
    source_file: str        # relative path or description
    confidence: str         # high | medium | low | none
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def badge_label(self) -> str:
        return self.source_type


def _find_latest(directory: Path, pattern: str) -> Optional[Path]:
    try:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0] if matches else None
    except Exception:
        return None


def _has_runtime(runtime_dir: Path, filename: str) -> bool:
    """Check if a runtime data file exists and has data rows."""
    try:
        p = runtime_dir / filename
        if not p.exists():
            return False
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        return len(lines) >= 2  # header + at least 1 data row
    except Exception:
        return False


def classify_metrics(
    run_id: str,
    runtime_dir: Optional[Path] = None,
    campaign_config: Optional[dict] = None,
) -> list[ProvenanceRecord]:
    """
    Inspect current derived outputs and runtime data to classify all major metrics.

    Priority: REAL > SIMULATED > ESTIMATED > MISSING
    """
    records: list[ProvenanceRecord] = []
    cfg = campaign_config or {}

    # ── Locate derived outputs ────────────────────────────────────────────────
    vote_path_csv    = _find_latest(BASE_DIR / "derived" / "strategy", "*__vote_path.csv")
    budget_csv       = _find_latest(BASE_DIR / "derived" / "strategy", "*__budget_allocation.csv")
    field_strat_csv  = _find_latest(BASE_DIR / "derived" / "strategy", "*__field_strategy.csv")
    cal_params       = BASE_DIR / "derived" / "calibration" / "model_parameters.json"
    sim_dir          = BASE_DIR / "derived" / "scenario_forecasts"
    tps_csv          = _find_latest(BASE_DIR / "derived" / "voter_models", "*__precinct_turnout_scores.csv")
    ps_csv           = _find_latest(BASE_DIR / "derived" / "voter_models", "*__precinct_persuasion_scores.csv")
    voter_parquet    = _find_latest(BASE_DIR / "derived" / "voter_models", "*.parquet")
    universes_csv    = _find_latest(BASE_DIR / "derived" / "voter_universes", "*__universes.csv")

    has_calibration  = cal_params.exists()
    has_simulation   = sim_dir.exists() and any(sim_dir.rglob("*.csv"))
    has_voter_file   = voter_parquet is not None
    has_tps          = tps_csv is not None
    has_ps           = ps_csv is not None
    has_vote_path    = vote_path_csv is not None

    # Runtime data presence
    if runtime_dir is None:
        # Try to infer from campaign config
        state  = "CA"
        county = (cfg.get("campaign", {}).get("jurisdiction", "Sonoma County, CA")
                  .replace(", CA", "").replace(" County", "").replace(" ", "_"))
        slug   = (cfg.get("campaign", {}).get("contest_name", "prop_50_special")
                  .lower().replace(" ", "_")[:20])
        runtime_dir = BASE_DIR / "data" / "campaign_runtime" / state / county / slug

    has_field_results   = _has_runtime(runtime_dir, "field_results.csv")
    has_volunteer_log   = _has_runtime(runtime_dir, "volunteer_log.csv")
    has_budget_actuals  = _has_runtime(runtime_dir, "budget_actuals.csv")
    has_contact_results = _has_runtime(runtime_dir, "contact_results.csv")

    # ── 1. Turnout ────────────────────────────────────────────────────────────
    if has_calibration:
        records.append(ProvenanceRecord(
            metric_name="baseline_turnout",
            value="from model_parameters.json",
            source_type=SIMULATED,
            source_file="derived/calibration/model_parameters.json",
            confidence="medium",
            notes="OLS regression on historical election data. Confidence increases with more election history.",
        ))
    else:
        records.append(ProvenanceRecord(
            metric_name="baseline_turnout",
            value=0.42,
            source_type=ESTIMATED,
            source_file="prior",
            confidence="low",
            notes="Prior assumption (42%) — no calibration data available.",
        ))

    # ── 2. Contact Rate ───────────────────────────────────────────────────────
    if has_field_results:
        records.append(ProvenanceRecord(
            metric_name="contact_rate",
            value="computed from field_results.csv",
            source_type=REAL,
            source_file="data/campaign_runtime/.../field_results.csv",
            confidence="high",
            notes="Computed from actual doors knocked vs. contacts made in field results.",
        ))
    else:
        contact_success = cfg.get("field_program", {}).get("contact_success_rate", 0.22)
        records.append(ProvenanceRecord(
            metric_name="contact_rate",
            value=contact_success,
            source_type=ESTIMATED,
            source_file="config/campaign_config.yaml",
            confidence="low",
            notes=f"Configured estimate ({contact_success:.0%}). Upload field results to replace with real rate.",
        ))

    # ── 3. Persuasion Rate ────────────────────────────────────────────────────
    if has_contact_results:
        records.append(ProvenanceRecord(
            metric_name="persuasion_rate",
            value="computed from contact_results.csv",
            source_type=REAL,
            source_file="data/campaign_runtime/.../contact_results.csv",
            confidence="high",
            notes="Observed persuasion rate: persuasion_contacts / total_contacts.",
        ))
    elif has_tps and has_ps:
        records.append(ProvenanceRecord(
            metric_name="persuasion_rate",
            value="from voter PS/TPS scores",
            source_type=SIMULATED,
            source_file="derived/voter_models/*__precinct_persuasion_scores.csv",
            confidence="medium",
            notes="Derived from Persuasion Score model (party strength + age + TPS).",
        ))
    else:
        pers_rate = cfg.get("field_program", {}).get("persuasion_rate_per_contact", 0.04)
        records.append(ProvenanceRecord(
            metric_name="persuasion_rate",
            value=pers_rate,
            source_type=ESTIMATED,
            source_file="config/campaign_config.yaml",
            confidence="low",
            notes=f"Configured estimate ({pers_rate:.0%}). No voter model or real contact data.",
        ))

    # ── 4. Turnout Lift ───────────────────────────────────────────────────────
    if has_field_results:
        records.append(ProvenanceRecord(
            metric_name="turnout_lift_per_contact",
            value="computed from field_results.csv",
            source_type=REAL,
            source_file="data/campaign_runtime/.../field_results.csv",
            confidence="high",
            notes="Observed turnout lift from GOTV contacts in field results.",
        ))
    else:
        lift = cfg.get("field_program", {}).get("turnout_lift_per_contact", 0.06)
        records.append(ProvenanceRecord(
            metric_name="turnout_lift_per_contact",
            value=lift,
            source_type=ESTIMATED,
            source_file="config/campaign_config.yaml",
            confidence="low",
            notes=f"Configured prior ({lift:.0%}). No real canvass data to calibrate against.",
        ))

    # ── 5. Win Probability ────────────────────────────────────────────────────
    if has_simulation:
        records.append(ProvenanceRecord(
            metric_name="win_probability",
            value="from Monte Carlo simulation",
            source_type=SIMULATED,
            source_file="derived/scenario_forecasts/",
            confidence="medium",
            notes="Monte Carlo simulation over precinct-level vote distributions.",
        ))
    else:
        records.append(ProvenanceRecord(
            metric_name="win_probability",
            value=None,
            source_type=MISSING,
            source_file="",
            confidence="none",
            notes="Run simulation engine to generate win probability estimate.",
        ))

    # ── 6. Vote Path ──────────────────────────────────────────────────────────
    if has_vote_path:
        records.append(ProvenanceRecord(
            metric_name="vote_path",
            value="from derived/strategy/",
            source_type=SIMULATED if not has_voter_file else ESTIMATED,
            source_file=str(vote_path_csv.relative_to(BASE_DIR)) if vote_path_csv else "",
            confidence="medium" if has_voter_file else "low",
            notes="Vote path from campaign_strategy_ai.py. "
                  + ("Voter file present — universe sizes are real." if has_voter_file
                     else "No voter file — universe sizes are estimated priors."),
        ))
    else:
        records.append(ProvenanceRecord(
            metric_name="vote_path",
            value=None,
            source_type=MISSING,
            source_file="",
            confidence="none",
            notes="Run pipeline with campaign_config.yaml to generate vote path.",
        ))

    # ── 7. Budget ─────────────────────────────────────────────────────────────
    if has_budget_actuals:
        records.append(ProvenanceRecord(
            metric_name="budget_spend",
            value="from budget_actuals.csv",
            source_type=REAL,
            source_file="data/campaign_runtime/.../budget_actuals.csv",
            confidence="high",
            notes="Actual spend entered via War Room budget actuals form.",
        ))
    else:
        total = cfg.get("budget", {}).get("total_budget", 0)
        records.append(ProvenanceRecord(
            metric_name="budget_spend",
            value=total,
            source_type=ESTIMATED if total > 0 else MISSING,
            source_file="config/campaign_config.yaml",
            confidence="low" if total > 0 else "none",
            notes="Budget plan from campaign config — no actuals entered yet."
                  if total > 0 else "No budget configured. Complete Campaign Setup.",
        ))

    # ── 8. Volunteer Capacity ─────────────────────────────────────────────────
    if has_volunteer_log:
        records.append(ProvenanceRecord(
            metric_name="volunteer_capacity",
            value="from volunteer_log.csv",
            source_type=REAL,
            source_file="data/campaign_runtime/.../volunteer_log.csv",
            confidence="high",
            notes="Actual volunteer count and shift data from War Room volunteer tracking.",
        ))
    else:
        vols = cfg.get("volunteers", {}).get("volunteers_per_week", 0)
        records.append(ProvenanceRecord(
            metric_name="volunteer_capacity",
            value=vols,
            source_type=ESTIMATED if vols > 0 else MISSING,
            source_file="config/campaign_config.yaml",
            confidence="low" if vols > 0 else "none",
            notes=f"Configured estimate ({vols} volunteers/week). Enter volunteer logs to replace.",
        ))

    # ── 9. Persuadable Universe ───────────────────────────────────────────────
    if has_voter_file and has_ps:
        records.append(ProvenanceRecord(
            metric_name="persuadable_voter_universe",
            value="from voter PS scores",
            source_type=ESTIMATED,
            source_file="derived/voter_models/*__precinct_persuasion_scores.csv",
            confidence="medium",
            notes="Estimated from Persuasion Score model. Score thresholds are modeled, not field-validated.",
        ))
    else:
        records.append(ProvenanceRecord(
            metric_name="persuadable_voter_universe",
            value=None,
            source_type=MISSING,
            source_file="",
            confidence="none",
            notes="Load a voter file and run the pipeline to generate persuadable universe.",
        ))

    # ── 10. Field Pace ────────────────────────────────────────────────────────
    if has_field_results:
        records.append(ProvenanceRecord(
            metric_name="field_pace_doors_per_week",
            value="computed from field_results.csv",
            source_type=REAL,
            source_file="data/campaign_runtime/.../field_results.csv",
            confidence="high",
            notes="Weekly rolling average of doors knocked from actual field result uploads.",
        ))
    elif has_vote_path:
        records.append(ProvenanceRecord(
            metric_name="field_pace_doors_per_week",
            value="from field_strategy.csv",
            source_type=SIMULATED,
            source_file="derived/strategy/*__field_strategy.csv",
            confidence="medium",
            notes="Modeled weekly door target from campaign_strategy_ai. No actual results to compare.",
        ))
    else:
        records.append(ProvenanceRecord(
            metric_name="field_pace_doors_per_week",
            value=None,
            source_type=MISSING,
            source_file="",
            confidence="none",
            notes="Run pipeline after Campaign Setup to generate field plan.",
        ))

    log.info(
        f"[PROVENANCE] Classified {len(records)} metrics — "
        f"{sum(1 for r in records if r.source_type==REAL)} REAL, "
        f"{sum(1 for r in records if r.source_type==SIMULATED)} SIMULATED, "
        f"{sum(1 for r in records if r.source_type==ESTIMATED)} ESTIMATED, "
        f"{sum(1 for r in records if r.source_type==MISSING)} MISSING"
    )
    return records


def write_provenance_json(records: list[ProvenanceRecord], run_id: str) -> Path:
    """Write provenance records to derived/provenance/<run_id>__metric_provenance.json."""
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    out = PROVENANCE_DIR / f"{run_id}__metric_provenance.json"

    counts = {
        "REAL": sum(1 for r in records if r.source_type == REAL),
        "SIMULATED": sum(1 for r in records if r.source_type == SIMULATED),
        "ESTIMATED": sum(1 for r in records if r.source_type == ESTIMATED),
        "MISSING": sum(1 for r in records if r.source_type == MISSING),
    }
    payload = {
        "run_id": run_id,
        "summary": counts,
        "war_room_ready": counts["REAL"] >= 3,
        "metrics": [r.to_dict() for r in records],
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info(f"[PROVENANCE] Written: {out}")
    return out


def load_provenance(run_id: Optional[str] = None) -> Optional[dict]:
    """Load the latest (or specific run_id) provenance JSON."""
    try:
        if run_id:
            p = PROVENANCE_DIR / f"{run_id}__metric_provenance.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        # Latest
        matches = sorted(PROVENANCE_DIR.glob("*__metric_provenance.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return json.loads(matches[0].read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"[PROVENANCE] Could not load provenance: {e}")
    return None
