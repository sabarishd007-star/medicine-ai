"""Train the tabular heart-disease risk model from weights/heart.csv.

The upstream repository ships RandomForestClassifier.pkl built on scikit-learn
1.0.1. Its serialised tree node dtype is incompatible with modern scikit-learn
and cannot be unpickled, so rather than ship a broken or silently-wrong
artifact we retrain the same model type on the same public dataset and record
honest held-out metrics.

Note on the dataset: heart.csv (1025 rows) is the widely circulated expanded
version of the UCI Cleveland heart dataset. It contains duplicated rows from
oversampling the original 303 records. A naive random split therefore leaks
near-identical rows between train and test and reports implausibly high
accuracy. This script de-duplicates before splitting and reports both figures
so the inflation is visible rather than hidden.

Usage:
    python train_heart_model.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
CSV_PATH = os.path.join(WEIGHTS_DIR, "heart.csv")
MODEL_PATH = os.path.join(WEIGHTS_DIR, "heart_disease_model.joblib")
METRICS_PATH = os.path.join(WEIGHTS_DIR, "heart_disease.metrics.json")

FEATURES = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal",
]
TARGET = "target"
SEED = 42


def evaluate(model, X_test, y_test) -> dict:
    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]
    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "test_size": int(len(y_test)),
    }


def main() -> None:
    frame = pd.read_csv(CSV_PATH)
    raw_rows = len(frame)

    deduped = frame.drop_duplicates().reset_index(drop=True)
    duplicate_rows = raw_rows - len(deduped)

    X = deduped[FEATURES].to_numpy(dtype=np.float64)
    y = deduped[TARGET].to_numpy(dtype=np.int64)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_leaf=2,
        random_state=SEED,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    honest = evaluate(model, X_test, y_test)
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="roc_auc")

    # Deliberately reproduce the leaky setup so the inflation is documented.
    Xd = frame[FEATURES].to_numpy(dtype=np.float64)
    yd = frame[TARGET].to_numpy(dtype=np.int64)
    Xd_tr, Xd_te, yd_tr, yd_te = train_test_split(
        Xd, yd, test_size=0.2, random_state=SEED, stratify=yd
    )
    leaky_model = RandomForestClassifier(
        n_estimators=300, min_samples_leaf=2, random_state=SEED, n_jobs=-1
    ).fit(Xd_tr, yd_tr)
    leaky_accuracy = round(float(accuracy_score(yd_te, leaky_model.predict(Xd_te))), 4)

    joblib.dump({"model": model, "features": FEATURES}, MODEL_PATH)

    metrics = {
        "model_type": "RandomForestClassifier",
        "trained_on": "UCI Cleveland heart disease (expanded heart.csv), de-duplicated",
        "source_repo": "nilaymodak/HeartDiseasePrediction",
        "rows_raw": raw_rows,
        "duplicate_rows_removed": duplicate_rows,
        "rows_used": int(len(deduped)),
        "split": "stratified 80/20 on de-duplicated rows",
        "seed": SEED,
        "held_out": honest,
        "cross_val_roc_auc_mean": round(float(cv_scores.mean()), 4),
        "cross_val_roc_auc_std": round(float(cv_scores.std()), 4),
        "leaky_duplicate_split_accuracy": leaky_accuracy,
        "honesty_note": (
            "leaky_duplicate_split_accuracy is what you get by splitting the raw CSV "
            "with its duplicated rows; it is inflated by train/test leakage and must "
            "not be quoted. Use held_out metrics."
        ),
        "scope_note": (
            "Tabular clinical-variable risk estimate. Not part of the image screening "
            "pipeline and not a substitute for ECG, angiography or clinical assessment."
        ),
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"\nSaved model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
