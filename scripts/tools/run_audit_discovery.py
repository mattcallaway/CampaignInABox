"""
scripts/tools/run_audit_discovery.py — Campaign In A Box Prompt 23

Produces a comprehensive system inventory for external audit engines.
Outputs:
  reports/audit_discovery/system_inventory.json
  reports/audit_discovery/system_inventory.md
  reports/audit_discovery/python_dependencies.txt
  reports/audit_discovery/system_health.md
  reports/audit_discovery/export_manifest.json

Run from project root:
  python scripts/tools/run_audit_discovery.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap root ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
OUT  = ROOT / "reports" / "audit_discovery"
OUT.mkdir(parents=True, exist_ok=True)

EXPORT_TIME = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _count_files_by_ext(base: Path) -> dict[str, int]:
    ext_map: dict[str, int] = {}
    EXT_GROUPS = {
        "python": {".py"},
        "csv":    {".csv"},
        "json":   {".json"},
        "yaml":   {".yaml", ".yml"},
        "pkl":    {".pkl"},
        "geo":    {".geojson", ".shp", ".gpkg"},
        "excel":  {".xlsx", ".xls"},
        "text":   {".txt", ".md", ".log"},
        "other":  set(),
    }
    for p in base.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            ext = p.suffix.lower()
            placed = False
            for group, exts in EXT_GROUPS.items():
                if ext in exts:
                    ext_map[group] = ext_map.get(group, 0) + 1
                    placed = True
                    break
            if not placed:
                ext_map["other"] = ext_map.get("other", 0) + 1
    return ext_map


def _list_py_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def _get_imports(py_file: Path) -> list[str]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])
        return sorted(set(imports))
    except Exception:
        return []


def _read_json_safe(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_yaml_keys(p: Path) -> list[str]:
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return list(data.keys()) if isinstance(data, dict) else []
    except Exception:
        return []


def _dir_file_count(p: Path) -> int:
    return sum(1 for _ in p.rglob("*") if _.is_file()) if p.exists() else 0


def _sample_files(p: Path, n: int = 5) -> list[str]:
    if not p.exists():
        return []
    return [str(f.relative_to(ROOT)) for f in sorted(p.rglob("*")) if f.is_file()][:n]


def _log_sizes(log_dir: Path) -> list[dict]:
    results = []
    if not log_dir.exists():
        return results
    for f in sorted(log_dir.rglob("*.log"))[:20]:
        results.append({
            "file": str(f.relative_to(ROOT)),
            "size_bytes": f.stat().st_size,
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Repository Structure
# ─────────────────────────────────────────────────────────────────────────────

def build_repository_structure() -> dict:
    root_dirs = sorted(
        d.name for d in ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    file_counts = _count_files_by_ext(ROOT)
    key_files = [
        f.name for f in ROOT.iterdir()
        if f.is_file() and f.suffix in {".py", ".md", ".txt", ".yml", ".yaml", ".json", ".ps1", ".sh"}
    ]
    return {
        "root_dirs": root_dirs,
        "file_counts": file_counts,
        "key_files": sorted(key_files),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Engine Module Inventory
# ─────────────────────────────────────────────────────────────────────────────

ENGINE_RESPONSIBILITY = {
    "archive_ingest":          "Ingests historical election data into normalized archive",
    "precinct_profiles":       "Builds precinct behavioral profiles from historical data",
    "trend_analysis":          "Computes long-term turnout/support trends per precinct",
    "train_turnout_model":     "Trains Random Forest turnout prediction model",
    "train_support_model":     "Trains Gradient Boosting support/persuasion model",
    "election_similarity":     "Identifies similar historical elections for calibration",
    "generate_archive_summary":"Produces archive_summary.json for state integration",
    "model_calibrator":        "Calibrates model outputs against observed results",
    "lift_models":             "Applies turnout/persuasion lift curves to precincts",
    "scenarios":               "Runs deterministic and Monte Carlo scenario projections",
    "campaign_strategy_ai":    "Generates full strategy recommendations and targeting",
    "state_builder":           "Builds and persists the canonical campaign state store",
    "state_schema":            "Defines and validates campaign state schema",
    "voter_parser":            "Parses and normalizes raw voter file data",
    "persuasion_model":        "Scores voter persuadability using modeled features",
    "turnout_propensity":      "Scores voter likelihood to turn out",
    "auth_manager":            "Manages user authentication and role-based permissions",
    "artifact_validator":      "Validates pipeline output artifacts for integrity",
    "integrity_repairs":       "Auto-repairs common data integrity issues",
    "runtime_loader":          "Loads live field/volunteer runtime data for war room",
}

def build_engine_inventory() -> dict:
    engine_dir = ROOT / "engine"
    subsystems: dict[str, list[dict]] = {}
    for subdir in sorted(engine_dir.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("_") or subdir.name == "__pycache__":
            continue
        modules = []
        for py in _list_py_files(subdir):
            rel = str(py.relative_to(ROOT))
            imports = _get_imports(py)
            modules.append({
                "module_name": py.stem,
                "file_path": rel,
                "responsibility": ENGINE_RESPONSIBILITY.get(py.stem, "Campaign engine module"),
                "import_dependencies": imports,
            })
        if modules:
            subsystems[subdir.name] = modules
    return subsystems


# ─────────────────────────────────────────────────────────────────────────────
# Section 5+6: UI Pages & Sidebar Navigation
# ─────────────────────────────────────────────────────────────────────────────

def build_ui_inventory() -> dict:
    ui_cfg = ROOT / "config" / "ui_pages.yaml"
    pages: list[dict] = []
    nav_structure: list[dict] = []

    if ui_cfg.exists():
        try:
            import yaml
            cfg = yaml.safe_load(ui_cfg.read_text(encoding="utf-8")) or {}
            order = 0
            for section_key, section_data in cfg.items():
                label = section_data.get("label", section_key)
                section_pages = []
                for page in section_data.get("pages", []):
                    p_id = page.get("id", "")
                    p_label = page.get("label", p_id)
                    # Try to infer source file from page label
                    slug = re.sub(r"[^a-z0-9]+", "_", p_label.lower()).strip("_")
                    inferred_src = f"ui/dashboard/{slug}_view.py"
                    pages.append({
                        "page_name": p_id,
                        "label": p_label,
                        "sidebar_section": label,
                        "inferred_source": inferred_src,
                    })
                    section_pages.append({"id": p_id, "label": p_label})
                    order += 1
                nav_structure.append({
                    "section_key": section_key,
                    "label": label,
                    "display_order": order,
                    "pages": section_pages,
                })
        except Exception as e:
            pages = [{"error": str(e)}]

    # Scan actual dashboard view files
    dashboard_dir = ROOT / "ui" / "dashboard"
    view_files = sorted(
        str(f.relative_to(ROOT))
        for f in dashboard_dir.glob("*_view.py")
    ) if dashboard_dir.exists() else []

    return {
        "pages": pages,
        "nav_structure": nav_structure,
        "dashboard_view_files": view_files,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 7: Configuration Files
# ─────────────────────────────────────────────────────────────────────────────

def build_config_inventory() -> list[dict]:
    config_dir = ROOT / "config"
    results = []
    if not config_dir.exists():
        return results
    for f in sorted(config_dir.iterdir()):
        if not f.is_file():
            continue
        entry: dict = {
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "keys_present": [],
        }
        if f.suffix in {".yaml", ".yml"}:
            entry["keys_present"] = _read_yaml_keys(f)
        elif f.suffix == ".json":
            data = _read_json_safe(f)
            entry["keys_present"] = list(data.keys()) if isinstance(data, dict) else []
        results.append(entry)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Section 8+9: Data & Derived Directory Inventories
# ─────────────────────────────────────────────────────────────────────────────

DATA_EXPECTED = {
    "data/elections":        ["SOV or election results CSVs"],
    "data/election_archive": ["Historical election data folders per state/county/year"],
    "data/voters":           ["Voter file CSVs or exports"],
    "data/intelligence":     ["Polling, demographics, registration, ballot return data"],
    "data/campaign_runtime": ["Field activity, budget, volunteer schedule data"],
}

def build_data_inventory() -> dict:
    data_dir = ROOT / "data"
    result: dict[str, dict] = {}
    for rel_path, expected in DATA_EXPECTED.items():
        p = ROOT / rel_path
        result[rel_path] = {
            "exists": p.exists(),
            "file_count": _dir_file_count(p),
            "sample_files": _sample_files(p),
            "expected_content": expected,
            "missing": not p.exists() or _dir_file_count(p) == 0,
        }
    return result


DERIVED_SUBDIRS = [
    "models", "state", "archive", "performance", "strategy",
    "strategies", "simulation", "forecasts", "file_registry",
    "advanced_modeling", "calibration", "war_room",
]

def build_derived_inventory() -> dict:
    derived_dir = ROOT / "derived"
    result: dict[str, dict] = {}
    for sub in DERIVED_SUBDIRS:
        p = derived_dir / sub
        result[sub] = {
            "exists": p.exists(),
            "file_count": _dir_file_count(p),
            "sample_files": _sample_files(p, n=8),
        }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Section 10: Model Inventory
# ─────────────────────────────────────────────────────────────────────────────

def build_model_inventory() -> list[dict]:
    models_dir = ROOT / "derived" / "models"
    result = []
    if not models_dir.exists():
        return result

    for pkl in sorted(models_dir.glob("*.pkl")):
        # Look for companion parameter JSON
        param_file = pkl.with_name(pkl.stem + "_parameters.json")
        params = _read_json_safe(param_file) if param_file.exists() else {}
        result.append({
            "model_name": pkl.stem,
            "file_path": str(pkl.relative_to(ROOT)),
            "size_bytes": pkl.stat().st_size,
            "training_source": params.get("training_source", "derived/archive/normalized_elections.csv"),
            "training_date": params.get("trained_at", "unknown"),
            "training_records": params.get("training_records", "unknown"),
            "feature_count": params.get("feature_count", "unknown"),
            "model_type": params.get("model_type", "unknown"),
            "parameters_file": str(param_file.relative_to(ROOT)) if param_file.exists() else None,
        })

    # Also check for feature importance
    for feat_f in sorted(models_dir.glob("*feature_importance*")):
        result.append({
            "model_name": feat_f.stem,
            "file_path": str(feat_f.relative_to(ROOT)),
            "size_bytes": feat_f.stat().st_size,
            "model_type": "feature_importance_table",
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Section 11+12: Strategy & Simulation Engine
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_FILES = {
    "strategy_generator":    "engine/strategy/campaign_strategy_ai.py",
    "targeting_engine":      "engine/strategy/campaign_strategy_ai.py",
    "scenario_simulator":    "engine/advanced_modeling/scenarios.py",
    "monte_carlo":           "engine/advanced_modeling/scenarios.py",
    "resource_allocator":    "engine/strategy/campaign_strategy_ai.py",
    "lift_models":           "engine/advanced_modeling/lift_models.py",
    "calibration":           "engine/calibration/model_calibrator.py",
}

def build_strategy_inventory() -> dict:
    modules = {}
    for name, rel in STRATEGY_FILES.items():
        p = ROOT / rel
        modules[name] = {
            "file": rel,
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        }

    # Simulation config
    sim_cfg_p = ROOT / "config" / "forecast_scenarios.yaml"
    sim_config: dict = {}
    if sim_cfg_p.exists():
        try:
            import yaml
            sim_config = yaml.safe_load(sim_cfg_p.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    return {
        "strategy_modules": modules,
        "simulation_config": sim_config,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 13: Campaign State Store
# ─────────────────────────────────────────────────────────────────────────────

def build_state_snapshot() -> dict:
    state_dir = ROOT / "derived" / "state" / "latest"
    if not state_dir.exists():
        return {"available": False}
    state_files = sorted(state_dir.glob("*campaign_state.json"))
    if not state_files:
        return {"available": False}
    state = _read_json_safe(state_files[-1])
    # Return keys present and safe top-level values (no PII)
    safe_keys = [
        "campaign_name", "contest_id", "county", "state", "election_date",
        "win_probability", "vote_goal", "health_index", "risk_level",
        "war_room_ready", "real_metrics", "archive_summary",
        "historical_models_active", "run_id",
    ]
    snapshot = {"available": True, "all_keys": list(state.keys())}
    for k in safe_keys:
        if k in state:
            v = state[k]
            # Truncate large objects
            if isinstance(v, (list, dict)) and len(str(v)) > 500:
                snapshot[k] = f"[truncated — {type(v).__name__} with {len(v)} items]"
            else:
                snapshot[k] = v
    return snapshot


# ─────────────────────────────────────────────────────────────────────────────
# Section 14: File Registry Snapshot
# ─────────────────────────────────────────────────────────────────────────────

def build_file_registry_snapshot() -> dict:
    reg_path = ROOT / "derived" / "file_registry" / "latest" / "file_registry.json"
    if not reg_path.exists():
        return {"available": False, "file_count": 0}
    records: list[dict] = []
    try:
        records = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False, "file_count": 0}

    type_counts: dict[str, int] = {}
    prov_counts: dict[str, int] = {}
    missing: list[str] = []

    for r in records:
        ft = r.get("file_type", "unknown")
        pv = r.get("provenance", "unknown")
        type_counts[ft] = type_counts.get(ft, 0) + 1
        prov_counts[pv] = prov_counts.get(pv, 0) + 1
        abs_p = ROOT / r.get("current_path", "")
        if not abs_p.exists():
            missing.append(r.get("current_path", "unknown"))

    return {
        "available": True,
        "file_count": len(records),
        "file_types": type_counts,
        "provenance_categories": prov_counts,
        "missing_files": missing,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 15: Python Dependencies
# ─────────────────────────────────────────────────────────────────────────────

def capture_dependencies() -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception as e:
        return f"ERROR capturing dependencies: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Section 16: Deployment Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEPLOYMENT_PATHS = {
    "Dockerfile":           "deployment/docker/Dockerfile",
    "install_sh":           "deployment/install/install_campaign_in_a_box.sh",
    "install_ps1":          "deployment/install/install_campaign_in_a_box.ps1",
    "run_sh":               "run_campaign_box.sh",
    "run_ps1":              "run_campaign_box.ps1",
    "environment_yml":      "environment.yml",
    "requirements_txt":     "requirements.txt",
    "system_check":         "deployment/scripts/system_check.py",
}

def build_deployment_inventory() -> list[dict]:
    result = []
    for label, rel in DEPLOYMENT_PATHS.items():
        p = ROOT / rel
        result.append({
            "component": label,
            "path": rel,
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Section 17: Logging System
# ─────────────────────────────────────────────────────────────────────────────

def build_log_inventory() -> dict:
    logs_dir = ROOT / "logs"
    if not logs_dir.exists():
        return {"available": False}
    categories = {}
    for sub in sorted(logs_dir.iterdir()):
        if sub.is_dir():
            log_files = _log_sizes(sub)
            categories[sub.name] = {
                "file_count": len(list(sub.rglob("*.log"))),
                "recent_files": log_files,
            }
    return {"available": True, "categories": categories}


# ─────────────────────────────────────────────────────────────────────────────
# Section 18: Security Snapshot
# ─────────────────────────────────────────────────────────────────────────────

def build_security_snapshot() -> dict:
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        return {"gitignore_present": False}

    text = gitignore.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]

    voter_rules    = [l for l in lines if "voter" in l.lower() or "vf_" in l.lower()]
    runtime_rules  = [l for l in lines if "runtime" in l.lower() or "field" in l.lower()]
    donor_rules    = [l for l in lines if "donor" in l.lower() or "finance" in l.lower()]
    archive_rules  = [l for l in lines if "archive" in l.lower()]

    return {
        "gitignore_present": True,
        "total_rules": len(lines),
        "voter_file_rules": voter_rules,
        "runtime_data_rules": runtime_rules,
        "donor_data_rules": donor_rules,
        "archive_rules": archive_rules,
        "all_rules_sample": lines[:30],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 19: Provenance System
# ─────────────────────────────────────────────────────────────────────────────

PROVENANCE_VALUES = ["REAL", "SIMULATED", "ESTIMATED", "EXTERNAL", "MISSING"]

def build_provenance_inventory() -> dict:
    result: dict[str, list[str]] = {v: [] for v in PROVENANCE_VALUES}

    # Check file registry
    reg_path = ROOT / "derived" / "file_registry" / "latest" / "file_registry.json"
    if reg_path.exists():
        try:
            records = json.loads(reg_path.read_text(encoding="utf-8"))
            for r in records:
                pv = r.get("provenance", "").upper()
                if pv in result:
                    result[pv].append(r.get("current_path", "unknown"))
        except Exception:
            pass

    # Scan derived provenance directory
    prov_dir = ROOT / "derived" / "provenance"
    if prov_dir.exists():
        for f in prov_dir.rglob("*.json"):
            try:
                data = _read_json_safe(f)
                pv = (data.get("provenance") or "").upper()
                if pv in result:
                    result[pv].append(str(f.relative_to(ROOT)))
            except Exception:
                pass

    return {
        "possible_values": PROVENANCE_VALUES,
        "datasets_by_provenance": result,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 20: System Health
# ─────────────────────────────────────────────────────────────────────────────

def run_system_health() -> str:
    health_script = ROOT / "deployment" / "scripts" / "system_check.py"
    if not health_script.exists():
        # Generate a basic self-check
        lines = ["# Campaign In A Box — System Health Report", f"Generated: {EXPORT_TIME}", ""]
        checks = [
            ("engine/ directory",        (ROOT / "engine").exists()),
            ("config/ directory",        (ROOT / "config").exists()),
            ("derived/state/",           (ROOT / "derived" / "state").exists()),
            ("derived/models/",          (ROOT / "derived" / "models").exists()),
            ("campaign_config.yaml",     (ROOT / "config" / "campaign_config.yaml").exists()),
            ("ui_pages.yaml",            (ROOT / "config" / "ui_pages.yaml").exists()),
            ("users_registry.json",      (ROOT / "config" / "users_registry.json").exists()),
            ("turnout_model.pkl",        (ROOT / "derived" / "models" / "turnout_model.pkl").exists()),
            ("support_model.pkl",        (ROOT / "derived" / "models" / "support_model.pkl").exists()),
            ("archive_summary.json",     (ROOT / "derived" / "archive" / "archive_summary.json").exists()),
            ("normalized_elections.csv", (ROOT / "derived" / "archive" / "normalized_elections.csv").exists()),
            ("file_registry.json",       (ROOT / "derived" / "file_registry" / "latest" / "file_registry.json").exists()),
            (".gitignore",               (ROOT / ".gitignore").exists()),
        ]
        for label, ok in checks:
            status = "✅ PASS" if ok else "❌ FAIL"
            lines.append(f"| {label:<40} | {status} |")
        return "\n".join(lines)

    try:
        result = subprocess.run(
            [sys.executable, str(health_script)],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT)
        )
        return result.stdout + (result.stderr or "")
    except Exception as e:
        return f"ERROR running system_check.py: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Markdown Renderer
# ─────────────────────────────────────────────────────────────────────────────

def _md_section(title: str, content: str) -> str:
    return f"\n## {title}\n\n{content}\n"


def render_markdown(inventory: dict) -> str:
    lines = [
        "# Campaign In A Box — System Inventory",
        f"**Export Time:** {inventory['export_time']}  ",
        f"**Export By:** Audit Discovery Script v1.0",
        "",
        "---",
    ]

    # Repository Structure
    repo = inventory["repository_structure"]
    lines.append("\n## Repository Structure\n")
    lines.append(f"**Root directories:** {', '.join(repo['root_dirs'])}\n")
    lines.append("**File counts by type:**\n")
    for k, v in repo["file_counts"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append(f"\n**Key root files:** {', '.join(repo['key_files'])}")

    # Engine Inventory
    lines.append("\n## Engine Module Inventory\n")
    for subsystem, modules in inventory["engine_modules"].items():
        lines.append(f"### {subsystem}\n")
        for m in modules:
            lines.append(f"- **{m['module_name']}** — `{m['file_path']}`")
            lines.append(f"  - *{m['responsibility']}*")

    # UI Pages
    lines.append("\n## UI Pages\n")
    lines.append("| Page | Sidebar Section |")
    lines.append("|------|----------------|")
    for p in inventory["ui_inventory"]["pages"]:
        lines.append(f"| {p.get('page_name','—')} | {p.get('sidebar_section','—')} |")

    # Config Files
    lines.append("\n## Configuration Files\n")
    lines.append("| File | Size (bytes) | Keys |")
    lines.append("|------|-------------|------|")
    for c in inventory["config_files"]:
        keys = ", ".join(c.get("keys_present", [])[:8])
        lines.append(f"| {c['filename']} | {c['size_bytes']} | {keys} |")

    # Data Directory
    lines.append("\n## Data Directory\n")
    for path, info in inventory["data_inventory"].items():
        status = "❌ MISSING" if info["missing"] else "✅"
        lines.append(f"- `{path}` {status} — {info['file_count']} files")

    # Derived Directory
    lines.append("\n## Derived/Output Inventory\n")
    for sub, info in inventory["derived_inventory"].items():
        exists = "✅" if info["exists"] else "—"
        lines.append(f"- `derived/{sub}` {exists} — {info['file_count']} files")

    # Models
    lines.append("\n## Trained Models\n")
    for m in inventory["model_inventory"]:
        lines.append(f"- **{m['model_name']}** — `{m['file_path']}` ({m.get('model_type','pkl')})")
        if m.get("training_date") and m.get("training_date") != "unknown":
            lines.append(f"  - Trained: {m['training_date']}, Records: {m.get('training_records','?')}, Features: {m.get('feature_count','?')}")

    # Strategy
    lines.append("\n## Strategy & Simulation Engine\n")
    for name, info in inventory["strategy_engine"]["strategy_modules"].items():
        status = "✅" if info["exists"] else "❌"
        lines.append(f"- `{name}` {status} — `{info['file']}`")

    # State Store
    lines.append("\n## Campaign State Store\n")
    state = inventory["state_snapshot"]
    if state.get("available"):
        lines.append(f"**State keys present:** {', '.join(state.get('all_keys', []))}\n")
        for k in ["contest_id", "county", "state", "risk_level", "win_probability", "historical_models_active"]:
            if k in state:
                lines.append(f"- `{k}`: {state[k]}")
    else:
        lines.append("State store not yet generated. Run pipeline first.")

    # File Registry
    lines.append("\n## File Registry\n")
    reg = inventory["file_registry"]
    if reg.get("available"):
        lines.append(f"- **Total files:** {reg['file_count']}")
        lines.append(f"- **By type:** {reg.get('file_types', {})}")
        lines.append(f"- **By provenance:** {reg.get('provenance_categories', {})}")
        if reg.get("missing_files"):
            lines.append(f"- **Missing files:** {len(reg['missing_files'])}")
    else:
        lines.append("File registry not yet generated.")

    # Deployment
    lines.append("\n## Deployment Configuration\n")
    lines.append("| Component | Path | Status |")
    lines.append("|-----------|------|--------|")
    for d in inventory["deployment"]:
        status = "✅" if d["exists"] else "❌"
        lines.append(f"| {d['component']} | `{d['path']}` | {status} |")

    # Logs
    lines.append("\n## Logging System\n")
    log_inv = inventory["log_inventory"]
    if log_inv.get("available"):
        for cat, info in log_inv.get("categories", {}).items():
            lines.append(f"- `logs/{cat}` — {info['file_count']} log files")
    else:
        lines.append("No logs directory found.")

    # Security
    lines.append("\n## Security Snapshot\n")
    sec = inventory["security"]
    if sec.get("gitignore_present"):
        lines.append(f"- `.gitignore` present: ✅ ({sec['total_rules']} rules)")
        lines.append(f"- Voter file protection rules: {len(sec.get('voter_file_rules', []))}")
        lines.append(f"- Runtime data rules: {len(sec.get('runtime_data_rules', []))}")
        for rule in sec.get("voter_file_rules", []):
            lines.append(f"  - `{rule}`")
    else:
        lines.append("⚠️ .gitignore not found!")

    # Provenance
    lines.append("\n## Provenance System\n")
    prov = inventory["provenance"]
    lines.append(f"**Possible values:** {', '.join(prov['possible_values'])}\n")
    for val, datasets in prov["datasets_by_provenance"].items():
        lines.append(f"- **{val}:** {len(datasets)} datasets")
        for d in datasets[:3]:
            lines.append(f"  - `{d}`")

    lines.append("\n---\n*Generated by Campaign In A Box Audit Discovery Script*")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Campaign In A Box — Audit Discovery Export")
    print("=" * 60)

    print("[1/10] Repository structure...")
    repo_structure = build_repository_structure()

    print("[2/10] Engine module inventory...")
    engine_modules = build_engine_inventory()

    print("[3/10] UI pages & navigation...")
    ui_inventory = build_ui_inventory()

    print("[4/10] Configuration files...")
    config_files = build_config_inventory()

    print("[5/10] Data & derived directories...")
    data_inventory   = build_data_inventory()
    derived_inventory = build_derived_inventory()

    print("[6/10] Model inventory...")
    model_inventory = build_model_inventory()

    print("[7/10] Strategy & simulation engine...")
    strategy_engine = build_strategy_inventory()

    print("[8/10] State store & file registry...")
    state_snapshot = build_state_snapshot()
    file_registry  = build_file_registry_snapshot()

    print("[9/10] Security, logs, provenance, deployment...")
    deployment   = build_deployment_inventory()
    log_inventory = build_log_inventory()
    security      = build_security_snapshot()
    provenance    = build_provenance_inventory()

    print("[10/10] System health check...")
    health_report = run_system_health()

    # ── Assemble master inventory ─────────────────────────────────────────────
    inventory = {
        "export_time":        EXPORT_TIME,
        "export_version":     "1.0",
        "system":             "Campaign In A Box",
        "repository_structure": repo_structure,
        "engine_modules":     engine_modules,
        "ui_inventory":       ui_inventory,
        "config_files":       config_files,
        "data_inventory":     data_inventory,
        "derived_inventory":  derived_inventory,
        "model_inventory":    model_inventory,
        "strategy_engine":    strategy_engine,
        "state_snapshot":     state_snapshot,
        "file_registry":      file_registry,
        "deployment":         deployment,
        "log_inventory":      log_inventory,
        "security":           security,
        "provenance":         provenance,
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    files_generated = []

    json_out = OUT / "system_inventory.json"
    json_out.write_text(json.dumps(inventory, indent=2, default=str), encoding="utf-8")
    files_generated.append("system_inventory.json")
    print(f"  [OK] {json_out.relative_to(ROOT)}")

    md_out = OUT / "system_inventory.md"
    md_out.write_text(render_markdown(inventory), encoding="utf-8")
    files_generated.append("system_inventory.md")
    print(f"  [OK] {md_out.relative_to(ROOT)}")

    deps = capture_dependencies()
    deps_out = OUT / "python_dependencies.txt"
    deps_out.write_text(deps, encoding="utf-8")
    files_generated.append("python_dependencies.txt")
    print(f"  [OK] {deps_out.relative_to(ROOT)}")

    health_out = OUT / "system_health.md"
    health_out.write_text(health_report, encoding="utf-8")
    files_generated.append("system_health.md")
    print(f"  [OK] {health_out.relative_to(ROOT)}")

    manifest = {
        "export_time":      EXPORT_TIME,
        "export_version":   "1.0",
        "system":           "Campaign In A Box",
        "files_generated":  files_generated,
        "output_directory": "reports/audit_discovery/",
        "github_safe":      True,
        "contains_pii":     False,
        "notes":            "Voter files, runtime data, and donor records are excluded per .gitignore rules.",
    }
    manifest_out = OUT / "export_manifest.json"
    manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files_generated.append("export_manifest.json")
    print(f"  [OK] {manifest_out.relative_to(ROOT)}")

    print()
    print("=" * 60)
    print("  AUDIT DISCOVERY EXPORT COMPLETE")
    print("=" * 60)
    for f in files_generated:
        print(f"  >> reports/audit_discovery/{f}")
    print()


if __name__ == "__main__":
    main()
