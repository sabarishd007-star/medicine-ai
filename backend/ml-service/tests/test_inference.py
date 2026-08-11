import io
import os
import sys

import numpy as np
import pytest
import torch
from PIL import Image

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import backends  # noqa: E402
import model_registry  # noqa: E402
from app import analyze_image, app  # noqa: E402
from architectures import KneeResNet  # noqa: E402
from gradcam import GradCAM, cam_coverage, overlay_cam  # noqa: E402

client = TestClient(app)

TRAINED = [
    key
    for key, spec in model_registry.REGISTRY.items()
    if os.path.exists(model_registry.weights_path(spec))
]


def make_image(size=(256, 256), seed=0):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (*size, 3), dtype=np.uint8))


def image_bytes(size=(256, 256), fmt="PNG"):
    buf = io.BytesIO()
    make_image(size).save(buf, format=fmt)
    return buf.getvalue()


# --- registry -------------------------------------------------------------


def test_health_reports_module_counts():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["modules_registered"] == len(model_registry.REGISTRY)
    assert body["modules_trained"] == len(TRAINED)


def test_diseases_endpoint_exposes_provenance():
    entries = client.get("/diseases").json()["diseases"]
    assert {e["key"] for e in entries} == set(model_registry.REGISTRY)
    for entry in entries:
        assert entry["model_status"] in (
            model_registry.STATUS_TRAINED,
            model_registry.STATUS_UNTRAINED,
        )
        assert entry["provenance"], f"{entry['key']} must declare provenance"
        assert len(entry["classes"]) >= 2


def test_class_lists_match_checkpoint_output_width():
    assert len(model_registry.REGISTRY["knee_osteoarthritis"].classes) == 3
    assert len(model_registry.REGISTRY["skin_cancer"].classes) == 3
    assert len(model_registry.REGISTRY["diabetic_retinopathy"].classes) == 5
    assert len(model_registry.REGISTRY["brain_tumor"].classes) == 4


def test_every_class_has_knowledge_base_entry():
    import json

    with open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "disease_info.json"),
        encoding="utf-8",
    ) as fh:
        kb = json.load(fh)
    for key, spec in model_registry.REGISTRY.items():
        assert key in kb, f"missing KB section for {key}"
        for label in spec.classes:
            assert label in kb[key], f"missing KB entry {key}/{label}"


# --- architecture ---------------------------------------------------------


def test_knee_architecture_matches_checkpoint():
    spec = model_registry.REGISTRY["knee_osteoarthritis"]
    path = model_registry.weights_path(spec)
    if not os.path.exists(path):
        pytest.skip("knee checkpoint not installed")
    state = torch.load(path, map_location="cpu")
    model = KneeResNet(num_classes=3)
    model.load_state_dict(state)  # raises if names/shapes drift
    assert state["conv1.0.weight"].shape[1] == 1
    assert state["fc.weight"].shape[0] == 3


def test_knee_preprocess_is_single_channel_299():
    tensor = backends.knee_preprocess(make_image())
    assert tensor.shape == (1, 1, 299, 299)


def test_knee_preprocess_is_deterministic():
    """Upstream left random flip/rotate in the inference transform; we removed them."""
    img = make_image(seed=21)
    assert torch.allclose(backends.knee_preprocess(img), backends.knee_preprocess(img))


def test_skin_preprocess_scales_to_unit_range():
    arr = backends.skin_preprocess(make_image())
    assert arr.shape == (1, 224, 224, 3)
    assert 0.0 <= arr.min() and arr.max() <= 1.0


def test_dr_preprocess_keeps_raw_scale():
    arr = backends.dr_preprocess(make_image())
    assert arr.shape == (1, 224, 224, 3)
    assert arr.max() > 1.0


def test_ordinal_decoding():
    threshold = 0.3776
    assert backends.decode_ordinal(np.array([0.9, 0.1, 0.1, 0.1, 0.1]), threshold) == 0
    assert backends.decode_ordinal(np.array([0.9, 0.9, 0.9, 0.1, 0.1]), threshold) == 2
    assert backends.decode_ordinal(np.array([0.9] * 5), threshold) == 4
    assert backends.decode_ordinal(np.zeros(5), threshold) == 0


# --- grad-cam -------------------------------------------------------------


def test_gradcam_is_real_and_shaped_to_the_layer():
    bundle = model_registry.get_bundle("brain_tumor")
    tensor = bundle.backend.preprocess(make_image())
    with GradCAM(bundle.backend.model, bundle.backend.target_layer) as engine:
        cam, logits = engine.run(tensor)
    assert cam.shape == (7, 7)
    assert cam.min() >= 0.0 and cam.max() <= 1.0 + 1e-6
    assert logits.shape == (1, 4)


def test_gradcam_differs_between_target_classes():
    bundle = model_registry.get_bundle("brain_tumor")
    tensor = bundle.backend.preprocess(make_image(seed=3))
    with GradCAM(bundle.backend.model, bundle.backend.target_layer) as engine:
        cam_a, _ = engine.run(tensor, class_index=0)
    with GradCAM(bundle.backend.model, bundle.backend.target_layer) as engine:
        cam_b, _ = engine.run(tensor, class_index=1)
    assert not np.allclose(cam_a, cam_b)


def test_overlay_matches_source_resolution():
    img = np.zeros((120, 90, 3), dtype=np.uint8)
    cam = np.linspace(0, 1, 49).reshape(7, 7).astype(np.float32)
    assert overlay_cam(img, cam).shape == img.shape


def test_cam_coverage_bounds():
    assert cam_coverage(np.ones((4, 4), dtype=np.float32)) == 1.0
    assert cam_coverage(np.zeros((4, 4), dtype=np.float32)) == 0.0


@pytest.mark.parametrize("disease", TRAINED)
def test_trained_modules_produce_non_degenerate_gradcam(disease):
    """A CAM of all zeros means the gradient died through a saturated head."""
    result = analyze_image(disease, make_image(seed=13))
    assert result["gradcam_available"], f"{disease} produced no Grad-CAM"
    assert result["gradcam_coverage"] > 0.0, f"{disease} produced an all-zero Grad-CAM"


SAMPLE_IMAGE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample.jpg"
)


@pytest.mark.parametrize("disease", TRAINED)
def test_gradcam_localises_on_a_real_image(disease):
    """On real input the map should be localised, not saturated across the frame."""
    if not os.path.exists(SAMPLE_IMAGE):
        pytest.skip("sample.jpg not present")
    result = analyze_image(disease, Image.open(SAMPLE_IMAGE).convert("RGB"))
    assert 0.0 < result["gradcam_coverage"] < 1.0


# --- inference ------------------------------------------------------------


@pytest.mark.parametrize("disease", sorted(model_registry.REGISTRY))
def test_analyze_is_deterministic(disease):
    img = make_image(seed=11)
    first = analyze_image(disease, img)
    second = analyze_image(disease, img)
    assert first["confidence"] == second["confidence"]
    assert first["top_class"] == second["top_class"]


@pytest.mark.parametrize("disease", sorted(model_registry.REGISTRY))
def test_probability_count_matches_class_count(disease):
    result = analyze_image(disease, make_image(seed=5))
    spec = model_registry.REGISTRY[disease]
    assert set(result["class_probabilities"]) == set(spec.classes)


def test_softmax_modules_sum_to_one_hundred():
    result = analyze_image("knee_osteoarthritis", make_image(seed=5))
    assert result["score_semantics"] == "softmax"
    assert sum(result["class_probabilities"].values()) == pytest.approx(100.0, abs=0.1)


def test_ordinal_module_is_labelled_as_such():
    result = analyze_image("diabetic_retinopathy", make_image(seed=5))
    assert result["score_semantics"] == "ordinal_sigmoid"


def test_untrained_module_is_never_conclusive():
    result = analyze_image("brain_tumor", make_image(seed=7))
    assert result["model_status"] == model_registry.STATUS_UNTRAINED
    assert result["is_conclusive"] is False
    assert result["prediction"] == "Not Clinically Valid - Untrained Model"
    assert result["stage"] is None


class NearUniformNet(torch.nn.Module):
    """Two-class net whose logits stay close together, so softmax never clears 75%."""

    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv2d(3, 4, kernel_size=3, padding=1)
        self.head = torch.nn.Linear(4, 2)
        with torch.no_grad():
            self.head.weight.mul_(0.001)
            self.head.bias.copy_(torch.tensor([0.0, 0.1]))

    def forward(self, x):
        feats = torch.relu(self.conv(x))
        pooled = torch.nn.functional.adaptive_avg_pool2d(feats, 1).flatten(1)
        return self.head(pooled)


def _patch_bundle(monkeypatch, disease, model, classes):
    import app as app_module

    spec = model_registry.REGISTRY[disease]
    object.__setattr__(spec, "classes", classes) if False else None
    bundle = model_registry.ModelBundle(
        spec=spec,
        backend=backends.TorchBackend(
            model, model.conv, backends.make_resnet_preprocess(spec.input_size)
        ),
        status=model_registry.STATUS_TRAINED,
    )
    monkeypatch.setattr(app_module, "get_bundle", lambda _d: bundle)
    return bundle


def test_confidence_gate_blocks_low_confidence(monkeypatch):
    import app as app_module

    spec = model_registry.REGISTRY["skin_cancer"]
    model = torch.nn.Module()
    net = NearUniformNet()
    net.head = torch.nn.Linear(4, len(spec.classes))
    with torch.no_grad():
        net.head.weight.mul_(0.001)
        net.head.bias.copy_(torch.zeros(len(spec.classes)))
    del model
    _patch_bundle(monkeypatch, "skin_cancer", net, spec.classes)

    result = app_module.analyze_image("skin_cancer", make_image())
    assert result["confidence"] < spec.confidence_threshold * 100
    assert result["is_conclusive"] is False
    assert result["prediction"] == "Inconclusive - Consult Specialist"


def test_confident_trained_model_returns_class_label(monkeypatch):
    import app as app_module

    spec = model_registry.REGISTRY["skin_cancer"]
    net = NearUniformNet()
    net.head = torch.nn.Linear(4, len(spec.classes))
    with torch.no_grad():
        net.head.weight.mul_(0.001)
        bias = torch.zeros(len(spec.classes))
        bias[1] = 12.0
        net.head.bias.copy_(bias)
    _patch_bundle(monkeypatch, "skin_cancer", net, spec.classes)

    result = app_module.analyze_image("skin_cancer", make_image())
    assert result["confidence"] > 75.0
    assert result["is_conclusive"] is True
    assert result["prediction"] == spec.classes[1]


# --- api validation -------------------------------------------------------


def test_predict_rejects_unknown_disease():
    resp = client.post(
        "/predict",
        data={"disease": "heart_attack", "patientName": "A", "patientAge": "30"},
        files={"file": ("s.png", image_bytes(), "image/png")},
    )
    assert resp.status_code == 400


def test_predict_rejects_non_image():
    resp = client.post(
        "/predict",
        data={"disease": "brain_tumor", "patientName": "A", "patientAge": "30"},
        files={"file": ("s.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 415


def test_predict_rejects_bad_age():
    resp = client.post(
        "/predict",
        data={"disease": "brain_tumor", "patientName": "A", "patientAge": "400"},
        files={"file": ("s.png", image_bytes(), "image/png")},
    )
    assert resp.status_code == 422


def test_predict_rejects_tiny_image():
    resp = client.post(
        "/predict",
        data={"disease": "brain_tumor", "patientName": "A", "patientAge": "30"},
        files={"file": ("s.png", image_bytes(size=(8, 8)), "image/png")},
    )
    assert resp.status_code == 422


def test_predict_happy_path_writes_pdf():
    resp = client.post(
        "/predict",
        data={
            "disease": "knee_osteoarthritis",
            "patientName": "Test Patient",
            "patientAge": "54",
            "patientNotes": "Right knee pain, 6 months",
        },
        files={"file": ("knee.png", image_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["report_url"].startswith("/reports/")
    assert os.path.exists(body["report_pdf_path"])
    assert os.path.getsize(body["report_pdf_path"]) > 1000
    assert "heatmap_path" not in body
    assert body["patient"]["age"] == 54
    assert body["disclaimer"]
    assert body["provenance"]
    os.remove(body["report_pdf_path"])


# --- tabular heart risk ---------------------------------------------------

VALID_HEART = {
    "age": 63, "sex": 1, "cp": 3, "trestbps": 145, "chol": 233, "fbs": 1,
    "restecg": 0, "thalach": 150, "exang": 0, "oldpeak": 2.3, "slope": 0,
    "ca": 0, "thal": 1,
}


def test_heart_schema_documents_fields():
    body = client.get("/heart-risk/schema").json()
    assert set(body["fields"]) == set(VALID_HEART)
    assert "scope_note" in body


def test_heart_risk_prediction():
    import heart_risk

    if not heart_risk.is_available():
        pytest.skip("heart model not trained")
    body = client.post("/heart-risk", json=VALID_HEART).json()
    assert 0 <= body["risk_probability"] <= 100
    assert body["input_type"] == "tabular_clinical_variables"
    assert body["disclaimer"]
    assert body["metrics"]["held_out"]["accuracy"] > 0.5


def test_heart_metrics_expose_leakage_warning():
    import heart_risk

    if not heart_risk.is_available():
        pytest.skip("heart model not trained")
    metrics = client.get("/heart-risk/schema").json()["metrics"]
    assert metrics["duplicate_rows_removed"] > 0
    assert metrics["leaky_duplicate_split_accuracy"] > metrics["held_out"]["accuracy"]
    assert "honesty_note" in metrics


def test_heart_risk_rejects_out_of_range():
    payload = dict(VALID_HEART, age=500)
    assert client.post("/heart-risk", json=payload).status_code == 422
