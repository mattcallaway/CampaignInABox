"""
engine/archive/train_turnout_model.py

Trains a turnout prediction model using historical elections.
Outputs derived/models/turnout_model.pkl
"""
import pandas as pd
import numpy as np
import logging
import json
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "derived" / "archive"
MODELS_DIR = BASE_DIR / "derived" / "models"
LOG_DIR = BASE_DIR / "logs" / "archive"

MODELS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("train_turnout")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / "model_training.log")
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

def train_model():
    infile = ARCHIVE_DIR / "normalized_elections.csv"
    if not infile.exists():
        logger.error("No archive data found. Cannot train turnout model.")
        return

    df = pd.read_csv(infile)
    if len(df) < 50:
        logger.warning("Insufficient data to train robust model.")
        return

    # Basic feature engineering
    df["is_presidential"] = (df["contest_type"] == "presidential").astype(int)
    df["is_midterm"] = (df["contest_type"] == "midterm").astype(int)
    df["is_local"] = df["contest_type"].isin(["local_general", "local_special", "municipal"]).astype(int)
    df["is_measure"] = (df["contest_type"] == "ballot_measure").astype(int)
    df["registered_log"] = np.log1p(df["registered"])

    features = ["is_presidential", "is_midterm", "is_local", "is_measure", "registered_log"]
    target = "turnout_rate"

    X = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    logger.info(f"Turnout Model trained. MAE: {mae:.4f}, R2: {r2:.4f}")

    # Save model
    model_path = MODELS_DIR / "turnout_model.pkl"
    joblib.dump(model, model_path)
    
    # Save metadata
    meta = {
        "training_elections": int(df["contest"].nunique()),
        "training_precincts": int(df["precinct"].nunique()),
        "year_range": f"{df['year'].min()} - {df['year'].max()}",
        "features": features,
        "metrics": {"mae": round(mae, 4), "r2": round(r2, 4)}
    }
    with open(MODELS_DIR / "turnout_model_parameters.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"Saved turnout model to {model_path}")

if __name__ == "__main__":
    train_model()
    print("Turnout model training complete.")
