import logging
logging.basicConfig(level=logging.INFO)
import sys
sys.path.insert(0, '.')

# Phase 1: Archive ingest
from engine.archive.archive_ingest import run_ingest
df = run_ingest(run_id='20260312__p24')
prov_real = df['provenance'].isin(['REAL','EXTERNAL']).any()
print(f'Archive: {len(df)} records, real={prov_real}')

# Phase 2: Precinct profiles
from engine.archive.precinct_profiles import build_profiles
profiles = build_profiles(run_id='20260312__p24')
print(f'Profiles: {len(profiles) if profiles is not None else 0}')

# Phase 2: Trends
from engine.archive.trend_analysis import compute_trends
trends = compute_trends(run_id='20260312__p24')
print(f'Trends: {len(trends) if trends is not None else 0}')

# Phase 2: Similarity
from engine.archive.election_similarity import run_similarity
sim = run_similarity(run_id='20260312__p24')
print(f'Similarity: {len(sim) if sim is not None else 0}')

# Phase 3: Train + calibrate support model
from engine.archive.train_support_model import train_model
params = train_model(run_id='20260312__p24')
print(f'Model trained: {params is not None}')

# Phase 5: File registry
from engine.data_intake.file_registry_pipeline import run_registry_pipeline
reg = run_registry_pipeline(run_id='20260312__p24')
print(f'Registry active={reg["active_files_found"]} missing={reg["missing_files_count"]}')

print('ALL PHASES COMPLETE')
