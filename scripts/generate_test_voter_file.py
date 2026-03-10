"""
scripts/generate_test_voter_file.py — Prompt 11 test utility

Generate a synthetic Sonoma County voter file for testing the voter intelligence layer.
Creates realistic-looking data with known precinct IDs from the real precinct model.

Usage:
    python scripts/generate_test_voter_file.py
    python scripts/generate_test_voter_file.py --n 5000

Output: data/voters/CA/Sonoma/voter_file_synthetic.csv (NOT committed — in .gitignore)
"""
import argparse
import random
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

OUTPUT_PATH = BASE_DIR / "data" / "voters" / "CA" / "Sonoma" / "voter_file_synthetic.csv"


def generate(n: int = 2000, seed: int = 42):
    random.seed(seed)

    # Try to load real precinct IDs from the model
    precinct_ids = []
    for pattern in [
        "derived/precinct_models/**/Sonoma*.csv",
        "derived/precinct_models/**/*.csv",
    ]:
        paths = sorted(BASE_DIR.glob(pattern))
        if paths:
            import pandas as pd
            df = pd.read_csv(paths[-1], dtype=str)
            if "canonical_precinct_id" in df.columns:
                precinct_ids = df["canonical_precinct_id"].dropna().tolist()
                print(f"  Using {len(precinct_ids)} real precinct IDs from model")
                break

    if not precinct_ids:
        # Fallback: sample IDs from Sonoma MPREC range
        precinct_ids = [str(i) for i in range(100001, 100391)]
        print(f"  Using {len(precinct_ids)} synthetic precinct IDs (range 100001-100390)")

    parties = ["D", "R", "N", "N", "D", "D", "D"]  # CA weighted distribution
    election_years = [2016, 2018, 2020, 2022, 2024]
    genders = ["M", "F", "U"]
    ethnicities = ["W", "H", "A", "B", "O"]

    rows = []
    for i in range(n):
        voter_id = f"CA{10000000 + i:08d}"
        precinct = random.choice(precinct_ids)
        party = random.choice(parties)
        age = random.randint(18, 85)
        gender = random.choices(genders, weights=[45, 50, 5])[0]
        ethnicity = random.choices(ethnicities, weights=[60, 25, 7, 5, 3])[0]

        # Vote history: more realistic turnout patterns
        # High propensity: regular voters; low propensity: occasional
        propensity_type = random.choices(
            ["high", "medium", "low"],
            weights=[30, 40, 30]
        )[0]
        vh_base = {"high": 0.85, "medium": 0.50, "low": 0.15}[propensity_type]
        vote_history = {
            f"vote_history_{y}": "Y" if random.random() < vh_base else "N"
            for y in election_years
        }

        # Mail ballot: CA skews heavily VBM
        vbm = random.choices(["Y", "N"], weights=[75, 25])[0]

        row = {
            "voter_id": voter_id,
            "precinct": precinct,
            "party": party,
            "age": age,
            "gender": gender,
            "ethnicity": ethnicity,
            "mail_ballot_status": vbm,
            **vote_history,
        }
        rows.append(row)

    import pandas as pd

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nGenerated {n:,} synthetic voters -> {OUTPUT_PATH}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Party distribution:\n{df['party'].value_counts().to_string()}")
    print(f"\nNow run the pipeline to ingest:")
    print(f"  python scripts/run_pipeline.py --state CA --county Sonoma --year 2025 --contest-slug prop_50_special")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic voter file for testing")
    parser.add_argument("--n", type=int, default=2000, help="Number of voters (default: 2000)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(n=args.n, seed=args.seed)
