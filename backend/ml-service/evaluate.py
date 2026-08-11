"""Measure real accuracy for MediScan AI image modules.

Runs a module's full production inference path over a labelled test set and
writes weights/<key>.metrics.json, which the API and PDF then surface. Nothing
else in the system is allowed to claim accuracy; if this file has not been run
for a module, that module reports no metrics.

Reported figures are deliberately conservative:
  * accuracy, macro/weighted precision, recall, F1, per-class breakdown
  * confusion matrix over the registry's own class list
  * gated accuracy - accuracy counting only predictions that clear the
    confidence threshold, alongside the coverage that gate achieves
  * label_mapping_exact - false when the dataset taxonomy had to be collapsed

Usage:
    python evaluate.py --disease diabetic_retinopathy --limit 200
    python evaluate.py --all --limit 200
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import datasets as ds  # noqa: E402
import model_registry  # noqa: E402
from backends import decode_ordinal  # noqa: E402

WEIGHTS_DIR = model_registry.WEIGHTS_DIR


def predict_index(bundle, image) -> tuple:
    """Return (predicted_index, confidence) using the production inference path."""
    output = bundle.backend.infer(image)
    scores = np.asarray(output.probabilities, dtype=np.float64)
    if output.probabilities_are_ordinal:
        index = decode_ordinal(scores, bundle.spec.ordinal_threshold)
    else:
        index = int(np.argmax(scores))
    return index, float(scores[index])


def confusion(y_true, y_pred, n_classes):
    matrix = np.zeros((n_classes, n_classes), dtype=int)
    for true, pred in zip(y_true, y_pred):
        matrix[true][pred] += 1
    return matrix


def per_class_metrics(matrix, classes):
    out = {}
    for i, name in enumerate(classes):
        tp = int(matrix[i][i])
        fp = int(matrix[:, i].sum() - tp)
        fn = int(matrix[i, :].sum() - tp)
        support = int(matrix[i, :].sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        out[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }
    return out


def evaluate(disease: str, limit: int, stride: int, seed: int = 42, data_dir: str = "", verbose: bool = True) -> dict:
    if disease not in ds.DATASETS:
        raise SystemExit(
            f"No evaluation dataset configured for '{disease}'. "
            f"Available: {sorted(ds.DATASETS)}"
        )

    spec = ds.DATASETS[disease]
    bundle = model_registry.get_bundle(disease)

    if not bundle.is_trained:
        raise SystemExit(
            f"'{disease}' has no trained checkpoint (status={bundle.status}). "
            "Refusing to produce metrics for an untrained model."
        )

    classes = bundle.spec.classes
    threshold = bundle.spec.confidence_threshold

    y_true, y_pred, confidences = [], [], []
    started = time.time()

    if disease == "skin_cancer":
        sample_iter = ds.iter_skin_samples(limit=limit, stride=stride, seed=seed)
    elif disease == "brain_tumor":
        if not data_dir:
            raise SystemExit(
                "brain_tumor evaluation needs the Kaggle download path. "
                "Pass --data-dir <extracted-folder>.")
        sample_iter = ds.iter_brain_samples(data_dir, limit=limit)
    else:
        sample_iter = ds.iter_samples(spec, limit=limit, stride=stride, seed=seed)

    for image, label in sample_iter:
        index, confidence = predict_index(bundle, image)
        y_true.append(label)
        y_pred.append(index)
        confidences.append(confidence)
        if verbose and len(y_true) % 25 == 0:
            running = float(np.mean(np.array(y_true) == np.array(y_pred)))
            print(f"    {len(y_true):4d} samples  running acc={running:.3f}", flush=True)

    if not y_true:
        raise SystemExit(f"No samples were retrieved for '{disease}'.")

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    conf_arr = np.array(confidences)

    matrix = confusion(y_true, y_pred, len(classes))
    accuracy = float((y_true_arr == y_pred_arr).mean())
    per_class = per_class_metrics(matrix, classes)

    supports = np.array([per_class[c]["support"] for c in classes], dtype=float)
    f1s = np.array([per_class[c]["f1"] for c in classes], dtype=float)
    precisions = np.array([per_class[c]["precision"] for c in classes], dtype=float)
    recalls = np.array([per_class[c]["recall"] for c in classes], dtype=float)
    present = supports > 0
    weight = supports / supports.sum() if supports.sum() else supports

    gate = conf_arr >= threshold
    gated_accuracy = (
        float((y_true_arr[gate] == y_pred_arr[gate]).mean()) if gate.any() else None
    )

    # A model that always predicts the most common class would score this.
    counts = np.bincount(y_true_arr, minlength=len(classes))
    majority_baseline = float(counts.max() / counts.sum())

    classes_present = int((counts > 0).sum())
    if classes_present < 2:
        raise SystemExit(
            f"Evaluation sample contains only {classes_present} class(es) "
            f"({dict(zip(classes, counts.tolist()))}). Accuracy would be meaningless. "
            "Increase --limit or change --seed."
        )

    metrics = {
        "disease": disease,
        "model_status": bundle.status,
        "model_sha256": bundle.weights_sha256,
        "framework": bundle.spec.framework,
        "architecture": bundle.spec.architecture,
        "classes": list(classes),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "eval_seconds": round(time.time() - started, 1),
        "dataset": {
            "name": ("Kaggle download (local)" if not spec.hf_dataset else spec.hf_dataset),
            "split": spec.split,
            "url": spec.source_url,
            "data_dir": data_dir,
            "license_note": spec.license_note,
            "samples_evaluated": int(len(y_true)),
            "sampling": f"uniform random rows, seed={seed}",
            "class_support": dict(zip(classes, counts.tolist())),
            "native_labels": spec.native_labels,
            "label_mapping_exact": spec.exact_taxonomy,
            "mapping_note": spec.mapping_note,
        },
        "accuracy": round(accuracy, 4),
        "macro_precision": round(float(precisions[present].mean()) if present.any() else 0.0, 4),
        "macro_recall": round(float(recalls[present].mean()) if present.any() else 0.0, 4),
        "macro_f1": round(float(f1s[present].mean()) if present.any() else 0.0, 4),
        "weighted_f1": round(float((f1s * weight).sum()), 4),
        "majority_class_baseline": round(majority_baseline, 4),
        "beats_majority_baseline": bool(accuracy > majority_baseline),
        "confidence_gate": {
            "threshold": threshold,
            "coverage": round(float(gate.mean()), 4),
            "accuracy_on_gated": None if gated_accuracy is None else round(gated_accuracy, 4),
            "mean_confidence": round(float(conf_arr.mean()), 4),
        },
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_rows": "true label",
        "confusion_matrix_cols": "predicted label",
    }

    caveats = [
        "Measured on a public mirror of the test data, not a private hold-out set. "
        "Some overlap with the checkpoint's original training data cannot be excluded, "
        "so this figure may be optimistic.",
    ]
    if not spec.exact_taxonomy:
        caveats.append(
            "Dataset labels were collapsed to fit the model's coarser class list; "
            "part of the error is mapping loss, not model error."
        )
    if len(y_true) < 200:
        caveats.append(
            f"Only {len(y_true)} samples evaluated - the confidence interval on this "
            "estimate is wide. Increase --limit for a firmer number."
        )
    metrics["caveats"] = caveats

    safety = _safety_summary(disease, matrix, classes)
    if safety:
        metrics["safety"] = safety
        metrics["caveats"].append(safety["warning"])

    return metrics


# Classes that represent disease requiring escalation. Calling one of these
# "normal" is a false negative: the failure mode that actually harms a patient,
# and one that overall accuracy hides when the benign class dominates.
POSITIVE_CLASSES = {
    "skin_cancer": ["Basal Cell Carcinoma (Cancer)", "Melanoma (Cancer)"],
    "diabetic_retinopathy": [
        "Mild Non-Proliferative DR",
        "Moderate Non-Proliferative DR",
        "Severe Non-Proliferative DR",
        "Proliferative DR",
    ],
    "knee_osteoarthritis": ["Non Severe OA", "Severe OA"],
    "brain_tumor": ["Glioma", "Meningioma", "Pituitary"],
}


def _safety_summary(disease: str, matrix, classes) -> dict:
    positives = POSITIVE_CLASSES.get(disease)
    if not positives:
        return {}

    positive_idx = [i for i, name in enumerate(classes) if name in positives]
    negative_idx = [i for i in range(len(classes)) if i not in positive_idx]
    if not positive_idx or not negative_idx:
        return {}

    diseased_total = int(sum(matrix[i, :].sum() for i in positive_idx))
    missed = int(sum(matrix[i, j] for i in positive_idx for j in negative_idx))
    healthy_total = int(sum(matrix[i, :].sum() for i in negative_idx))
    false_alarms = int(sum(matrix[i, j] for i in negative_idx for j in positive_idx))

    miss_rate = missed / diseased_total if diseased_total else 0.0
    sensitivity = 1.0 - miss_rate
    specificity = (
        (healthy_total - false_alarms) / healthy_total if healthy_total else 0.0
    )

    return {
        "definition": (
            f"Positive = {positives}. A false negative is a diseased case predicted "
            "as non-diseased."
        ),
        "diseased_samples": diseased_total,
        "missed_diseased_cases": missed,
        "false_negative_rate": round(miss_rate, 4),
        "sensitivity_recall": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "false_alarms": false_alarms,
        "warning": (
            f"SAFETY: this module missed {missed} of {diseased_total} diseased cases "
            f"({miss_rate:.1%} false-negative rate) on the evaluated sample. Overall "
            "accuracy hides this because the non-diseased class dominates. Treat a "
            "negative result as non-informative, never as reassurance."
        ),
    }


def write_metrics(disease: str, metrics: dict) -> str:
    path = os.path.join(WEIGHTS_DIR, f"{disease}.metrics.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    return path


def summarise(metrics: dict) -> None:
    print(f"\n  accuracy        : {metrics['accuracy']:.4f}")
    print(f"  macro F1        : {metrics['macro_f1']:.4f}")
    print(f"  baseline (major): {metrics['majority_class_baseline']:.4f}")
    gate = metrics["confidence_gate"]
    print(
        f"  gated accuracy  : {gate['accuracy_on_gated']} "
        f"(coverage {gate['coverage']:.2f} at threshold {gate['threshold']})"
    )
    print(f"  samples         : {metrics['dataset']['samples_evaluated']}")
    if not metrics["dataset"]["label_mapping_exact"]:
        print("  NOTE: label taxonomy was collapsed to fit this model.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disease", help="registry key to evaluate")
    parser.add_argument("--all", action="store_true", help="evaluate every configured dataset")
    parser.add_argument("--limit", type=int, default=200, help="samples to evaluate")
    parser.add_argument("--stride", type=int, default=1, help="deprecated, ignored")
    parser.add_argument(
        "--data-dir",
        help="Path to extracted dataset folder, required for brain_tumor (Kaggle download).",
    )
    parser.add_argument("--seed", type=int, default=42, help="sampling seed")
    args = parser.parse_args()

    if args.all:
        targets = list(ds.DATASETS)
    elif args.disease:
        targets = [args.disease]
    else:
        parser.error("pass --disease <key> or --all")

    for disease in targets:
        print(f"\n=== Evaluating {disease} ===")
        try:
            metrics = evaluate(disease, args.limit, args.stride, seed=args.seed, data_dir=args.data_dir or "")
        except SystemExit as exc:
            print(f"  SKIPPED: {exc}")
            continue
        path = write_metrics(disease, metrics)
        summarise(metrics)
        print(f"  written -> {path}")

    print("\nModules without a configured dataset report no metrics, by design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
