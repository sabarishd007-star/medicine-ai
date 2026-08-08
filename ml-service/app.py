import io
import json
import os
import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pdf_generator import generate_pdf_report

app = FastAPI(title="MediScan AI - ML Service")

# Create folders if missing
os.makedirs("temp_heatmaps", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Serve generated reports statically for web downloads
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Load static disease knowledge base
with open("disease_info.json", "r") as f:
    DISEASE_KNOWLEDGE_BASE = json.load(f)

CONFIDENCE_THRESHOLD = 0.75  # 75% cutoff safeguard

CLASS_LABELS = {
    "brain_tumor": ["Glioma", "Meningioma", "No Tumor", "Pituitary"],
    "pneumonia": ["Normal", "Pneumonia"]
}

@app.post("/predict")
async def predict(
    disease: str = Form(...),
    patientName: str = Form(...),
    patientAge: int = Form(...),
    file: UploadFile = File(...)
):
    # Load and process image
    image_bytes = await file.read()
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # Simulated AI inference & Grad-CAM visual generation
    classes = CLASS_LABELS.get(disease, ["Class A", "Class B"])
    simulated_conf = round(float(np.random.uniform(0.70, 0.98)), 4)
    simulated_idx = int(np.random.choice(len(classes)))

    if simulated_conf < CONFIDENCE_THRESHOLD:
        pred_label = "Inconclusive - Consult Specialist"
        is_conclusive = False
    else:
        pred_label = classes[simulated_idx]
        is_conclusive = True

    # Generate synthetic Grad-CAM heatmap overlay for preview
    height, width, _ = cv_img.shape
    heatmap = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(heatmap, (width // 2, height // 2), min(width, height) // 3, 255, -1)
    heatmap = cv2.GaussianBlur(heatmap, (101, 101), 0)
    colored_heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    superimposed = cv2.addWeighted(cv_img, 0.6, colored_heatmap, 0.4, 0)

    heatmap_filename = f"temp_heatmaps/heatmap_{file.filename}"
    cv2.imwrite(heatmap_filename, superimposed)

    # Get static guidance
    info = DISEASE_KNOWLEDGE_BASE.get(disease, {}).get(pred_label, {
        "summary": "Screening output generated. Consult a specialist for formal verification.",
        "next_steps": "Consult a qualified medical provider."
    })

    # Generate PDF Report
    pdf_filename = f"reports/Report_{patientName.replace(' ', '_')}.pdf"
    patient_data = {"name": patientName, "age": patientAge}
    prediction_data = {
        "disease": disease,
        "prediction": pred_label,
        "confidence": round(simulated_conf * 100, 2),
        "is_conclusive": is_conclusive,
        "heatmap_path": heatmap_filename
    }
    
    generate_pdf_report(pdf_filename, patient_data, prediction_data, info)

    return {
        "prediction": pred_label,
        "confidence": round(simulated_conf * 100, 2),
        "is_conclusive": is_conclusive,
        "heatmap_path": heatmap_filename,
        "report_pdf_path": pdf_filename
    }