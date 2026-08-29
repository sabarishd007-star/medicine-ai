"""MedSAM segmentation integration for MediScan AI.

Provides precise lesion/tumor boundary masks using the Medical Segment Anything Model.
Falls back gracefully if MedSAM checkpoint is not available.
"""
import os
import numpy as np
from typing import Optional, Tuple, List
from PIL import Image

# Optional dependency - only loaded when needed
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# MedSAM model (lazy-loaded)
_sam_predictor = None
_sam_loaded = False


def _load_medsam(checkpoint_path: str = "./weights/medsam_vit_b.pth") -> bool:
    """Load MedSAM model. Returns True if successful."""
    global _sam_predictor, _sam_loaded
    if _sam_loaded:
        return _sam_predictor is not None

    _sam_loaded = True

    if not CV2_AVAILABLE:
        print("Warning: opencv-python not installed, MedSAM unavailable")
        return False

    if not os.path.exists(checkpoint_path):
        print(f"MedSAM checkpoint not found at {checkpoint_path}")
        print("Download from: https://github.com/bowang-lab/MedSAM")
        return False

    try:
        from segment_anything import sam_model_registry, SamPredictor
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        sam = sam_model_registry["vit_b"](checkpoint=checkpoint_path)
        sam.to(device=device)
        _sam_predictor = SamPredictor(sam)
        print(f"MedSAM loaded on {device}")
        return True
    except ImportError:
        print("Warning: segment-anything not installed. Install with: pip install segment-anything-fast")
        return False
    except Exception as e:
        print(f"Warning: Failed to load MedSAM: {e}")
        return False


def generate_segmentation_mask(
    image: Image.Image,
    bbox_coords: List[float],
    checkpoint_path: str = "./weights/medsam_vit_b.pth"
) -> Optional[Tuple[Image.Image, float]]:
    """
    Generate a precise segmentation mask for a region of interest.

    Args:
        image: PIL Image (RGB) - the original medical scan
        bbox_coords: [x1, y1, x2, y2] bounding box of region of interest
        checkpoint_path: Path to MedSAM vit_b checkpoint

    Returns:
        Tuple of (mask_overlay_image, confidence_score) or None if unavailable
    """
    if not _load_medsam(checkpoint_path):
        return None

    try:
        # Convert PIL to numpy (RGB)
        image_np = np.array(image.convert("RGB"))
        if image_np.ndim != 3 or image_np.shape[2] != 3:
            raise ValueError("Image must be RGB")

        # Set image in predictor
        _sam_predictor.set_image(image_np)

        # Prepare input box
        import numpy as np
        input_box = np.array(bbox_coords, dtype=np.float32)

        # Predict mask
        masks, scores, _ = _sam_predictor.predict(
            box=input_box[None, :],
            multimask_output=False
        )

        if len(masks) == 0:
            return None

        mask = masks[0]  # (H, W) boolean
        score = float(scores[0])

        # Create colored overlay (red with transparency)
        overlay = image_np.copy()
        red_color = np.array([255, 0, 0], dtype=np.uint8)
        overlay[mask] = (overlay[mask] * 0.5 + red_color * 0.5).astype(np.uint8)

        # Also create pure mask image for download
        mask_img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        overlay_img = Image.fromarray(overlay)

        return overlay_img, mask_img, score

    except Exception as e:
        print(f"MedSAM segmentation failed: {e}")
        return None


def generate_segmentation_from_gradcam(
    image: Image.Image,
    gradcam_heatmap: np.ndarray,
    threshold: float = 0.5,
    checkpoint_path: str = "./weights/medsam_vit_b.pth"
) -> Optional[Tuple[Image.Image, Image.Image, float]]:
    """
    Automatically derive a bounding box from Grad-CAM heatmap and run MedSAM.

    Args:
        image: Original PIL image
        gradcam_heatmap: Normalized Grad-CAM heatmap [0,1]
        threshold: Heatmap threshold to determine ROI bounding box
        checkpoint_path: Path to MedSAM checkpoint

    Returns:
        Tuple of (overlay_img, mask_img, score) or None
    """
    # Find bounding box of high-activation region
    binary = (gradcam_heatmap > threshold).astype(np.uint8)
    if binary.sum() == 0:
        return None

    coords = np.column_stack(np.where(binary > 0))
    y1, x1 = coords.min(axis=0)
    y2, x2 = coords.max(axis=0)

    # Add padding
    h, w = binary.shape
    pad = max(10, int(0.05 * max(h, w)))
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w - 1, x2 + pad)
    y2 = min(h - 1, y2 + pad)

    bbox = [float(x1), float(y1), float(x2), float(y2)]
    return generate_segmentation_mask(image, bbox, checkpoint_path)


def is_medsam_available(checkpoint_path: str = "./weights/medsam_vit_b.pth") -> bool:
    """Check if MedSAM is loadable without actually loading it."""
    return CV2_AVAILABLE and os.path.exists(checkpoint_path)


if __name__ == "__main__":
    # Quick self-test
    print("MedSAM available:", is_medsam_available())
    print("OpenCV available:", CV2_AVAILABLE)