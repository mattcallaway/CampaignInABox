"""
scripts/ops/simulation_engine.py

Computes "Net Gain" and simulates campaign impact under different field scenarios.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

def run_net_gain_simulation(
    df: pd.DataFrame,
    ops_config: Dict[str, Any],
    contest_mode: str = "measure"
) -> pd.DataFrame:
    """
    Compute expected impact of field work.
    """
    sim_df = df.copy()
    
    persuasion_lift = ops_config.get("persuasion_effect_per_contact", 0.02)
    turnout_lift = ops_config.get("turnout_effect_per_contact", 0.05)
    
    # 1. Identify Universes (Assumes universe_name exists from universe_builder)
    # If not present, we assume all are potentially bridgeable but with lower effect
    is_persuade = sim_df["universe_name"].str.contains("Persuasion", case=False, na=False)
    is_base = sim_df["universe_name"].str.contains("Mobilization|Base", case=False, na=False)
    
    # 2. Compute Net Gain
    # Measure Mode: Contacts in persuasion universe lift support_pct
    # Turnout Mode: Contacts in base universe lift turnout_pct
    
    # For simplification at precinct level:
    # expected_net_gain = (contacts * persuasion_lift * weight) + (contacts * turnout_lift * weight)
    
    # Turnout Gain: contacts * turnout_lift * support_pct (assuming they vote for us if mobilized)
    sim_df["net_gain_turnout"] = np.where(
        is_base,
        sim_df["expected_contacts"] * turnout_lift * sim_df["support_pct"],
        sim_df["expected_contacts"] * (turnout_lift * 0.2) * sim_df["support_pct"] # small bleed effect
    )
    
    # Persuasion Gain: contacts * persuasion_lift * expected_active_voters
    sim_df["net_gain_persuasion"] = np.where(
        is_persuade,
        sim_df["expected_contacts"] * persuasion_lift,
        sim_df["expected_contacts"] * (persuasion_lift * 0.1) # small bleed effect
    )
    
    sim_df["expected_net_gain"] = sim_df["net_gain_turnout"] + sim_df["net_gain_persuasion"]
    
    return sim_df

def simulate_scenarios(
    plan_df: pd.DataFrame,
    ops_config: Dict[str, Any]
) -> pd.DataFrame:
    """
    Simulate overall campaign outcomes under field levels.
    """
    base_registered = plan_df["registered"].sum()
    base_turnout = plan_df["turnout_pct"].mean()
    base_support = plan_df["support_pct"].mean()
    
    scenarios = [
        {"id": "baseline", "name": "Baseline (No Field)", "effort": 0.0},
        {"id": "field_light", "name": "Field Light (30% Capacity)", "effort": 0.3},
        {"id": "field_medium", "name": "Field Medium (70% Capacity)", "effort": 0.7},
        {"id": "field_heavy", "name": "Field Heavy (100% Capacity)", "effort": 1.0},
    ]
    
    results = []
    
    # ── Master / Top-Level ──
    for scn in scenarios:
        effort = scn["effort"]
        total_gain = plan_df["expected_net_gain"].sum() * effort
        adj_votes_baseline = base_registered * base_turnout * base_support
        adj_votes_final = adj_votes_baseline + total_gain
        results.append({
            "jurisdiction": "All",
            "scenario_id": scn["id"],
            "scenario_name": scn["name"],
            "effort_level": effort,
            "net_vote_gain": int(total_gain) if pd.notna(total_gain) else 0,
            "projected_support_votes": int(adj_votes_final) if pd.notna(adj_votes_final) else 0,
            "win_margin_estimate": int(adj_votes_final - (base_registered * base_turnout * 0.5)) if pd.notna(adj_votes_final) else 0
        })
        
    # ── Prompt 19: Per-Jurisdiction ──
    if "county" in plan_df.columns:
        for county, group in plan_df.groupby("county"):
            g_reg = group["registered"].sum()
            g_turn = group["turnout_pct"].mean()
            g_supp = group["support_pct"].mean()
            for scn in scenarios:
                effort = scn["effort"]
                t_gain = group["expected_net_gain"].sum() * effort
                a_base = g_reg * g_turn * g_supp
                a_fin = a_base + t_gain
                results.append({
                    "jurisdiction": county,
                    "scenario_id": scn["id"],
                    "scenario_name": scn["name"],
                    "effort_level": effort,
                    "net_vote_gain": int(t_gain) if pd.notna(t_gain) else 0,
                    "projected_support_votes": int(a_fin) if pd.notna(a_fin) else 0,
                    "win_margin_estimate": int(a_fin - (g_reg * g_turn * 0.5)) if pd.notna(a_fin) else 0
                })

        
    return pd.DataFrame(results)
