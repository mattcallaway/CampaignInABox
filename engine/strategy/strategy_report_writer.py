"""
engine/strategy/strategy_report_writer.py — Prompt 13

Generates a professional campaign strategy report in Markdown.

Output: reports/strategy/<run_id>__campaign_strategy.md

Sections:
  1. Executive Summary
  2. Vote Path Analysis
  3. Targeting Strategy
  4. Field Program Plan
  5. Budget Allocation
  6. Campaign Timeline
  7. Risk Analysis
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR  = BASE_DIR / "reports" / "strategy"


def _g(cfg: dict, *keys, default=None) -> Any:
    d = cfg
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def _priority_emoji(p: str) -> str:
    return {"High": "🔴 High", "Medium": "🟡 Medium", "Low": "🟢 Low"}.get(p, p)


def write_strategy_report(bundle: dict, run_id: str) -> Path:
    """
    Write the full campaign strategy report.

    Args:
        bundle: Output of campaign_strategy_ai.generate_strategy_bundle()
        run_id: Pipeline run ID

    Returns: Path to written .md file
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{run_id}__campaign_strategy.md"

    cfg    = bundle.get("inputs", {}).get("config", {})
    vp     = bundle.get("vote_path", {})
    budget = bundle.get("budget", {})
    field  = bundle.get("field_strategy", {})
    risks  = bundle.get("risks", [])

    contest_name = _g(cfg, "campaign", "contest_name", default="Campaign")
    contest_type = _g(cfg, "campaign", "contest_type", default="ballot_measure")
    jurisdiction = _g(cfg, "campaign", "jurisdiction", default="")
    election_date = _g(cfg, "campaign", "election_date", default="")
    message = _g(cfg, "strategy", "primary_message", default="")
    generated_at = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")

    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        f"# Campaign Strategy Plan",
        f"## {contest_name}",
        f"",
        f"**Jurisdiction:** {jurisdiction}  ",
        f"**Election Date:** {election_date}  ",
        f"**Contest Type:** {contest_type.replace('_', ' ').title()}  ",
        f"**Generated:** {generated_at}  ",
        f"**Run ID:** `{run_id}`",
        f"",
        "---",
        "",
    ]

    # ── 1. Executive Summary ──────────────────────────────────────────────────
    status_icon = "✅" if vp.get("coverage_rate", 0) >= 1.0 else "⚠️"
    lines += [
        "## 1. Executive Summary",
        "",
    ]
    if message:
        lines += [f"> **Campaign Message:** *{message}*", ""]

    lines += [
        f"**Status:** {status_icon} {'Vote path is achievable with current resources.' if vp.get('coverage_rate',0)>=1.0 else 'Gap exists — resource increase or target adjustment needed.'}",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Registered Voters | {vp.get('registered', 0):,} |",
        f"| Expected Turnout | {vp.get('expected_voters', 0):,} ({vp.get('baseline_turnout_pct', 0):.1%}) |",
        f"| Win Number | **{vp.get('win_number', 0):,} votes** ({_g(cfg,'targets','target_vote_share',default=0.52):.1%}) |",
        f"| Stretch Goal | {vp.get('stretch_number',0):,} votes (incl. {_g(cfg,'targets','win_margin',default=0.04):.0%} buffer) |",
        f"| Vote Path Coverage | {vp.get('coverage_rate',0):.1%} |",
        f"| Days to Election | {field.get('days_to_election', 0)} |",
        f"| Total Budget | ${budget.get('total', 0):,} |",
        "",
        "**Recommended Strategy:**",
    ]

    # Strategy recommendation
    pers_p = _g(cfg, "strategy", "persuasion_priority", default="High")
    gotv_p = _g(cfg, "strategy", "turnout_priority", default="Medium")
    if pers_p == "High" and gotv_p == "High":
        rec = "Balanced persuasion + GOTV program — hit both simultaneously via targeted field."
    elif pers_p == "High":
        rec = "Lead with persuasion field program; deploy GOTV mail in final 3 weeks."
    else:
        rec = "Lead with GOTV mobilization of base supporters; use mail for persuasion."
    lines += [f"*{rec}*", ""]

    # High risks
    high_risks = [r for r in risks if r.get("level") == "HIGH"]
    if high_risks:
        lines += ["**⚠️ High Priority Risks:**"]
        for r in high_risks:
            lines += [f"- **{r['risk']}** — {r['description']}"]
        lines += [""]

    lines += ["---", ""]

    # ── 2. Vote Path ──────────────────────────────────────────────────────────
    lines += [
        "## 2. Vote Path Analysis",
        "",
        "```",
        f"  Registered:              {vp.get('registered', 0):>10,}",
        f"  Expected Voters:         {vp.get('expected_voters', 0):>10,}  ({vp.get('baseline_turnout_pct', 0):.1%} turnout)",
        f"  ─────────────────────────────────────",
        f"  Win Number:              {vp.get('win_number', 0):>10,}  ({_g(cfg,'targets','target_vote_share',default=0.52):.1%})",
        f"",
        f"  Base Committed Votes:    {vp.get('base_votes', 0):>10,}",
        f"  Persuasion Needed:       {vp.get('persuasion_votes_needed', 0):>10,}",
        f"  GOTV Turnout Needed:     {vp.get('gotv_votes_needed', 0):>10,}",
        f"  ─────────────────────────────────────",
        f"  Projected Total:         {vp.get('cumulative_total', 0):>10,}  ({vp.get('coverage_rate', 0):.1%} of win number)",
        "```",
        "",
        "---",
        "",
    ]

    # ── 3. Targeting Strategy ─────────────────────────────────────────────────
    lines += [
        "## 3. Targeting Strategy",
        "",
        f"| Program | Priority | Target Group |",
        f"|---------|----------|--------------|",
        f"| Persuasion | {_priority_emoji(pers_p)} | Persuasion Universe (PS > 0.60) |",
        f"| GOTV | {_priority_emoji(gotv_p)} | Low-TPS supporters (TPS < 0.40) |",
        f"| Base Mob. | {_priority_emoji(_g(cfg,'strategy','base_mobilization_priority',default='Medium'))} | Base supporters with moderate TPS |",
        f"| Mail | {_priority_emoji(_g(cfg,'strategy','mail_priority',default='Medium'))} | High-value persuasion precincts |",
        f"| Digital | {_priority_emoji(_g(cfg,'strategy','digital_priority',default='Low'))} | Young voters + digital-first segments |",
        "",
    ]

    coalition = _g(cfg, "strategy", "coalition_targets", default=[])
    if coalition:
        lines += [f"**Coalition Targets:** {', '.join(coalition)}", ""]

    geo_targets = _g(cfg, "strategy", "key_geographic_targets", default=[])
    if geo_targets:
        lines += [f"**Priority Geographies:** {', '.join(geo_targets)}", ""]

    lines += ["---", ""]

    # ── 4. Field Program ──────────────────────────────────────────────────────
    lines += [
        "## 4. Field Program Plan",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Doors Needed | {field.get('total_doors_needed', 0):,} |",
        f"| Persuasion Doors | {field.get('persuasion_doors_needed', 0):,} |",
        f"| GOTV Doors | {field.get('gotv_doors_needed', 0):,} |",
        f"| Doors/Week Needed | {field.get('doors_per_week_needed', 0):,} |",
        f"| Volunteer Capacity/Week | {field.get('volunteer_doors_per_week', 0):,} doors |",
        f"| Paid Canvassers Needed | {field.get('paid_canvassers_needed', 0)} |",
        f"| Weeks to Election | {field.get('weeks_to_election', 0):.1f} |",
        "",
        "### Weekly Canvassing Plan",
        "",
        "| Week | Persuasion Doors | GOTV Doors | Total | Persuasion Contacts | GOTV Contacts |",
        "|------|-----------------|-----------|-------|--------------------:|-------------:|",
    ]
    for wk in field.get("weekly_plan", [])[:16]:  # cap at 16 weeks
        lines.append(
            f"| {wk['week']:>4} | {wk['persuasion_doors']:>15,} | {wk['gotv_doors']:>9,} | "
            f"{wk['total_doors']:>5,} | {wk['expected_persuasion_contacts']:>19,} | {wk['expected_gotv_contacts']:>13,} |"
        )
    lines += ["", "---", ""]

    # ── 5. Budget Plan ────────────────────────────────────────────────────────
    total_b = budget.get("total", 1)
    roi = budget.get("roi_estimates", {})
    lines += [
        "## 5. Budget Allocation",
        "",
        f"**Total Budget:** ${total_b:,}  *(Method: {budget.get('method','explicit')})*",
        "",
        f"| Program | Budget | % of Total | Est. Reach |",
        f"|---------|--------|-----------|-----------|",
        f"| Field Canvassing | ${budget.get('field',0):,} | {budget.get('field',0)/total_b:.0%} | {roi.get('field_contacts_possible',0):,} contacts |",
        f"| Mail | ${budget.get('mail',0):,} | {budget.get('mail',0)/total_b:.0%} | {roi.get('mail_pieces_possible',0):,} pieces |",
        f"| Digital | ${budget.get('digital',0):,} | {budget.get('digital',0)/total_b:.0%} | {roi.get('digital_impressions',0):,} impressions |",
        f"| Research | ${budget.get('research',0):,} | {budget.get('research',0)/total_b:.0%} | Ongoing |",
        "",
        "---",
        "",
    ]

    # ── 6. Timeline ────────────────────────────────────────────────────────────
    days = field.get("days_to_election", 90)
    weeks = field.get("weeks_to_election", 12)
    lines += [
        "## 6. Campaign Timeline",
        "",
        f"**{days} days ({weeks:.1f} weeks) remaining**",
        "",
        "| Phase | Timing | Focus |",
        "|-------|--------|-------|",
    ]
    if weeks >= 10:
        lines.append(f"| Research & ID | Now – Week 4 | Voter contact, persuasion ID |")
    if weeks >= 7:
        lines.append(f"| Persuasion | Week {"5" if weeks>=10 else "1"} – Week {max(int(weeks)-4, 2)} | Field + mail persuasion |")
    lines += [
        f"| GOTV Ramp | Final 4 weeks | VBM chase, election protection |",
        f"| Election Day | Day 0 | Phone bank, ride shares, poll monitoring |",
        "",
        "---",
        "",
    ]

    # ── 7. Risk Analysis ──────────────────────────────────────────────────────
    lines += [
        "## 7. Risk Analysis",
        "",
        "| Risk | Level | Description | Mitigation |",
        "|------|-------|-------------|-----------|",
    ]
    for r in risks:
        lvl = {"HIGH": "🔴 HIGH", "MEDIUM": "🟡 MEDIUM", "LOW": "🟢 LOW"}.get(r.get("level", ""), r.get("level", ""))
        lines.append(f"| {r['risk']} | {lvl} | {r['description']} | {r['mitigation']} |")
    lines += ["", "---", ""]

    # ── Footer ────────────────────────────────────────────────────────────────
    lines += [
        f"*Generated by Campaign In A Box — Run ID: `{run_id}` — {generated_at}*",
        "",
        "> **Security note:** This report contains no individual voter data. "
        "All figures are precinct-level aggregates.",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
