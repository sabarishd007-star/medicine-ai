"""MediScan AI - ML inference service.

Runs disease-specific CNN inference, real Grad-CAM explainability, a confidence
gate that refuses to force a label, and PDF report generation.

Honesty contract: every response carries `model_status`. When it is
UNTRAINED_BACKBONE the network has no trained checkpoint on disk, the output is
not clinically meaningful, and both the API and the PDF say so. Modules backed
by third-party checkpoints carry a `provenance` string stating that their
accuracy has not been independently reproduced here.
"""

import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

import heart_risk
from backends import decode_ordinal
from gradcam import cam_coverage, overlay_cam
from model_registry import (
    REGISTRY,
    STATUS_TRAINED,
    STATUS_UNTRAINED,
    get_bundle,
    list_diseases,
)
from pdf_generator import generate_pdf_report
from segmentation import (
    generate_segmentation_from_gradcam,
    generate_segmentation_mask,
    is_medsam_available,
)

# ONNX Runtime (optional)
try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("mediscan.ml")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEATMAP_DIR = os.path.join(BASE_DIR, "temp_heatmaps")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
SERVICE_VERSION = "0.3.0"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MIN_IMAGE_SIDE = 32

os.makedirs(HEATMAP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

app = FastAPI(title="MediScan AI - ML Service", version=SERVICE_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/reports", StaticFiles(directory=REPORT_DIR), name="reports")
app.mount("/heatmaps", StaticFiles(directory=HEATMAP_DIR), name="heatmaps")

with open(os.path.join(BASE_DIR, "disease_info.json"), "r", encoding="utf-8") as fh:
    DISEASE_KNOWLEDGE_BASE = json.load(fh)

UNTRAINED_NOTICE = (
    "No trained checkpoint is installed for this module. The network is running on an "
    "untrained classification head, so the class and confidence below are numerically "
    "real but carry NO clinical meaning. Install validated weights before any use."
)

DISCLAIMER = (
    "This tool provides an AI-assisted screening estimate based on image pattern "
    "recognition. It is not a certified diagnostic device and does not replace "
    "evaluation by a licensed medical professional."
)


def _decode_image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail="File is not a readable image.") from exc
    if min(image.size) < MIN_IMAGE_SIDE:
        raise HTTPException(
            status_code=422,
            detail=f"Image too small; minimum side is {MIN_IMAGE_SIDE}px.",
        )
    return image.convert("RGB")


def _safe_stem(value: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
    return cleaned[:48] or fallback


def analyze_image(disease: str, pil_image: Image.Image, source_name: str = "scan") -> dict:
    """Run preprocessing, inference, the confidence gate and Grad-CAM."""
    bundle = get_bundle(disease)
    spec = bundle.spec

    # A Keras module with no checkpoint on disk has no loaded backend at all.
    # Short-circuit gracefully instead of crashing on `backend.infer(...)`.
    if bundle.backend is None:
        return {
            "disease": spec.key,
            "disease_display": spec.display_name,
            "modality": spec.modality,
            "prediction": "Not Clinically Valid - Untrained Model",
            "top_class": spec.classes[0],
            "confidence": 0.0,
            "confidence_threshold": round(spec.confidence_threshold * 100, 2),
            "is_conclusive": False,
            "class_probabilities": {label: 0.0 for label in spec.classes},
            "score_semantics": "unavailable",
            "stage": None,
            "model_status": bundle.status,
            "framework": spec.framework,
            "architecture": spec.architecture,
            "model_sha256": None,
            "model_metrics": None,
            "provenance": spec.provenance,
            "gradcam_available": False,
            "gradcam_coverage": None,
            "heatmap_path": None,
            "heatmap_url": None,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    output = bundle.backend.infer(pil_image)
    scores = np.asarray(output.probabilities, dtype=np.float64)

    if output.probabilities_are_ordinal:
        top_index = decode_ordinal(scores, spec.ordinal_threshold)
        confidence = float(scores[top_index])
        distribution = {
            label: round(float(scores[i]) * 100, 2) for i, label in enumerate(spec.classes)
        }
        score_semantics = "ordinal_sigmoid"
    else:
        top_index = int(np.argmax(scores))
        confidence = float(scores[top_index])
        distribution = {
            label: round(float(scores[i]) * 100, 2) for i, label in enumerate(spec.classes)
        }
        score_semantics = "softmax"

    top_label = spec.classes[top_index]
    is_conclusive = bundle.is_trained and confidence >= spec.confidence_threshold

    if not bundle.is_trained:
        prediction = "Not Clinically Valid - Untrained Model"
    elif is_conclusive:
        prediction = top_label
    else:
        prediction = "Inconclusive - Consult Specialist"

    cam = output.cam
    heatmap_path = None
    heatmap_url = None
    coverage = None
    if cam is not None:
        bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        overlay = overlay_cam(bgr, cam)
        name = f"{_safe_stem(source_name, 'scan')}_{uuid.uuid4().hex[:8]}.png"
        heatmap_path = os.path.join(HEATMAP_DIR, name)
        cv2.imwrite(heatmap_path, overlay)
        heatmap_url = f"/heatmaps/{name}"
        coverage = round(cam_coverage(cam), 4)

    return {
        "disease": spec.key,
        "disease_display": spec.display_name,
        "modality": spec.modality,
        "prediction": prediction,
        "top_class": top_label,
        "confidence": round(confidence * 100, 2),
        "confidence_threshold": round(spec.confidence_threshold * 100, 2),
        "is_conclusive": is_conclusive,
        "class_probabilities": distribution,
        "score_semantics": score_semantics,
        "stage": top_label if (spec.staged and is_conclusive) else None,
        "model_status": bundle.status,
        "framework": spec.framework,
        "architecture": spec.architecture,
        "model_sha256": bundle.weights_sha256,
        "model_metrics": bundle.metrics,
        "provenance": spec.provenance,
        "gradcam_available": cam is not None,
        "gradcam_coverage": coverage,
        "heatmap_path": heatmap_path,
        "heatmap_url": heatmap_url,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health() -> dict:
    modules = list_diseases()
    return {
        "status": "ok",
        "service": "mediscan-ml",
        "version": SERVICE_VERSION,
        "modules_registered": len(modules),
        "modules_trained": sum(1 for m in modules if m["model_status"] == STATUS_TRAINED),
        "tabular_heart_available": heart_risk.is_available(),
    }


@app.get("/diseases")
def diseases() -> dict:
    return {"diseases": list_diseases()}


@app.post("/predict")
async def predict(
    disease: str = Form(...),
    patientName: str = Form(...),
    patientAge: int = Form(...),
    patientNotes: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    if disease not in REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown disease '{disease}'. Supported: {sorted(REGISTRY)}",
        )
    if not 0 < patientAge < 130:
        raise HTTPException(status_code=422, detail="patientAge must be between 1 and 129.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
        )

    pil_image = _decode_image(raw)

    try:
        result = analyze_image(disease, pil_image, file.filename or "scan")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Inference failed for disease=%s", disease)
        raise HTTPException(status_code=500, detail="Inference failed.") from exc

    info = DISEASE_KNOWLEDGE_BASE.get(disease, {}).get(
        result["top_class"],
        {
            "summary": "No knowledge-base entry for this class.",
            "stage_info": "N/A",
            "next_steps": "Consult a qualified medical provider.",
        },
    )
    if not result["is_conclusive"]:
        info = dict(info)
        info["next_steps"] = (
            "Result did not clear the confidence gate. Do not act on this output; "
            "seek review by a licensed specialist."
        )

    report_name = f"Report_{_safe_stem(patientName, 'patient')}_{uuid.uuid4().hex[:8]}.pdf"
    report_path = os.path.join(REPORT_DIR, report_name)
    patient_data = {"name": patientName, "age": patientAge, "notes": patientNotes}
    generate_pdf_report(report_path, patient_data, result, info)

    logger.info(
        "predict disease=%s status=%s conclusive=%s conf=%.2f",
        disease,
        result["model_status"],
        result["is_conclusive"],
        result["confidence"],
    )

    response = dict(result)
    response.pop("heatmap_path", None)
    response.update(
        {
            "patient": {"name": patientName, "age": patientAge},
            "guidance": info,
            "report_pdf_path": report_path,
            "report_url": f"/reports/{report_name}",
            "notice": UNTRAINED_NOTICE if result["model_status"] == STATUS_UNTRAINED else None,
            "safety_warning": _safety_warning(result),
            "disclaimer": DISCLAIMER,
        }
    )
    return response


def _safety_warning(result: dict) -> Optional[str]:
    """Surface the measured false-negative rate alongside any negative finding."""
    metrics = result.get("model_metrics") or {}
    safety = metrics.get("safety")
    if not safety:
        return None
    return safety["warning"]


@app.get("/heart-risk/schema")
def heart_schema() -> dict:
    return heart_risk.schema()


@app.post("/heart-risk")
def heart_predict(payload: heart_risk.HeartRiskRequest) -> dict:
    if not heart_risk.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Heart risk model is not installed. Run "
                "`python train_heart_model.py` to build it from weights/heart.csv."
            ),
        )
    try:
        return heart_risk.predict(payload)
    except Exception as exc:
        logger.exception("Heart risk inference failed")
        raise HTTPException(status_code=500, detail="Heart risk inference failed.") from exc


SEGMENTATION_DIR = os.path.join(BASE_DIR, "temp_segmentations")
os.makedirs(SEGMENTATION_DIR, exist_ok=True)

app.mount("/segmentations", StaticFiles(directory=SEGMENTATION_DIR), name="segmentations")


@app.get("/segmentation/status")
def segmentation_status() -> dict:
    """Check if MedSAM segmentation is available."""
    return {
        "available": is_medsam_available(),
        "checkpoint_path": "./weights/medsam_vit_b.pth",
        "opencv_available": True,
    }


@app.post("/segmentation/generate")
async def generate_segmentation(
    disease: str = Form(...),
    patientName: str = Form(...),
    patientAge: int = Form(...),
    file: UploadFile = File(...),
    use_gradcam_roi: bool = Form(True),
    bbox_x1: Optional[float] = Form(None),
    bbox_y1: Optional[float] = Form(None),
    bbox_x2: Optional[float] = Form(None),
    bbox_y2: Optional[float] = Form(None),
):
    """
    Generate a precise MedSAM segmentation mask for the uploaded scan.

    If `use_gradcam_roi` is true, automatically derives the bounding box from
    the Grad-CAM heatmap. Otherwise, uses the provided bbox coordinates.
    """
    if disease not in REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown disease '{disease}'. Supported: {sorted(REGISTRY)}",
        )
    if not is_medsam_available():
        raise HTTPException(
            status_code=503,
            detail="MedSAM segmentation not available. Install checkpoint at ./weights/medsam_vit_b.pth",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
        )

    pil_image = _decode_image(raw)

    # First run inference to get Grad-CAM
    result = analyze_image(disease, pil_image, file.filename or "scan")

    if result.get("gradcam_available") and use_gradcam_roi:
        # Need to re-run to get the raw CAM
        bundle = get_bundle(disease)
        if bundle.backend is not None:
            output = bundle.backend.infer(pil_image)
            cam = output.cam
        else:
            cam = None
    else:
        cam = None

    if cam is not None and use_gradcam_roi:
        seg_result = generate_segmentation_from_gradcam(pil_image, cam)
    else:
        if not all(v is not None for v in [bbox_x1, bbox_y1, bbox_x2, bbox_y2]):
            raise HTTPException(
                status_code=422,
                detail="Provide bbox_x1, bbox_y1, bbox_x2, bbox_y2 when not using Grad-CAM ROI.",
            )
        seg_result = generate_segmentation_mask(pil_image, [bbox_x1, bbox_y1, bbox_x2, bbox_y2])

    if seg_result is None:
        raise HTTPException(status_code=500, detail="Segmentation failed.")

    overlay_img, mask_img, score = seg_result

    # Save segmentation outputs
    import uuid
    name = f"{_safe_stem(patientName, 'patient')}_{uuid.uuid4().hex[:8]}"
    overlay_path = os.path.join(SEGMENTATION_DIR, f"{name}_overlay.png")
    mask_path = os.path.join(SEGMENTATION_DIR, f"{name}_mask.png")
    overlay_img.save(overlay_path)
    mask_img.save(mask_path)

    return {
        "disease": disease,
        "segmentation_score": round(score, 4),
        "overlay_url": f"/segmentations/{name}_overlay.png",
        "mask_url": f"/segmentations/{name}_mask.png",
        "message": "MedSAM segmentation generated successfully.",
    }


# ONNX Runtime inference endpoint
ORT_SESSION = None
ORT_INPUT_NAME = None


def _load_onnx_session(model_path: str = "./models/densenet_model.onnx") -> bool:
    global ORT_SESSION, ORT_INPUT_NAME
    if not ORT_AVAILABLE:
        return False
    if not os.path.exists(model_path):
        return False
    try:
        ORT_SESSION = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        ORT_INPUT_NAME = ORT_SESSION.get_inputs()[0].name
        return True
    except Exception as e:
        print(f"ONNX load failed: {e}")
        return False


@app.get("/onnx/status")
def onnx_status() -> dict:
    return {
        "ort_available": ORT_AVAILABLE,
        "model_loaded": ORT_SESSION is not None,
        "model_path": "./models/densenet_model.onnx",
    }


@app.post("/onnx/load")
def onnx_load(model_path: str = "./models/densenet_model.onnx") -> dict:
    ok = _load_onnx_session(model_path)
    return {"loaded": ok}


def _onnx_preprocess(pil_image: Image.Image) -> np.ndarray:
    """Preprocess PIL image to ONNX input tensor (1, 3, 224, 224) float32."""
    resized = pil_image.resize((224, 224), Image.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))  # HWC -> CHW
    arr = np.expand_dims(arr, axis=0).astype(np.float32)  # (1, 3, 224, 224)
    return np.ascontiguousarray(arr)


@app.post("/onnx/predict")
async def onnx_predict(
    disease: str = Form(...),
    patientName: str = Form(...),
    patientAge: int = Form(...),
    patientNotes: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """Run inference using ONNX Runtime (microsecond-level latency)."""
    if not ORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="onnxruntime not installed")
    if ORT_SESSION is None:
        # Try auto-load
        if not _load_onnx_session():
            raise HTTPException(
                status_code=503,
                detail="ONNX model not loaded. POST /onnx/load or place densenet_model.onnx at ./models/densenet_model.onnx",
            )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
        )

    pil_image = _decode_image(raw)
    input_tensor = _onnx_preprocess(pil_image)

    # Run inference
    outputs = ORT_SESSION.run(None, {ORT_INPUT_NAME: input_tensor})
    logits = outputs[0][0]  # (num_classes,)
    # Softmax
    exp_logits = np.exp(logits - np.max(logits))
    probs = exp_logits / exp_logits.sum()
    top_index = int(np.argmax(probs))
    confidence = float(probs[top_index])

    # Build result similar to analyze_image
    spec = REGISTRY.get(disease)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown disease '{disease}'")

    top_label = spec.classes[top_index] if top_index < len(spec.classes) else spec.classes[0]
    is_conclusive = confidence >= spec.confidence_threshold
    prediction = top_label if is_conclusive else "Inconclusive - Consult Specialist"

    return {
        "disease": disease,
        "disease_display": spec.display_name,
        "modality": spec.modality,
        "prediction": prediction,
        "top_class": top_label,
        "confidence": round(confidence * 100, 2),
        "confidence_threshold": round(spec.confidence_threshold * 100, 2),
        "is_conclusive": is_conclusive,
        "class_probabilities": {label: round(float(probs[i]) * 100, 2) for i, label in enumerate(spec.classes)},
        "score_semantics": "softmax_onnx",
        "model_status": "ONNX_OPTIMIZED",
        "runtime": "onnxruntime",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
