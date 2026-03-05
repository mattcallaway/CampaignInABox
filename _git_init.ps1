git config user.email "campaign@example.com"
git config user.name "Campaign In A Box"
git add scripts/lib/ scripts/validation/ scripts/ingest.py scripts/run_pipeline.py scripts/geography/boundary_loader.py scripts/verify_run.py .gitattributes data/ staging/
git commit -m "feat: restructure data paths, add ingestion pipeline, lib/classify+fips+hashing, validation/, boundary index scaffold"
git add derived/ votes/2024/CA/Sonoma/ logs/ reports/ needs/
git commit -m "derived: first Sonoma run 2026-03-04__230432__6e40c8bc__msi + partial validation run"
