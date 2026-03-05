"""
Prompt 8 validation runner — runs strategy generator on actual sample data.
"""
import sys, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from scripts.simulation.simulation_engine import run_simulation
from scripts.ops.operations_planner import run_operations_planner
from scripts.strategy.strategy_generator import run_strategy_generator

BASE = Path(__file__).parent.parent.parent
STATE = "CA"
COUNTY = "Sonoma"
CONTEST = "Sonoma_2024_nov2024_general"

# ── Load latest precinct model ─────────────────────────────────────────────
model_files = sorted(
    [f for f in (BASE / "derived" / "precinct_models").rglob("*.csv")
     if ".gitkeep" not in str(f)],
    key=lambda p: p.stat().st_mtime,
    reverse=True
)
if not model_files:
    print("No precinct model found. Exiting.")
    sys.exit(1)

model_path = model_files[0]
print(f"Using model: {model_path.relative_to(BASE)}")
model_df = pd.read_csv(model_path)
print(f"Rows: {len(model_df)}, Cols: {list(model_df.columns)}")

RUN_ID = datetime.datetime.now().strftime("%Y-%m-%d__%H%M%S__prompt8")

# ── Step 1: Simulation Engine ─────────────────────────────────────────────────
print("\n--- Simulation Engine ---")
sim = run_simulation(
    model_df=model_df,
    state=STATE,
    county=COUNTY,
    contest=CONTEST,
    run_id=RUN_ID,
    mode="both",
)
print(f"Deterministic: {len(sim['deterministic'])} rows")
print(f"Monte Carlo:   {len(sim['simulation_results'])} rows")
print(f"Scenario summary: {len(sim['scenario_summary'])} rows")
if sim["win_probability"] is not None:
    print(f"Baseline Win Probability: {sim['win_probability']:.1%}")
    print(f"Median Margin: {sim['median_margin']:+,.0f}")
for k, v in sim["paths"].items():
    print(f"  Written: {v.relative_to(BASE)}")

# ── Step 2: Operations Planner ─────────────────────────────────────────────────
print("\n--- Operations Planner ---")
ops = run_operations_planner(
    model_df=model_df,
    state=STATE,
    county=COUNTY,
    contest=CONTEST,
    run_id=RUN_ID,
)
print(f"Regions: {len(ops['regions'])}")
print(f"Field plan rows: {len(ops['field_plan'])}")
for k, v in ops["paths"].items():
    print(f"  Written: {v.relative_to(BASE)}")

# ── Step 3: Strategy Generator ─────────────────────────────────────────────────
print("\n--- Strategy Generator ---")
pack_dir = run_strategy_generator(
    contest_id="2024_CA_sonoma_nov2024_general",
    run_id=RUN_ID,
    contest_mode="auto",
    forecast_mode="both",
    weeks=6,
    state=STATE,
    county=COUNTY,
    contest_slug=CONTEST,
)

# If blocked (no derived targets), use model_df directly
if pack_dir is None:
    print("  Standard discovery blocked. Running direct-load approach...")
    # Manually build a degraded pack from the model data
    from scripts.simulation.simulation_engine import run_deterministic_forecast
    from scripts.strategy.strategy_generator import (
        write_strategy_pack, infer_contest_mode, compute_win_path,
        compute_focus, compute_field_pace, universe_guidance, update_needs,
        DEFAULT_WEEKS,
    )
    import yaml
    ops_cfg = {}
    cfg_path = BASE / "config" / "field_ops.yaml"
    if cfg_path.exists():
        ops_cfg = yaml.safe_load(cfg_path.read_text()) or {}

    contest_id = f"2024_CA_{COUNTY.lower()}_{CONTEST}"
    inputs = {
        "targets":    model_df,
        "turfs":      pd.DataFrame(),
        "forecasts":  pd.DataFrame(),
        "universes":  pd.DataFrame(),
        "regions":    ops["regions"],
        "field_plan": ops["field_plan"],
        "simulations": sim["simulation_results"],
        "inputs_found":   {"precinct_model": {"path": str(model_path), "hash": "live"}},
        "inputs_missing": ["target_ranking", "walk_turfs", "scenario_forecasts", "precinct_universes"],
        "derived_mode":   "degraded",
        "forecast_mode":  "both",
        "win_probability": sim["win_probability"],
    }
    final_mode, mode_reason = infer_contest_mode(model_df, "auto")
    win_path = compute_win_path(model_df, pd.DataFrame(), sim["simulation_results"], final_mode)
    win_path["win_probability"] = sim["win_probability"]
    focus = compute_focus(model_df, ops["regions"])
    pace_df = compute_field_pace(ops["field_plan"], ops_cfg, weeks=6)
    uni_text = universe_guidance(pd.DataFrame(), False)

    pack_dir = write_strategy_pack(
        contest_id=contest_id,
        run_id=RUN_ID,
        contest_mode=final_mode,
        mode_reason=mode_reason,
        inputs=inputs,
        win_path=win_path,
        focus=focus,
        pace_df=pace_df,
        uni_guidance=uni_text,
        ops_config=ops_cfg,
    )

if pack_dir:
    print(f"\nStrategy Pack: {pack_dir.relative_to(BASE)}")
    for f in sorted(pack_dir.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")

    # Print summary of meta
    meta_path = pack_dir / "STRATEGY_META.json"
    if meta_path.exists():
        import json
        meta = json.loads(meta_path.read_text())
        print(f"\nSTRATEGY_META.json:")
        print(f"  contest_id:    {meta.get('contest_id')}")
        print(f"  contest_mode:  {meta.get('contest_mode')}")
        print(f"  derived_mode:  {meta.get('derived_mode')}")
        print(f"  forecast_mode: {meta.get('forecast_mode')}")
        print(f"  win_probability: {meta.get('topline_metrics', {}).get('win_probability')}")
        ms = meta.get("model_summary", {})
        print(f"  precinct_count: {ms.get('precinct_count')}")
        print(f"  turf_count:     {ms.get('turf_count')}")
        print(f"  region_count:   {ms.get('region_count')}")
        print(f"  scenario_count: {ms.get('scenario_count')}")
        print(f"  recommended_strategy: {meta.get('recommended_strategy', '')}")
