"""
engine/archive/train_support_model.py

Trains a support/persuasion prediction model using historical elections.
Outputs derived/models/support_model.pkl
"""
import pandas as pd
import numpy as np
import logging
import json
import joblib
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = BASE_DIR / "derived" / "archive"
MODELS_DIR = BASE_DIR / "derived" / "models"
LOG_DIR = BASE_DIR / "logs" / "archive"

logger = logging.getLogger("train_support")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / "model_training.log")
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

def train_model():
    infile = ARCHIVE_DIR / "normalized_elections.csv"
    if not infile.exists():
        logger.error("No archive data found. Cannot train support model.")
        return

    df = pd.read_csv(infile)
    if len(df) < 50:
        return

    # Basic feature engineering
    df["is_presidential"] = (df["contest_type"] == "presidential").astype(int)
    df["is_midterm"] = (df["contest_type"] == "midterm").astype(int)
    df["is_local"] = df["contest_type"].isin(["local_general", "local_special", "municipal"]).astype(int)
    df["is_measure"] = (df["contest_type"] == "ballot_measure").astype(int)
    
    # proxy for historical leaning
    profile_file = ARCHIVE_DIR / "precinct_profiles.csv"
    if profile_file.exists():
        prof = pd.read_csv(profile_file)
        df = df.merge(prof[["precinct", "partisan_tilt"]], on="precinct", how="left")
    else:
        df["partisan_tilt"] = 0.0

    features = ["is_presidential", "is_midterm", "is_local", "is_measure", "turnout_rate", "partisan_tilt"]
    target = "support_rate"

    X = df[features].fillna(0)
    y = df[target].fillna(0.5)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    logger.info(f"Support Model trained. MAE: {mae:.4f}, R2: {r2:.4f}")

    model_path = MODELS_DIR / "support_model.pkl"
    joblib.dump(model, model_path)
    
    # Feature importance
    fi = pd.DataFrame({"feature": features, "importance": model.feature_importances_})
    fi = fi.sort_values("importance", ascending=False)
    fi_path = MODELS_DIR / "support_feature_importance.csv"
    fi.to_csv(fi_path, index=False)
    
    # Save metadata
    meta = {
        "training_elections": int(df["contest"].nunique()),
        "features": features,
        "metrics": {"mae": round(mae, 4), "r2": round(r2, 4)}
    }
    with open(MODELS_DIR / "support_model_parameters.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"Saved support model to {model_path}")

if __name__ == "__main__":
    train_model()
    print("Support model training complete.")
