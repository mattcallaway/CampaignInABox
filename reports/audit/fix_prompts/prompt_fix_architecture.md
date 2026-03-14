# Fix Prompt: Architecture & Technical Debt Cleanup
**Campaign In A Box | Prompt 23 Audit Fix Prompts**

---

## Objective
Clean up architectural technical debt: shared utility extraction, tmp file removal, and orphan module cleanup.

---

## Fix 1: Create Shared `engine/utils/helpers.py`

**New file:** `engine/utils/helpers.py`

```python
"""
engine/utils/helpers.py — Shared utilities for all engine modules.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Optional
import pandas as pd

# Canonical project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

log = logging.getLogger(__name__)


def g(d: dict, *keys, default=None) -> Any:
    """Safe nested dict accessor. Returns default if any key is missing."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def find_latest_csv(directory: Path, pattern: str) -> Optional[pd.DataFrame]:
    """Find the most recently written CSV matching pattern in directory."""
    try:
        matches = sorted(
            directory.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return pd.read_csv(matches[0], index_col=False)
    except Exception as e:
        log.debug(f"[HELPERS] find_latest_csv({directory}, {pattern}): {e}")
    return None


def load_yaml(path: Path) -> dict:
    """Safely load YAML file. Returns empty dict on error."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.warning(f"[HELPERS] Could not load YAML {path}: {e}")
        return {}
```

**After creation:** Update all engine files to import from `engine.utils.helpers` instead of defining their own `_g()` and `_find_latest()`.

---

## Fix 2: Delete `tmp_patch_*.py` Files

Run the following one-time cleanup (safe — these are development artifacts):

```powershell
# From project root:
Remove-Item tmp_patch_app.py, tmp_patch_app_login.py, tmp_patch_app_v.py
Remove-Item tmp_patch_diag.py, tmp_patch_dm.py, tmp_patch_footer.py
Remove-Item tmp_patch_lift_models.py, tmp_patch_map.py, tmp_patch_nav.py
Remove-Item tmp_patch_readme.py, tmp_patch_strat.py, tmp_patch_strategy.py
Remove-Item tmp_patch_ui.py, tmp_patch_wr.py, tmp_fix_pipeline.py
Remove-Item tmp_gen_ca.py, tmp_refactor.py, tmp_update_collab.py
Remove-Item tmp_update_sim.py, tmp_update_state_builder.py
```

**Safety note:** Review each file before deletion to confirm no logic needs to be preserved.

---

## Fix 3: Split `campaign_strategy_ai.py` (548 lines)

**Target structure:**
```
engine/strategy/
  __init__.py
  vote_path.py          ← extract compute_vote_path()
  budget_allocator.py   ← extract compute_budget_allocation()
  field_strategy.py     ← extract compute_field_strategy()
  risk_analyzer.py      ← extract generate_risk_analysis()
  campaign_strategy_ai.py  ← thin orchestrator that imports from above
```

This refactor does not change any logic — only separates concerns.

---

## Fix 4: Add pytest Test Suite

**New directory:** `tests/`

```python
# tests/test_lift_models.py
import pytest
import pandas as pd
from engine.advanced_modeling.lift_models import apply_lifts

def test_apply_lifts_basic():
    df = pd.DataFrame([{
        "registered": 5000,
        "turnout_pct": 0.55,
        "support_pct": 0.51,
        "contacts_estimated": 500,
    }])
    result = apply_lifts(df)
    assert result["turnout_new"].iloc[0] > 0.55
    assert result["support_new"].iloc[0] > 0.51
    assert result["net_margin_gain"].iloc[0] > 0
    assert result["turnout_new"].iloc[0] <= 1.0
    assert result["support_new"].iloc[0] <= 1.0
```

Run with: `pytest tests/ -v`
