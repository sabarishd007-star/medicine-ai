"""Disease model registry for MediScan AI.

Every entry describes a real checkpoint: its framework, architecture, class
taxonomy and preprocessing. Class lists mirror exactly what each upstream model
was trained to output - they are never padded to look more capable than they
are. A module with no checkpoint on disk is still served, but reported as
UNTRAINED_BACKBONE so no caller mistakes an untrained head for a clinical model.
"""

import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch
import torch.nn as nn
from torchvision.models import resnet18

import backends
from architectures import KneeResNet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")

STATUS_TRAINED = "TRAINED"
STATUS_UNTRAINED = "UNTRAINED_BACKBONE"

FRAMEWORK_TORCH = "pytorch"
FRAMEWORK_KERAS = "keras"


@dataclass(frozen=True)
class DiseaseSpec:
    key: str
    display_name: str
    modality: str
    classes: List[str]
    framework: str
    weights_file: str
    architecture: str
    input_size: int = 224
    confidence_threshold: float = 0.75
    dataset: str = ""
    staged: bool = False
    ordinal_threshold: Optional[float] = None
    last_conv_layer: Optional[str] = None
    nested_model: Optional[str] = None
    source: str = ""
    provenance: str = ""


REGISTRY: Dict[str, DiseaseSpec] = {
    "brain_tumor": DiseaseSpec(
        key="brain_tumor",
        display_name="Brain Tumor",
        modality="MRI",
        classes=["Glioma", "Meningioma", "No Tumor", "Pituitary"],
        framework=FRAMEWORK_TORCH,
        weights_file="brain_tumor.pth",
        architecture="resnet18",
        dataset="Kaggle Brain Tumor MRI Dataset",
        source="LovelySrenika/Brain-Tumor-Detection-Using-CNN",
        provenance="Upstream repository ships a notebook only, no checkpoint. Requires local training.",
    ),
    "knee_osteoarthritis": DiseaseSpec(
        key="knee_osteoarthritis",
        display_name="Knee Osteoarthritis",
        modality="Knee X-ray",
        classes=["Normal", "Non Severe OA", "Severe OA"],
        framework=FRAMEWORK_TORCH,
        weights_file="knee_osteoarthritis.pth",
        architecture="knee_resnet18_1ch",
        input_size=299,
        dataset="Knee Osteoarthritis Severity Grading",
        staged=True,
        source="shaina-12/Knee-Ostheoarthritis-Detection-and-Severity-Prediction",
        provenance=(
            "Third-party checkpoint 'Model Version3.pth'. Coarse 3-way severity, "
            "NOT the 5-point Kellgren-Lawrence scale. No independently reproduced test metrics."
        ),
    ),
    "skin_cancer": DiseaseSpec(
        key="skin_cancer",
        display_name="Skin Cancer",
        modality="Dermoscopy",
        classes=[
            "Basal Cell Carcinoma (Cancer)",
            "Melanoma (Cancer)",
            "Nevus (Non-Cancerous)",
        ],
        framework=FRAMEWORK_KERAS,
        weights_file="skin_cancer.h5",
        architecture="mobilenetv2",
        dataset="ISIC-derived 3-class subset",
        last_conv_layer="block_16_depthwise",
        source="sid321axn/skin_cancer_detection_webapp",
        provenance=(
            "Third-party MobileNetV2 checkpoint, 3 classes only. Does NOT cover the "
            "full HAM10000 7-class taxonomy. No independently reproduced test metrics."
        ),
    ),
    "diabetic_retinopathy": DiseaseSpec(
        key="diabetic_retinopathy",
        display_name="Diabetic Retinopathy",
        modality="Retinal Fundus",
        classes=[
            "No DR",
            "Mild Non-Proliferative DR",
            "Moderate Non-Proliferative DR",
            "Severe Non-Proliferative DR",
            "Proliferative DR",
        ],
        framework=FRAMEWORK_KERAS,
        weights_file="diabetic_retinopathy.h5",
        architecture="densenet121",
        dataset="APTOS/EyePACS-style DR grading",
        staged=True,
        ordinal_threshold=0.37757874193797547,
        last_conv_layer="relu",
        nested_model="densenet121",
        source="Akshar106/Diabetic-Retinopathy-Blindness-Detection-and-Staging",
        provenance=(
            "Third-party DenseNet121 with an ordinal sigmoid head decoded at the "
            "upstream threshold 0.3776. No independently reproduced test metrics."
        ),
    ),
    "pneumonia": DiseaseSpec(
        key="pneumonia",
        display_name="Pneumonia",
        modality="Chest X-ray",
        classes=["Normal", "Pneumonia"],
        framework=FRAMEWORK_KERAS,
        weights_file="pneumonia_cheXnet.h5",
        architecture="densenet121",
        input_size=224,
        dataset="NIH ChestX-ray14 / Kaggle Chest X-Ray Pneumonia (binary Normal/Pneumonia)",
        confidence_threshold=0.7,
        last_conv_layer="conv5_block32_concat",
        source="CheXNet (Rajpurkar et al., Stanford, 2017) / KlepeisLab/ChestX-ray14",
        provenance=(
            "CheXNet DenseNet-121 trained for radiologist-level pneumonia/opacity "
            "detection on chest X-rays (Rajpurkar et al., 'CheXNet: Radiologist-Level "
            "Pneumonia Detection on Chest X-Rays', Stanford ML Group, 2017). Supports "
            "Grad-CAM on the final DenseNet conv block. Install validated weights at "
            "ml-service/weights/pneumonia_cheXnet.h5; until then served as UNTRAINED_BACKBONE. "
            "See also: 'Trustworthy pneumonia detection in chest X-ray imaging' (PLOS ONE 2025, "
            "ViT + Grad-CAM) and 'Pneumonia and pneumothorax detection: A multi-factor "
            "evaluation' (PLOS ONE 2026, ViT on NIH ChestX-ray14)."
        ),
    ),
}


@dataclass
class ModelBundle:
    spec: DiseaseSpec
    backend: object
    status: str
    weights_path: Optional[str] = None
    weights_sha256: Optional[str] = None
    metrics: Optional[dict] = field(default=None)

    @property
    def is_trained(self) -> bool:
        return self.status == STATUS_TRAINED


_cache: Dict[str, ModelBundle] = {}
_lock = threading.Lock()


def weights_path(spec: DiseaseSpec) -> str:
    return os.path.join(WEIGHTS_DIR, spec.weights_file)


def _metrics_path(key: str) -> str:
    return os.path.join(WEIGHTS_DIR, f"{key}.metrics.json")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_metrics(key: str) -> Optional[dict]:
    path = _metrics_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def list_diseases() -> List[dict]:
    entries = []
    for spec in REGISTRY.values():
        trained = os.path.exists(weights_path(spec))
        entries.append(
            {
                "key": spec.key,
                "display_name": spec.display_name,
                "modality": spec.modality,
                "classes": list(spec.classes),
                "dataset": spec.dataset,
                "framework": spec.framework,
                "architecture": spec.architecture,
                "confidence_threshold": spec.confidence_threshold,
                "provides_stage": spec.staged,
                "model_status": STATUS_TRAINED if trained else STATUS_UNTRAINED,
                "source": spec.source,
                "provenance": spec.provenance,
                "metrics": _load_metrics(spec.key),
            }
        )
    return entries


def _build_torch_backend(spec: DiseaseSpec, path: str):
    if spec.architecture == "knee_resnet18_1ch":
        model = KneeResNet(num_classes=len(spec.classes))
        preprocess = backends.knee_preprocess
        target = model.layer3[-1]
    elif spec.architecture == "resnet18":
        model = resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, len(spec.classes))
        preprocess = backends.make_resnet_preprocess(spec.input_size)
        target = model.layer4[-1]
    else:
        raise ValueError(f"Unsupported torch architecture: {spec.architecture}")

    status = STATUS_UNTRAINED
    digest = None
    if os.path.exists(path):
        state = torch.load(path, map_location="cpu")
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        state = {k.replace("module.", "", 1): v for k, v in state.items()}
        model.load_state_dict(state)
        status = STATUS_TRAINED
        digest = _sha256(path)

    model.eval()
    for param in model.parameters():
        param.requires_grad_(True)

    return backends.TorchBackend(model, target, preprocess), status, digest


def _build_keras_backend(spec: DiseaseSpec, path: str):
    if not os.path.exists(path):
        return None, STATUS_UNTRAINED, None

    import tf_keras

    model = tf_keras.models.load_model(path, compile=False)

    if spec.key == "skin_cancer":
        preprocess = backends.skin_preprocess
    elif spec.key == "diabetic_retinopathy":
        preprocess = backends.dr_preprocess
    elif spec.key == "pneumonia":
        preprocess = backends.cxr_preprocess
    else:
        preprocess = backends.skin_preprocess

    backend = backends.KerasBackend(
        model=model,
        preprocess=preprocess,
        last_conv_layer=spec.last_conv_layer,
        nested_model=spec.nested_model,
        ordinal=spec.ordinal_threshold is not None,
    )
    return backend, STATUS_TRAINED, _sha256(path)


def get_bundle(disease: str) -> ModelBundle:
    if disease not in REGISTRY:
        raise KeyError(disease)

    cached = _cache.get(disease)
    if cached is not None:
        return cached

    with _lock:
        cached = _cache.get(disease)
        if cached is not None:
            return cached

        spec = REGISTRY[disease]
        path = weights_path(spec)

        if spec.framework == FRAMEWORK_TORCH:
            backend, status, digest = _build_torch_backend(spec, path)
        elif spec.framework == FRAMEWORK_KERAS:
            backend, status, digest = _build_keras_backend(spec, path)
        else:
            raise ValueError(f"Unsupported framework: {spec.framework}")

        bundle = ModelBundle(
            spec=spec,
            backend=backend,
            status=status,
            weights_path=path if status == STATUS_TRAINED else None,
            weights_sha256=digest,
            metrics=_load_metrics(disease),
        )
        _cache[disease] = bundle
        return bundle


def clear_cache() -> None:
    with _lock:
        _cache.clear()
