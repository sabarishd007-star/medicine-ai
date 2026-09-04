"""Export trained PyTorch model to ONNX format for accelerated inference.

Usage:
    python export_onnx.py --checkpoint ./weights/densenet_upgraded.pth --output ./weights/densenet_model.onnx --num-classes 4
"""
import os
import sys

import torch

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from model_registry import REGISTRY
except ImportError:
    REGISTRY = {}


def get_medical_model(num_classes: int, architecture: str = "densenet121"):
    """Load model architecture matching the checkpoint."""
    import torch.nn as nn
    from torchvision.models import densenet121, resnet18

    if "densenet" in architecture.lower():
        model = densenet121(weights=None)
        # Recreate the same classifier head used in retrain.py
        import torch.nn as nn
        num_features = model.classifier.in_features
        model.classifier = torch.nn.Sequential(
            torch.nn.Dropout(0.3),
            torch.nn.Linear(num_features, num_classes)
        )
    elif "resnet" in architecture.lower():
        from torchvision.models import resnet18
        model = resnet18(weights=None)
        import torch.nn as nn
        num_features = model.fc.in_features
        model.fc = torch.nn.Sequential(
            torch.nn.Dropout(0.3),
            torch.nn.Linear(num_features, num_classes)
        )
    else:
        raise ValueError(f"Unsupported architecture: {architecture}")

    # Resize final layer to num_classes
    if hasattr(model, 'classifier'):
        if isinstance(model.classifier, torch.nn.Sequential):
            # DenseNet style
            in_features = model.classifier[-1].in_features
            model.classifier[-1] = torch.nn.Linear(in_features, num_classes)
        else:
            in_features = model.classifier.in_features
            model.classifier = torch.nn.Linear(in_features, num_classes)
    elif hasattr(model, 'fc'):
        in_features = model.fc.in_features
        model.fc = torch.nn.Linear(in_features, num_classes)

    return model


def convert_to_onnx(
    checkpoint_path: str,
    output_path: str,
    num_classes: int = 4,
    input_shape: tuple = (1, 3, 224, 224),
    opset_version: int = 14,
) -> None:
    """Export trained checkpoint to ONNX format."""
    import torch

    model = get_medical_model(num_classes)

    # Load checkpoint
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    # Handle different checkpoint formats
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        # If checkpoint has class info, use it
        if "classes" in checkpoint:
            print(f"Checkpoint classes: {checkpoint['classes']}")
    else:
        state_dict = checkpoint

    # Handle potential key mismatches
    model_state = model.state_dict()
    filtered_state = {}
    for k, v in state_dict.items():
        # Remove 'module.' prefix from DataParallel
        k_clean = k.replace("module.", "")
        if k_clean in model_state and model_state[k_clean].shape == v.shape:
            filtered_state[k_clean] = v
        else:
            print(f"Skipping mismatched key: {k} (shape: {v.shape})")

    model.load_state_dict(filtered_state, strict=False)
    model.eval()

    # Dummy input
    dummy_input = torch.randn(1, 3, 224, 224)

    # Export
    output_file = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        output_file,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "output": {0: "batch_size"}
        },
        verbose=False
    )

    print(f"Model successfully exported to ONNX: {output_file}")

    # Verify the exported model
    import onnx
    onnx_model = onnx.load(output_file)
    onnx.checker.check_model(onnx_model)
    print("ONNX model validation passed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export PyTorch model to ONNX")
    parser.add_argument("--checkpoint", default="./weights/densenet_upgraded.pth", help="Path to PyTorch checkpoint")
    parser.add_argument("--output", default="./models/densenet_model.onnx", help="Output ONNX path")
    parser.add_argument("--num-classes", type=int, default=4, help="Number of output classes")
    args = parser.parse_args()

    convert_to_onnx(args.checkpoint, args.output, args.num_classes)
