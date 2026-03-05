"""
scripts/lib/integrity.py

Precinct data integrity enforcement.
Enforces: 0 ≤ ballots_cast ≤ registered, 0 ≤ yes+no ≤ ballots_cast.
All repairs are logged and exported to diagnostics.

This is a guardrail step — runs after allocation, before feature engineering.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def enforce_precinct_constraints(
    df: pd.DataFrame,
    id_col: str = "canonical_precinct_id",
    registered_col: str = "registered",
    ballots_col: str = "ballots_cast",
    yes_col: Optional[str] = "yes_votes",
    no_col: Optional[str] = "no_votes",
    log_ctx: str = "",
    logger=None,
) -> tuple[pd.DataFrame, dict]:
    """
    Enforce precinct-level constraints deterministically.

    Rules:
      1. registered → cast to integer (round if within 0.01, else log + round)
      2. ballots_cast ≤ registered  (scale down if violated)
      3. yes_votes + no_votes ≤ ballots_cast  (proportional scale-down)
      4. All values ≥ 0

    Returns:
      (repaired_df, repair_report_dict)
    """
    import pandas as pd
    import numpy as np

    out = df.copy()
    repairs: list[dict] = []
    n_rows = len(out)

    def _col(c: Optional[str]) -> Optional[str]:
        return c if c and c in out.columns else None

    reg_c  = _col(registered_col)
    bal_c  = _col(ballots_col)
    yes_c  = _col(yes_col)
    no_c   = _col(no_col)
    id_c   = _col(id_col) or out.columns[0]

    def _to_float(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce").fillna(0)

    # ── 1. Cast registered to integer ─────────────────────────────────────────
    if reg_c:
        reg_f = _to_float(out[reg_c])
        frac  = (reg_f - reg_f.round()).abs()
        anomaly_mask = frac > 0.01
        n_anom = anomaly_mask.sum()
        if n_anom > 0:
            sev = "high" if n_anom > 5 else "medium"
            _log(logger, f"[INTEGRITY] {n_anom} non-integer registered values (severity={sev}) — rounding")
            for pid in out.loc[anomaly_mask, id_c].tolist()[:5]:
                repairs.append(dict(precinct_id=pid, rule="registered_not_integer", severity=sev))
        out[reg_c] = reg_f.round().astype(int)

    # ── 2. ballots_cast ≤ registered ─────────────────────────────────────────
    if reg_c and bal_c:
        reg_v = _to_float(out[reg_c])
        bal_v = _to_float(out[bal_c])
        over_mask = (bal_v > reg_v) & (reg_v > 0)
        n_over = over_mask.sum()
        if n_over > 0:
            _log(logger, f"[INTEGRITY] {n_over}/{n_rows} precincts have ballots_cast > registered — scaling down")
            # Before totals
            before_reg = reg_v.sum()
            before_bal = bal_v.sum()
            # Scale factor per row
            sf = (reg_v / bal_v).clip(upper=1.0)
            new_bal = (bal_v * sf.where(over_mask, 1.0)).round().astype(int)
            # Also scale yes/no
            if yes_c:
                yes_v = _to_float(out[yes_c])
                out[yes_c] = (yes_v * sf.where(over_mask, 1.0)).round().clip(lower=0).astype(int)
            if no_c:
                no_v = _to_float(out[no_c])
                out[no_c] = (no_v * sf.where(over_mask, 1.0)).round().clip(lower=0).astype(int)
            out[bal_c] = new_bal
            for pid in out.loc[over_mask, id_c].tolist():
                repairs.append(dict(precinct_id=pid, rule="ballots_exceeds_registered",
                                    severity="high",
                                    before_bal=float(bal_v[out.index[out[id_c]==pid]].iloc[0]) if any(out[id_c]==pid) else None,
                                    after_bal=float(new_bal[out[id_c]==pid].iloc[0]) if any(out[id_c]==pid) else None))
            _log(logger, f"[INTEGRITY]   County totals: registered={before_reg:,.0f}, "
                          f"ballots before={before_bal:,.0f}, after={new_bal.sum():,.0f}")

    # Re-read after scaling
    if reg_c and bal_c:
        reg_v = _to_float(out[reg_c])
        bal_v = _to_float(out[bal_c])

    # ── 3. yes + no ≤ ballots ─────────────────────────────────────────────────
    if bal_c and yes_c and no_c:
        bal_v2 = _to_float(out[bal_c])
        yes_v  = _to_float(out[yes_c])
        no_v   = _to_float(out[no_c])
        total  = yes_v + no_v
        over2  = total > bal_v2
        n_over2 = over2.sum()
        if n_over2 > 0:
            _log(logger, f"[INTEGRITY] {n_over2} precincts have yes+no > ballots — scaling down")
            sf2 = (bal_v2 / total.replace(0, np.nan)).clip(upper=1.0).fillna(1.0)
            out[yes_c] = (yes_v * sf2).round().clip(lower=0).astype(int)
            out[no_c]  = (no_v  * sf2).round().clip(lower=0).astype(int)
            for pid in out.loc[over2, id_c].tolist():
                repairs.append(dict(precinct_id=pid, rule="yes_no_exceeds_ballots", severity="medium"))

    # ── 4. Non-negative clamp ─────────────────────────────────────────────────
    for c in [c for c in [reg_c, bal_c, yes_c, no_c] if c]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).clip(lower=0)
        if c in [reg_c, bal_c, yes_c, no_c]:
            out[c] = out[c].round().astype(int)

    # ── 5. Recompute turnout_pct ───────────────────────────────────────────────
    if reg_c and bal_c:
        reg_safe = out[reg_c].replace(0, np.nan)
        out["turnout_pct"] = (out[bal_c] / reg_safe).clip(0, 1).fillna(0).round(4)

    # ── 6. Recompute support_pct ──────────────────────────────────────────────
    if yes_c and bal_c:
        bal_safe = pd.to_numeric(out[bal_c], errors="coerce").replace(0, np.nan)
        out["support_pct"] = (pd.to_numeric(out[yes_c], errors="coerce") / bal_safe).clip(0, 1).fillna(0.5).round(4)

    report = {
        "total_rows": n_rows,
        "repaired_rows": len(set(r["precinct_id"] for r in repairs)),
        "repairs": repairs,
        "log_ctx": log_ctx,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    if repairs:
        _log(logger, f"[INTEGRITY] Total repairs: {len(repairs)} events across {report['repaired_rows']} precincts")
    else:
        _log(logger, f"[INTEGRITY] All {n_rows} precincts pass constraints — no repairs needed")

    return out, report


def write_integrity_report(
    report: dict,
    contest_id: str,
    run_id: str,
) -> dict[str, Path]:
    """Write diagnostics CSV and QA markdown for use by audit tools."""
    import pandas as pd

    paths: dict[str, Path] = {}
    diag_dir = BASE_DIR / "derived" / "diagnostics"
    qa_dir   = BASE_DIR / "reports" / "qa"
    diag_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    repairs = report.get("repairs", [])
    if repairs:
        df = pd.DataFrame(repairs)
    else:
        df = pd.DataFrame(columns=["precinct_id", "rule", "severity"])
    csv_path = diag_dir / f"{contest_id}__integrity_repairs.csv"
    df.to_csv(csv_path, index=False)
    paths["integrity_repairs_csv"] = csv_path

    # Markdown QA
    n_repaired = report.get("repaired_rows", 0)
    n_total    = report.get("total_rows", 0)
    status     = "✅ No violations" if n_repaired == 0 else f"⚠️ {n_repaired}/{n_total} precincts repaired"
    rules_used = list({r["rule"] for r in repairs})

    md = f"""# Integrity Repair Report
**Contest:** `{contest_id}`
**Run ID:** `{run_id}`
**Generated:** {report['timestamp']}

## Status: {status}

| Rule | Count |
|---|---|
""" + "\n".join(
        f"| {rule} | {sum(1 for r in repairs if r['rule']==rule)} |"
        for rule in sorted(rules_used)
    ) + ("""
| _(no repairs)_ | — |""" if not rules_used else "") + f"""

## Rule Definitions

| Rule | Description |
|---|---|
| `registered_not_integer` | Fractional `registered` value; rounded to nearest integer |
| `ballots_exceeds_registered` | `ballots_cast > registered`; proportionally scaled down |
| `yes_no_exceeds_ballots` | `yes_votes + no_votes > ballots_cast`; proportionally scaled down |

_Output: `derived/diagnostics/{contest_id}__integrity_repairs.csv`_
"""
    qa_path = qa_dir / f"{run_id}__integrity_repairs.md"
    qa_path.write_text(md, encoding="utf-8")
    paths["integrity_qa_md"] = qa_path

    return paths


def _log(logger, msg: str) -> None:
    if logger:
        try:
            logger.info(msg)
        except Exception:
            print(msg)
    else:
        print(msg)
