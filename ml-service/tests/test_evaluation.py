import json
import os
import sys

import numpy as np
import pytest

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datasets as ds  # noqa: E402
import evaluate as ev  # noqa: E402
import model_registry  # noqa: E402

WEIGHTS_DIR = model_registry.WEIGHTS_DIR


def load_metrics(key):
    path = os.path.join(WEIGHTS_DIR, f"{key}.metrics.json")
    if not os.path.exists(path):
        pytest.skip(f"{key} not evaluated yet")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


EVALUATED = [
    key
    for key in ds.DATASETS
    if os.path.exists(os.path.join(WEIGHTS_DIR, f"{key}.metrics.json"))
]


# --- metric maths ---------------------------------------------------------


def test_confusion_matrix_counts():
    matrix = ev.confusion([0, 0, 1, 1], [0, 1, 1, 1], 2)
    assert matrix.tolist() == [[1, 1], [0, 2]]


def test_per_class_metrics_on_known_matrix():
    matrix = np.array([[2, 1], [0, 3]])
    out = ev.per_class_metrics(matrix, ["a", "b"])
    assert out["a"]["precision"] == 1.0
    assert out["a"]["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert out["b"]["support"] == 3


def test_per_class_metrics_handles_absent_class():
    matrix = np.array([[3, 0], [0, 0]])
    out = ev.per_class_metrics(matrix, ["a", "b"])
    assert out["b"]["support"] == 0
    assert out["b"]["f1"] == 0.0


def test_safety_summary_counts_false_negatives():
    classes = [
        "Basal Cell Carcinoma (Cancer)",
        "Melanoma (Cancer)",
        "Nevus (Non-Cancerous)",
    ]
    # 10 BCC and 10 melanoma, half of each predicted as the benign class.
    matrix = np.array([[5, 0, 5], [0, 5, 5], [0, 0, 20]])
    safety = ev._safety_summary("skin_cancer", matrix, classes)
    assert safety["diseased_samples"] == 20
    assert safety["missed_diseased_cases"] == 10
    assert safety["false_negative_rate"] == 0.5
    assert safety["sensitivity_recall"] == 0.5
    assert "SAFETY" in safety["warning"]


def test_safety_summary_absent_for_unmapped_disease():
    assert ev._safety_summary("brain_tumor", np.eye(4, dtype=int), ["a", "b", "c", "d"]) == {}


# --- dataset adapters -----------------------------------------------------


def test_every_dataset_targets_a_registered_disease():
    for key, spec in ds.DATASETS.items():
        assert spec.disease in model_registry.REGISTRY


def test_label_map_targets_valid_class_indices():
    for key, spec in ds.DATASETS.items():
        n_classes = len(model_registry.REGISTRY[spec.disease].classes)
        for mapped in spec.label_map.values():
            if mapped is not None:
                assert 0 <= mapped < n_classes, f"{key} maps outside its class list"


def test_lossy_mappings_are_declared():
    """Collapsed taxonomies must be flagged so metrics cannot be over-read."""
    assert ds.DATASETS["knee_osteoarthritis"].exact_taxonomy is False
    assert ds.DATASETS["skin_cancer"].exact_taxonomy is False
    assert ds.DATASETS["diabetic_retinopathy"].exact_taxonomy is True
    for spec in ds.DATASETS.values():
        if not spec.exact_taxonomy:
            assert spec.mapping_note


def test_ham_map_drops_classes_the_model_lacks():
    """Unsupported lesion types must be excluded, never forced into a wrong class."""
    for code in ("bkl", "df", "akiec", "vasc"):
        assert ds.HAM_LABEL_MAP[code] is None
    assert set(v for v in ds.HAM_LABEL_MAP.values() if v is not None) == {0, 1, 2}


# --- recorded metrics -----------------------------------------------------


@pytest.mark.parametrize("key", EVALUATED)
def test_metrics_file_is_self_describing(key):
    metrics = load_metrics(key)
    for field in ("accuracy", "macro_f1", "confusion_matrix", "dataset", "caveats"):
        assert field in metrics
    assert metrics["dataset"]["samples_evaluated"] > 0
    assert metrics["caveats"], "every metrics file must state its limitations"


@pytest.mark.parametrize("key", EVALUATED)
def test_confusion_matrix_agrees_with_accuracy(key):
    metrics = load_metrics(key)
    matrix = np.array(metrics["confusion_matrix"])
    recomputed = np.trace(matrix) / matrix.sum()
    assert recomputed == pytest.approx(metrics["accuracy"], abs=1e-3)


@pytest.mark.parametrize("key", EVALUATED)
def test_evaluation_sample_covers_multiple_classes(key):
    """A single-class sample makes accuracy meaningless; guard against it."""
    metrics = load_metrics(key)
    matrix = np.array(metrics["confusion_matrix"])
    assert (matrix.sum(axis=1) > 0).sum() >= 2


@pytest.mark.parametrize("key", EVALUATED)
def test_metrics_declare_class_support(key):
    metrics = load_metrics(key)
    support = metrics["dataset"]["class_support"]
    assert sum(support.values()) == metrics["dataset"]["samples_evaluated"]


@pytest.mark.parametrize("key", EVALUATED)
def test_confusion_matrix_matches_registry_classes(key):
    metrics = load_metrics(key)
    expected = len(model_registry.REGISTRY[key].classes)
    assert np.array(metrics["confusion_matrix"]).shape == (expected, expected)


@pytest.mark.parametrize("key", EVALUATED)
def test_safety_block_present_for_screening_modules(key):
    metrics = load_metrics(key)
    assert "safety" in metrics, f"{key} must report a false-negative rate"
    safety = metrics["safety"]
    assert safety["diseased_samples"] > 0
    assert 0.0 <= safety["false_negative_rate"] <= 1.0
    assert safety["sensitivity_recall"] == pytest.approx(
        1 - safety["false_negative_rate"], abs=1e-4
    )


def test_untrained_module_cannot_be_evaluated():
    with pytest.raises(SystemExit):
        ev.evaluate("brain_tumor", limit=1, stride=1)


def test_unknown_disease_rejected():
    with pytest.raises(SystemExit):
        ev.evaluate("not_a_disease", limit=1, stride=1)


# --- api/report surfacing -------------------------------------------------


def test_api_exposes_measured_metrics():
    from fastapi.testclient import TestClient

    from app import app

    entries = {d["key"]: d for d in TestClient(app).get("/diseases").json()["diseases"]}
    for key in EVALUATED:
        assert entries[key]["metrics"] is not None
        assert entries[key]["metrics"]["accuracy"] > 0


def test_untrained_module_reports_no_metrics():
    from fastapi.testclient import TestClient

    from app import app

    entries = {d["key"]: d for d in TestClient(app).get("/diseases").json()["diseases"]}
    assert entries["brain_tumor"]["metrics"] is None
