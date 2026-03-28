"""
Training script: fetch historical Suzuka races via FastF1, engineer features,
train XGBoost classifier, save artifact to Modal volume.

Run on Modal:  modal run modal_ml/train.py
Run locally:   python modal_ml/train.py --local
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import modal
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

from modal_ml.features import FEATURE_COLUMNS, COMPOUND_MAP

# ---------------------------------------------------------------------------
# Modal setup (1.x API)
# ---------------------------------------------------------------------------

app = modal.App("successformula1-training")

model_volume = modal.Volume.from_name("f1-model-vol", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastf1==3.4.0",
        "xgboost==2.1.1",
        "scikit-learn==1.5.2",
        "pandas==2.2.3",
        "numpy==1.26.4",
        "joblib==1.4.2",
    )
)

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

SUZUKA_LAPS = 53
TRAINING_SESSIONS = [
    (2019, "Japan", "R"),
    (2022, "Japan", "R"),
    (2023, "Japan", "R"),
    (2024, "Japan", "R"),
]


def engineer_features(session) -> pd.DataFrame:
    import fastf1

    laps = session.laps.copy()
    if laps.empty:
        return pd.DataFrame()

    laps = laps[laps["LapNumber"] > 1].copy()

    laps["tire_compound"] = (
        laps["Compound"].fillna("MEDIUM").str.upper().map(COMPOUND_MAP).fillna(1).astype(int)
    )
    laps["tire_age"] = laps["TyreLife"].fillna(1).astype(int)
    laps["pit_stops"] = laps.groupby("DriverNumber")["PitOutTime"].transform(
        lambda x: x.notna().cumsum()
    )
    total_laps = laps["LapNumber"].max()
    laps["laps_remaining"] = total_laps - laps["LapNumber"]
    laps["position"] = laps["Position"].ffill().fillna(20).astype(int)
    laps["gap_to_leader"] = (
        laps["GapToLeader"]
        .apply(lambda x: x.total_seconds() if pd.notna(x) and hasattr(x, "total_seconds") else 0.0)
        .fillna(0.0)
    )
    laps["safety_car"] = 0
    laps["vsc"] = 0
    laps["radio_sentiment"] = 0.0
    laps["radio_pit_keyword"] = 0

    laps = laps.sort_values(["DriverNumber", "LapNumber"])
    laps["position_change_3lap"] = laps.groupby("DriverNumber")["position"].transform(
        lambda x: x.shift(3) - x
    ).fillna(0).astype(int)
    laps["gap_delta_3lap"] = laps.groupby("DriverNumber")["gap_to_leader"].transform(
        lambda x: x - x.shift(3)
    ).fillna(0.0)

    final_positions = laps.groupby("DriverNumber")["position"].last()
    laps["won"] = laps["DriverNumber"].map(lambda d: int(final_positions.get(d, 20) == 1))

    return laps[FEATURE_COLUMNS + ["won", "DriverNumber", "LapNumber"]].dropna()


def load_all_sessions() -> pd.DataFrame:
    import fastf1

    cache_dir = Path("/tmp/fastf1_cache")
    cache_dir.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))

    frames = []
    for year, gp, session_type in TRAINING_SESSIONS:
        try:
            print(f"Loading {year} {gp} {session_type}...")
            session = fastf1.get_session(year, gp, session_type)
            session.load(telemetry=False, weather=False, messages=False)
            df = engineer_features(session)
            if not df.empty:
                df["year"] = year
                frames.append(df)
                print(f"  → {len(df)} lap rows")
        except Exception as e:
            print(f"  ✗ Failed {year} {gp}: {e}")

    if not frames:
        raise RuntimeError("No training data loaded — check FastF1 connectivity")
    return pd.concat(frames, ignore_index=True)


def _run_training(output_path: str):
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score

    print("Loading sessions...")
    df = load_all_sessions()
    X = df[FEATURE_COLUMNS].values
    y = df["won"].values

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)

    auc = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
    print(f"\nValidation AUC: {auc:.4f}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    print(f"Model saved → {output_path}")


# ---------------------------------------------------------------------------
# Modal function + local entrypoint (Modal 1.x style)
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    volumes={"/model": model_volume},
    timeout=1800,
)
def train_on_modal():
    _run_training("/model/xgb_suzuka.pkl")
    model_volume.commit()
    print("Committed model to volume.")


@app.local_entrypoint()
def main():
    """Entry point when running `modal run modal_ml/train.py`"""
    train_on_modal.remote()


# ---------------------------------------------------------------------------
# Local fallback: python modal_ml/train.py --local
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    if args.local:
        _run_training("data/xgb_suzuka.pkl")
