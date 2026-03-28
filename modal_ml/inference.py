"""
Modal inference endpoint (Modal 1.x API).
Loads the trained XGBoost model from the Modal volume and serves predictions.

Deploy:  modal deploy modal_ml/inference.py
Test:    curl -X POST https://<your-modal-url>/predict \
              -H "Content-Type: application/json" \
              -d '{"drivers": [{"driver_number": 1, "position": 1, ...}]}'
"""

import modal
from typing import Any

app = modal.App("successformula1-inference")

model_volume = modal.Volume.from_name("f1-model-vol", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "xgboost==2.1.1",
        "scikit-learn==1.5.2",
        "numpy==1.26.4",
        "joblib==1.4.2",
    )
)

MODEL_PATH = "/model/xgb_suzuka.pkl"
FEATURE_COLUMNS = [
    "position", "gap_to_leader", "tire_age", "tire_compound",
    "pit_stops", "laps_remaining", "safety_car", "vsc",
    "radio_sentiment", "radio_pit_keyword",
    "position_change_3lap", "gap_delta_3lap",
]


@app.cls(
    image=image,
    volumes={"/model": model_volume},
    keep_warm=1,  # prevent cold starts during the race
)
class PredictionService:

    @modal.enter()
    def load(self):
        import joblib
        self.model = joblib.load(MODEL_PATH)
        print("Model loaded.")

    @modal.web_endpoint(method="POST")
    def predict(self, payload: dict) -> dict:
        import numpy as np

        drivers: list[dict] = payload.get("drivers", [])
        if not drivers:
            return {"predictions": []}

        rows = []
        driver_numbers = []
        for d in drivers:
            row = [d.get(col, 0) for col in FEATURE_COLUMNS]
            rows.append(row)
            driver_numbers.append(d["driver_number"])

        X = np.array(rows, dtype=float)
        raw_probs = self.model.predict_proba(X)[:, 1]

        total = raw_probs.sum()
        normalised = (raw_probs / total).tolist() if total > 0 else [1.0 / len(drivers)] * len(drivers)

        return {
            "predictions": [
                {"driver_number": dn, "win_probability": round(p, 4)}
                for dn, p in zip(driver_numbers, normalised)
            ]
        }
