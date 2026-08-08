"""Pluggable inference backends for MediScan AI.

Each backend exposes the same contract:

    infer(pil_image) -> InferenceOutput(probabilities, cam)

`probabilities` is a 1-D numpy array summing to 1.0 (or per-class sigmoid scores
for ordinal heads, flagged via `probabilities_are_ordinal`). `cam` is a [0,1]
Grad-CAM map, or None when the architecture exposes no usable conv layer.

Two backends exist because the upstream projects shipped different runtimes:
PyTorch for knee osteoarthritis, legacy Keras (.h5) for skin cancer and
diabetic retinopathy.
"""

import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from gradcam import GradCAM  # noqa: E402

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class InferenceOutput:
    probabilities: np.ndarray
    cam: Optional[np.ndarray]
    probabilities_are_ordinal: bool = False


class TorchBackend:
    """Generic PyTorch backend with hook-based Grad-CAM."""

    framework = "pytorch"

    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module, preprocess):
        self.model = model
        self.target_layer = target_layer
        self.preprocess = preprocess

    def infer(self, pil_image: Image.Image) -> InferenceOutput:
        tensor = self.preprocess(pil_image)
        with GradCAM(self.model, self.target_layer) as engine:
            cam, logits = engine.run(tensor)
        probabilities = F.softmax(logits, dim=1)[0].detach().cpu().numpy()
        return InferenceOutput(probabilities=probabilities, cam=cam)


class KerasBackend:
    """Legacy-Keras (.h5) backend with TF GradientTape Grad-CAM."""

    framework = "keras"

    def __init__(
        self,
        model,
        preprocess,
        last_conv_layer: Optional[str] = None,
        nested_model: Optional[str] = None,
        ordinal: bool = False,
    ):
        self.model = model
        self.preprocess = preprocess
        self.last_conv_layer = last_conv_layer
        self.nested_model = nested_model
        self.ordinal = ordinal

    @staticmethod
    def _apply_head(layers, x, class_index):
        """Replay the classifier head, taking the final Dense pre-activation.

        Softmax and sigmoid heads saturate to 1.0, which drives the gradient to
        ~1e-6 and yields an all-zero CAM. Differentiating the raw logit instead
        is the standard fix and is what the original Grad-CAM paper specifies.
        """
        import tensorflow as tf

        last = layers[-1] if layers else None
        for layer in layers:
            if layer is last and layer.__class__.__name__ == "Dense":
                weights = layer.get_weights()
                kernel = weights[0]
                x = tf.matmul(x, kernel)
                if len(weights) > 1:
                    x = x + weights[1]
            else:
                x = layer(x, training=False)
        return x[:, class_index]

    def _cam(self, array: np.ndarray, class_index: int) -> Optional[np.ndarray]:
        if not self.last_conv_layer:
            return None
        import tensorflow as tf
        import tf_keras

        if self.nested_model:
            # The conv layer lives inside a nested functional model (e.g. DenseNet121).
            # Expose both its activation and the nested model's own output, then replay
            # only the outer head layers. Replaying the nested model layer-by-layer is
            # not possible because of its skip connections.
            inner = self.model.get_layer(self.nested_model)
            grad_model = tf_keras.models.Model(
                inner.inputs,
                [inner.get_layer(self.last_conv_layer).output, inner.output],
            )
            head = [layer for layer in self.model.layers if layer.name != self.nested_model]

            with tf.GradientTape() as tape:
                features, inner_output = grad_model(array, training=False)
                tape.watch(features)
                channel = self._apply_head(head, inner_output, class_index)
            grads = tape.gradient(channel, features)
        else:
            conv_output = self.model.get_layer(self.last_conv_layer).output
            grad_model = tf_keras.models.Model(
                self.model.inputs, [conv_output, self.model.output]
            )
            with tf.GradientTape() as tape:
                features, preds = grad_model(array, training=False)
                tape.watch(features)
                channel = preds[:, class_index]
            grads = tape.gradient(channel, features)

        if grads is None:
            return None

        pooled = tf.reduce_mean(grads, axis=(0, 1, 2))
        cam = tf.squeeze(features[0] @ pooled[..., tf.newaxis]).numpy()
        cam = np.maximum(cam, 0)
        peak = cam.max()
        if peak > 0:
            cam = cam / peak
        return cam.astype(np.float32)

    def infer(self, pil_image: Image.Image) -> InferenceOutput:
        array = self.preprocess(pil_image)
        raw = np.asarray(self.model.predict(array, verbose=0)[0], dtype=np.float32)
        class_index = int(np.argmax(raw))
        cam = None
        try:
            cam = self._cam(array, class_index)
        except Exception:  # Grad-CAM must never take down an inference
            cam = None
        return InferenceOutput(
            probabilities=raw,
            cam=cam,
            probabilities_are_ordinal=self.ordinal,
        )


def knee_preprocess(pil_image: Image.Image) -> torch.Tensor:
    """Deterministic port of the upstream albumentations inference pipeline.

    Upstream applied HorizontalFlip(p=0.5) and Rotate(p=0.5) at prediction time.
    Those are training augmentations: keeping them would make the same scan
    return different answers on repeated uploads, so they are deliberately
    dropped here. Everything else matches the original transform exactly.
    """
    bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    gray = cv2.resize(gray, (299, 299), interpolation=cv2.INTER_LINEAR)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    gray = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(9, 9)).apply(gray)

    height, width = gray.shape[:2]
    crop_h, crop_w = 200, 280
    top = max((height - crop_h) // 2, 0)
    left = max((width - crop_w) // 2, 0)
    gray = gray[top : top + crop_h, left : left + crop_w]

    gray = cv2.resize(gray, (299, 299), interpolation=cv2.INTER_LINEAR)

    arr = gray.astype(np.float32) / 255.0
    arr = (arr - 0.6093) / 0.1534
    return torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)


def make_resnet_preprocess(size: int):
    def _preprocess(pil_image: Image.Image) -> torch.Tensor:
        resized = pil_image.resize((size, size), Image.BILINEAR)
        arr = np.asarray(resized, dtype=np.float32) / 255.0
        arr = (arr - IMAGENET_MEAN) / IMAGENET_STD
        arr = np.transpose(arr, (2, 0, 1))
        return torch.from_numpy(np.ascontiguousarray(arr)).unsqueeze(0)

    return _preprocess


def skin_preprocess(pil_image: Image.Image) -> np.ndarray:
    """Upstream: PIL resize to 224 then scale to [0,1]."""
    resized = pil_image.resize((224, 224), Image.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


def dr_preprocess(pil_image: Image.Image) -> np.ndarray:
    """Upstream: PIL resize to 224, kept as raw uint8 values (no rescale)."""
    resized = pil_image.resize((224, 224), Image.BILINEAR)
    arr = np.asarray(resized, dtype=np.uint8).astype(np.float32)
    return np.expand_dims(arr, axis=0)


def decode_ordinal(scores: np.ndarray, threshold: float) -> int:
    """Ordinal (CORAL-style) head: stage = count of sigmoid units above threshold - 1."""
    return int(max((scores > threshold).sum() - 1, 0))
