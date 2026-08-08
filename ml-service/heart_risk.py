"""Tabular heart-disease risk estimation.

Explicitly separate from the image screening pipeline. The project report
excludes heart attack from CNN-based detection because it needs clinical
variables rather than a static image; this module supplies that tabular route
without pretending it belongs to the scan flow.
"""

import json
import os
import threading
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
MODEL_PATH = os.path.join(WEIGHTS_DIR, "heart_disease_model.joblib")
METRICS_PATH = os.path.join(WEIGHTS_DIR, "heart_disease.metrics.json")

CONFIDENCE_THRESHOLD = 0.75

FIELD_DOCS = {
    "age": "Age in years",
    "sex": "1 = male, 0 = female",
    "cp": "Chest pain type: 0 typical angina, 1 atypical, 2 non-anginal, 3 asymptomatic",
    "trestbps": "Resting blood pressure (mm Hg)",
    "chol": "Serum cholesterol (mg/dl)",
    "fbs": "Fasting blood sugar > 120 mg/dl (1 = true)",
    "restecg": "Resting ECG result: 0 normal, 1 ST-T abnormality, 2 LV hypertrophy",
    "thalach": "Maximum heart rate achieved",
    "exang": "Exercise-induced angina (1 = yes)",
    "oldpeak": "ST depression induced by exercise relative to rest",
    "slope": "Slope of peak exercise ST segment: 0 upsloping, 1 flat, 2 downsloping",
    "ca": "Number of major vessels (0-4) coloured by fluoroscopy",
    "thal": "Thalassemia: 0 normal, 1 fixed defect, 2 reversible defect, 3 unknown",
}

_model = None
_features = None
_lock = threading.Lock()


class HeartRiskRequest(BaseModel):
    age: float = Field(..., ge=1, le=129)
    sex: int = Field(..., ge=0, le=1)
    cp: int = Field(..., ge=0, le=3)
    trestbps: float = Field(..., ge=50, le=260)
    chol: float = Field(..., ge=50, le=700)
    fbs: int = Field(..., ge=0, le=1)
    restecg: int = Field(..., ge=0, le=2)
    thalach: float = Field(..., ge=40, le=250)
    exang: int = Field(..., ge=0, le=1)
    oldpeak: float = Field(..., ge=-3, le=10)
    slope: int = Field(..., ge=0, le=2)
    ca: int = Field(..., ge=0, le=4)
    thal: int = Field(..., ge=0, le=3)


def is_available() -> bool:
    return os.path.exists(MODEL_PATH)


def _metrics() -> Optional[dict]:
    if not os.path.exists(METRICS_PATH):
        return None
    try:
        with open(METRICS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _load():
    global _model, _features
    if _model is not None:
        return _model, _features
    with _lock:
        if _model is None:
            import joblib

            payload = joblib.load(MODEL_PATH)
            _model = payload["model"]
            _features = payload["features"]
    return _model, _features


def schema() -> dict:
    return {
        "available": is_available(),
        "fields": FIELD_DOCS,
        "confidence_threshold": CONFIDENCE_THRESHOLD * 100,
        "metrics": _metrics(),
        "scope_note": (
            "Tabular risk estimate from routine clinical variables. This is NOT "
            "image-based screening and NOT an ECG interpretation."
        ),
    }


def predict(payload: HeartRiskRequest) -> dict:
    model, features = _load()
    row = np.array([[getattr(payload, name) for name in features]], dtype=np.float64)

    probabilities = model.predict_proba(row)[0]
    positive = float(probabilities[1])
    predicted_index = int(np.argmax(probabilities))
    confidence = float(probabilities[predicted_index])
    is_conclusive = confidence >= CONFIDENCE_THRESHOLD

    if is_conclusive:
        label = "Heart Disease Indicated" if predicted_index == 1 else "No Heart Disease Indicated"
    else:
        label = "Inconclusive - Consult Specialist"

    contributions = None
    importances = getattr(model, "feature_importances_", None)
    if importances is not None:
        ranked = sorted(zip(features, importances), key=lambda kv: kv[1], reverse=True)
        contributions = [
            {"feature": name, "importance": round(float(weight), 4)} for name, weight in ranked[:5]
        ]

    return {
        "prediction": label,
        "risk_probability": round(positive * 100, 2),
        "confidence": round(confidence * 100, 2),
        "confidence_threshold": CONFIDENCE_THRESHOLD * 100,
        "is_conclusive": is_conclusive,
        "model_type": "RandomForestClassifier",
        "input_type": "tabular_clinical_variables",
        "top_feature_importances": contributions,
        "metrics": _metrics(),
        "disclaimer": (
            "AI-assisted risk estimate from tabular clinical variables. Not a "
            "diagnosis, not an ECG interpretation, and no substitute for evaluation "
            "by a licensed clinician."
        ),
    }
