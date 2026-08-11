"""Grad-CAM implementation for MediScan AI.

Real gradient-based class activation mapping: forward/backward hooks capture the
activations and gradients of the chosen convolutional layer, the channel weights
are the globally averaged gradients, and the map is the ReLU of their weighted
sum. No synthetic shapes are drawn anywhere in this module.
"""

from typing import Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class GradCAM:
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.target_layer = target_layer
        self._activations = None
        self._gradients = None
        self._handles = []

    def __enter__(self) -> "GradCAM":
        self._handles.append(self.target_layer.register_forward_hook(self._save_activation))
        self._handles.append(self.target_layer.register_full_backward_hook(self._save_gradient))
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def release(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        self._activations = None
        self._gradients = None

    def _save_activation(self, _module, _inputs, output) -> None:
        self._activations = output

    def _save_gradient(self, _module, _grad_input, grad_output) -> None:
        self._gradients = grad_output[0]

    def run(self, input_tensor: torch.Tensor, class_index: int = None) -> Tuple[np.ndarray, torch.Tensor]:
        """Return (normalized CAM in [0,1], logits) for the given batch of one."""
        self.model.zero_grad(set_to_none=True)
        if not input_tensor.requires_grad:
            input_tensor = input_tensor.clone().requires_grad_(True)
        logits = self.model(input_tensor)
        if class_index is None:
            class_index = int(logits.argmax(dim=1).item())
        score = logits[0, class_index]
        score.backward(retain_graph=False)

        if self._activations is None or self._gradients is None:
            raise RuntimeError("Grad-CAM hooks captured no activations; check target layer.")

        weights = self._gradients.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((weights * self._activations).sum(dim=1, keepdim=True))
        cam = cam[0, 0].detach().cpu().numpy()

        cam = cam - cam.min()
        peak = cam.max()
        if peak > 0:
            cam = cam / peak
        return cam.astype(np.float32), logits.detach()


def overlay_cam(bgr_image: np.ndarray, cam: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    """Blend a [0,1] CAM over the original BGR image at its native resolution."""
    height, width = bgr_image.shape[:2]
    resized = cv2.resize(cam, (width, height), interpolation=cv2.INTER_LINEAR)
    heatmap = cv2.applyColorMap(np.uint8(255 * resized), cv2.COLORMAP_JET)
    return cv2.addWeighted(bgr_image, 1.0 - alpha, heatmap, alpha, 0)


def cam_coverage(cam: np.ndarray, threshold: float = 0.5) -> float:
    """Fraction of the map above `threshold`; a diffuse map is a weak explanation."""
    if cam.size == 0:
        return 0.0
    return float((cam >= threshold).sum() / cam.size)
