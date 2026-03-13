# Fix Prompt: UI Integration Fixes
**Campaign In A Box | Prompt 23 Audit Fix Prompts**

---

## Objective
Fix the dead code block in `app.py` and replace deprecated Streamlit API calls across all dashboard views.

---

## Fix 1: Remove Dead Code Block in `app.py`

**File:** `ui/dashboard/app.py`
**Lines:** ~249-259

The sidebar footer rendering block is inside an `except` block after `st.stop()`. This code is unreachable.

**Action:** Move the footer rendering outside and above the `st.stop()` call, or into a dedicated `render_sidebar_footer()` function called before the error block.

---

## Fix 2: Replace Deprecated `use_container_width` in All Views

**Files:** All `ui/dashboard/*_view.py` and `ui/dashboard/app.py`

**Find and replace:**
```python
# Old (deprecated after 2025-12-31):
st.dataframe(df, use_container_width=True)
st.dataframe(df, use_container_width=False)

# New:
st.dataframe(df, width='stretch')
st.dataframe(df, width='content')
```

Run the following search to find all occurrences:
```powershell
Select-String -Path "ui\dashboard\*.py" -Pattern "use_container_width"
```

---

## Fix 3: Add ESTIMATED Mode Banner to War Room View

**File:** `ui/dashboard/war_room_view.py`

When war room data is operating in ESTIMATED-only mode (no REAL field data), display a clear banner:

```python
# At top of render_war_room()
runtime = state.get("war_room_summary", {})
presence = runtime.get("presence", {})
has_real_data = any(presence.values())

if not has_real_data:
    st.warning(
        "⚠️ War Room operating on ESTIMATED data only. "
        "Upload field results in Data Manager to activate REAL tracking.",
        icon="⚠️"
    )
```

---

## Fix 4: Add Cache TTL Control to Data Loader

**File:** `ui/dashboard/data_loader.py`

Add a configurable cache TTL that can be reduced for war room mode:

```python
import os
_CACHE_TTL = int(os.environ.get("CIAB_CACHE_TTL", "120"))

@st.cache_data(ttl=_CACHE_TTL, show_spinner="Loading campaign data...")
def get_data() -> dict:
    return load_all()
```

Set `CIAB_CACHE_TTL=30` in war room mode for near-real-time updates.
