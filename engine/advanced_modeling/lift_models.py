"""
engine/advanced_modeling/lift_models.py — Prompt 10

Saturating lift curves and application to precinct baselines.

Core formula (from spec):
    lift(contacts) = max_lift * (1 - exp(-k * contacts))

Lift is applied to:
    turnout_new  = clamp(turnout_base  + turnout_lift,    0, 1)
    support_new  = clamp(support_base  + persuasion_lift * direction, 0, 1)

Expected votes are derived from:
    expected_yes_votes     = registered * turnout_new * support_new
    expected_yes_votes_old = registered * turnout_base * support_base
    added_votes_yes        = expected_yes_votes - expected_yes_votes_old
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent
_FIELD_EFFECTS_PATH = _ROOT / "config" / "field_effects.yaml"


def _load_field_effects() -> dict:
    """Load field_effects.yaml. Returns empty dict on failure."""
    try:
        import yaml
        if _FIELD_EFFECTS_PATH.exists():
            data = yaml.safe_load(_FIELD_EFFECTS_PATH.read_text(encoding="utf-8")) or {}
            log.debug(f"[LIFT_MODELS] Loaded field_effects.yaml from {_FIELD_EFFECTS_PATH}")
            return data
    except Exception as e:
        log.warning(f"[LIFT_MODELS] Could not load field_effects.yaml: {e}")
    return {}


_FIELD_EFFECTS_CACHE: dict | None = None


def _get_field_effects() -> dict:
    """Cached load of field_effects.yaml."""
    global _FIELD_EFFECTS_CACHE
    if _FIELD_EFFECTS_CACHE is None:
        _FIELD_EFFECTS_CACHE = _load_field_effects()
    return _FIELD_EFFECTS_CACHE



# ── Core lift functions ────────────────────────────────────────────────────────

def turnout_lift(
    contacts: float,
    max_lift: float = 0.08,
    k: float = 0.0008,
) -> float:
    """
    Saturating turnout lift given contacts.
    Returns a fractional lift (0–max_lift).
    """
    return max_lift * (1.0 - math.exp(-k * max(0.0, contacts)))


def persuasion_lift(
    contacts: float,
    max_lift: float = 0.06,
    k: float = 0.0010,
) -> float:
    """
    Saturating persuasion lift given contacts.
    Returns a fractional lift (0–max_lift).
    """
    return max_lift * (1.0 - math.exp(-k * max(0.0, contacts)))


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ── Vectorized versions ────────────────────────────────────────────────────────

def turnout_lift_vec(contacts: pd.Series, max_lift: float = 0.08, k: float = 0.0008) -> pd.Series:
    return max_lift * (1.0 - np.exp(-k * contacts.clip(lower=0)))


def persuasion_lift_vec(contacts: pd.Series, max_lift: float = 0.06, k: float = 0.0010) -> pd.Series:
    return max_lift * (1.0 - np.exp(-k * contacts.clip(lower=0)))


# ── Apply lifts to precinct-level DataFrame ────────────────────────────────────

def apply_lifts(
    universe_df: pd.DataFrame,
    contacts_col: str = "contacts_estimated",
    cfg: Optional[dict] = None,
    persuasion_direction: int = 1,
) -> pd.DataFrame:
    """
    Apply turnout + persuasion lifts to each precinct row.

    Config priority for k (decay rate) parameters:
      1. cfg['curves']['k_turnout'] / 'k_persuasion'  (advanced_modeling.yaml)
      2. field_effects.yaml gotv.door_knock_lift / persuasion.door_knock_swing (scaled)
      3. Hardcoded defaults (0.0008 turnout, 0.0010 persuasion)

    Historical trend flag:
      cfg.get('apply_historical_trends', False) — when True, adds t_trend/s_trend
      to baseline only (not additive with lift). Default: False to prevent
      double-counting when baselines already reflect historical trends.

    Parameters
    ----------
    universe_df : DataFrame with registered, turnout_pct (baseline), support_pct (baseline),
                  contacts_estimated
    contacts_col: column containing estimated contacts per precinct
    cfg         : advanced_modeling config dict
    persuasion_direction: +1 lifts YES share, -1 lifts NO share

    Returns
    -------
    DataFrame with added columns: turnout_lift, persuasion_lift,
        turnout_new, support_new, expected_added_votes_yes,
        expected_added_votes_no, net_margin_gain
    """
    cfg = cfg or {}
    curves = cfg.get("curves", {})
    fe     = _get_field_effects()

    # ── Resolve max_lift from cfg (advanced_modeling.yaml > defaults)
    max_to = curves.get("max_turnout_lift_pct",   0.08)
    max_pe = curves.get("max_persuasion_lift_pct", 0.06)

    # ── Resolve k (decay rate) — priority: cfg > field_effects.yaml > default
    # field_effects.yaml door_knock_lift is a per-contact value; we scale it to k
    # via: k ≈ field_effect_per_contact * 2   (approximation for saturation point)
    fe_gotv_lift = fe.get("gotv", {}).get("door_knock_lift", None)
    fe_pers_swing = fe.get("persuasion", {}).get("door_knock_swing", None)

    default_k_to = 0.0008
    default_k_pe = 0.0010

    if "k_turnout" in curves:
        k_to = float(curves["k_turnout"])
        k_to_source = "advanced_modeling.yaml"
    elif fe_gotv_lift is not None:
        # Scale field_effects per-contact lift to k parameter
        k_to = float(fe_gotv_lift) * 40.0   # 40x scale factor keeps saturation ~1000 contacts
        k_to_source = "field_effects.yaml (gotv.door_knock_lift scaled)"
    else:
        k_to = default_k_to
        k_to_source = "hardcoded default"

    if "k_persuasion" in curves:
        k_pe = float(curves["k_persuasion"])
        k_pe_source = "advanced_modeling.yaml"
    elif fe_pers_swing is not None:
        k_pe = float(fe_pers_swing) * 50.0
        k_pe_source = "field_effects.yaml (persuasion.door_knock_swing scaled)"
    else:
        k_pe = default_k_pe
        k_pe_source = "hardcoded default"

    log.info(
        f"[LIFT_MODELS] Resolved lift params: "
        f"max_to={max_to:.4f} max_pe={max_pe:.4f} "
        f"k_to={k_to:.6f} [{k_to_source}] "
        f"k_pe={k_pe:.6f} [{k_pe_source}]"
    )

    df = universe_df.copy()

    # ── Column resolver with explicit warning on missing critical columns
    def _c(*names, critical: bool = False):
        for n in names:
            if n in df.columns:
                return df[n].fillna(0)
        if critical:
            log.warning(
                f"[LIFT_MODELS] Critical column(s) {names} not found in DataFrame. "
                f"Defaulting to 0.0 — this will impact vote projections. "
                f"Available columns: {list(df.columns)[:10]}"
            )
        return pd.Series(0.0, index=df.index)

    reg      = _c("registered", critical=True).clip(lower=0)
    to_base  = _c("turnout_pct", "turnout_rate", critical=True).clip(0, 1)
    sup_base = _c("support_pct", "yes_rate", critical=True).clip(0, 1)
    contacts = _c(contacts_col, "contacts_estimated").clip(lower=0)

    # ── Lift curves
    t_lift = turnout_lift_vec(contacts, max_to, k_to)
    p_lift = persuasion_lift_vec(contacts, max_pe, k_pe)

    # ── Historical trends — apply to baseline only if flag set (C01 fix for M-01)
    # Default is False to prevent double-counting with pre-trended baselines
    apply_trends = bool(cfg.get("apply_historical_trends", False))
    if apply_trends:
        t_trend = _c("historical_turnout_trend")
        s_trend = _c("historical_support_trend")
        to_base_adj  = (to_base  + t_trend).clip(0, 1)
        sup_base_adj = (sup_base + s_trend).clip(0, 1)
        log.info("[LIFT_MODELS] Historical trends applied to baseline (apply_historical_trends=True)")
    else:
        to_base_adj  = to_base
        sup_base_adj = sup_base

    # ── Apply lifts
    to_new  = (to_base_adj  + t_lift).clip(0, 1)
    sup_new = (sup_base_adj + p_lift * persuasion_direction).clip(0, 1)

    # ── Vote math
    baseline_yes   = (reg * to_base  * sup_base).clip(lower=0)
    projected_yes  = (reg * to_new   * sup_new).clip(lower=0)
    baseline_no    = (reg * to_base  * (1 - sup_base)).clip(lower=0)
    projected_no   = (reg * to_new   * (1 - sup_new)).clip(lower=0)

    added_yes = (projected_yes - baseline_yes).clip(lower=0)
    added_no  = (projected_no  - baseline_no).clip(lower=0)
    net_gain  = added_yes - added_no

    df["turnout_lift"]              = t_lift.round(6)
    df["persuasion_lift"]           = p_lift.round(6)
    df["turnout_new"]               = to_new.round(6)
    df["support_new"]               = sup_new.round(6)
    df["expected_added_votes_yes"]  = added_yes.round(2)
    df["expected_added_votes_no"]   = added_no.round(2)
    df["net_margin_gain"]           = net_gain.round(2)

    return df



# ── Monte Carlo wrapper ────────────────────────────────────────────────────────

def apply_lifts_mc(
    universe_df: pd.DataFrame,
    contacts_col: str = "contacts_estimated",
    cfg: Optional[dict] = None,
    n_iter: int = 200,
    seed: int = 1337,
    persuasion_direction: int = 1,
) -> pd.DataFrame:
    """
    Monte Carlo version: samples elasticity priors for each iteration.
    Returns aggregate (mean, p10, p90) across iterations for the full DataFrame.
    Only aggregates net_margin_gain.
    """
    cfg     = cfg or {}
    curves  = cfg.get("curves", {})
    elast   = cfg.get("elasticity", {})

    rng = np.random.default_rng(seed)
    results = []

    to_mean = elast.get("turnout_lift_per_contact_mean", 0.004)
    to_sd   = elast.get("turnout_lift_per_contact_sd",   0.002)
    pe_mean = elast.get("persuasion_lift_per_contact_mean", 0.006)
    pe_sd   = elast.get("persuasion_lift_per_contact_sd",   0.003)

    max_to_base = curves.get("max_turnout_lift_pct",   0.08)
    max_pe_base = curves.get("max_persuasion_lift_pct", 0.06)

    for _ in range(n_iter):
        # Sample uncertain max_lift from prior
        sampled_max_to = float(rng.normal(max_to_base, to_mean * 3))
        sampled_max_pe = float(rng.normal(max_pe_base, pe_mean * 3))
        sampled_max_to = max(0.0, sampled_max_to)
        sampled_max_pe = max(0.0, sampled_max_pe)

        cfg_i = dict(cfg)
        cfg_i["curves"] = dict(curves)
        cfg_i["curves"]["max_turnout_lift_pct"]   = sampled_max_to
        cfg_i["curves"]["max_persuasion_lift_pct"] = sampled_max_pe

        lifted = apply_lifts(universe_df, contacts_col, cfg_i, persuasion_direction)
        results.append(lifted["net_margin_gain"].sum())

    arr = np.array(results)
    return {
        "net_gain_mean": float(arr.mean()),
        "net_gain_p10":  float(np.percentile(arr, 10)),
        "net_gain_p90":  float(np.percentile(arr, 90)),
        "net_gain_sd":   float(arr.std()),
    }
