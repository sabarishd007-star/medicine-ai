"""Automated retraining pipeline for MediScan AI.

Usage:
    python retrain.py --data-dir ./data/uploads --epochs 5 --lr 1e-4
"""
import argparse
import os
import sys

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

# Add parent dir to path for model import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from model_registry import REGISTRY, FRAMEWORK_TORCH
except ImportError:
    # Fallback if model_registry not available
    REGISTRY = {}
    FRAMEWORK_TORCH = "pytorch"


def get_medical_model(num_classes: int, architecture: str = "densenet121") -> nn.Module:
    """Load a pretrained medical imaging model and replace its classifier head."""
    if architecture == "densenet121":
        from torchvision.models import densenet121, DenseNet121_Weights
        model = densenet121(weights=DenseNet121_Weights.DEFAULT)
        num_features = model.classifier.in_features
        model.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, num_classes)
        )
    elif architecture == "resnet18":
        from torchvision.models import resnet18, ResNet18_Weights
        model = resnet18(weights=ResNet18_Weights.DEFAULT)
        num_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, num_classes)
        )
    elif architecture == "efficientnet_b4":
        from torchvision.models import efficientnet_b4, EfficientNet_B4_Weights
        model = efficientnet_b4(weights=EfficientNet_B4_Weights.DEFAULT)
        num_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, num_classes)
        )
    else:
        raise ValueError(f"Unsupported architecture: {architecture}")
    return model


def retrain_model(
    data_dir: str = "./data/uploads",
    epochs: int = 5,
    lr: float = 1e-4,
    batch_size: int = 16,
    architecture: str = "densenet121",
    output_path: str = "./weights/densenet_upgraded.pth"
) -> None:
    """Fine-tune a pretrained model on new upload data."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Data augmentation + normalization (ImageNet stats)
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    train_dataset = datasets.ImageFolder(root=data_dir, transform=transform)
    if len(train_dataset) == 0:
        raise ValueError(f"No images found in {data_dir}")

    print(f"Found {len(train_dataset)} images across {len(train_dataset.classes)} classes: {train_dataset.classes}")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2)

    model = get_medical_model(num_classes=len(train_dataset.classes), architecture=architecture).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    model.train()
    for epoch in range(1, epochs + 1):
        running_loss = 0.0
        correct = 0
        total = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        scheduler.step()
        epoch_loss = running_loss / len(train_loader)
        acc = 100. * correct / total
        print(f"Epoch [{epoch}/{epochs}], Loss: {epoch_loss:.4f}, Acc: {acc:.2f}%")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    torch.save({
        "model_state_dict": model.state_dict(),
        "classes": train_dataset.classes,
        "architecture": architecture,
        "epochs": epochs,
    }, output_path)
    print(f"Retraining complete. Model saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediScan AI automated retraining")
    parser.add_argument("--data-dir", default="./data/uploads", help="Directory with class-subfolder images")
    parser.add_argument("--epochs", type=int, default=5, help="Training epochs")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--architecture", default="densenet121", choices=["densenet121", "resnet18", "efficientnet_b4"])
    parser.add_argument("--output", default="./weights/densenet_upgraded.pth", help="Output checkpoint path")
    args = parser.parse_args()

    retrain_model(
        data_dir=args.data_dir,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        architecture=args.architecture,
        output_path=args.output,
    )