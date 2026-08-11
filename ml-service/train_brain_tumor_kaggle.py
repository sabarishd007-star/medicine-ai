"""Train the brain tumor MRI classifier from the Kaggle download.

Consumes the dataset directly from a manual Kaggle download — no API key
needed. Download it once from:

    https://www.kaggle.com/datasets/sartajbhuvaji/brain-tumor-classification-mri

Click "Download" (~250 MB), extract the ZIP, and point this script at the
extracted folder with --data-dir.

Expected folder layout (matches the Kaggle download exactly):
    <data-dir>/
    ├── Training/
    │   ├── glioma/
    │   ├── meningioma/
    │   ├── notumor/
    │   └── pituitary/
    └── Testing/
        ├── glioma/
        ├── meningioma/
        ├── notumor/
        └── pituitary/

The Training split is used for train/validation (80/20 stratified). The Testing
split is held back completely and is the only data evaluate.py scores against —
this is what makes the final accuracy figure honest.

Usage:
    python train_brain_tumor_kaggle.py --data-dir C:/Downloads/brain-tumor
    python train_brain_tumor_kaggle.py --data-dir C:/Downloads/brain-tumor --epochs 8
"""

import argparse
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import transforms
from torchvision.models import ResNet18_Weights, resnet18

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
OUT_PATH = os.path.join(WEIGHTS_DIR, "brain_tumor.pth")

# Kaggle folder names -> registry class names. Order matters: the model output
# index must match model_registry.REGISTRY["brain_tumor"].classes.
# The Kaggle download uses the longer "_tumor" suffix on each folder.
FOLDER_TO_CLASS = {
    "glioma_tumor": "Glioma",
    "meningioma_tumor": "Meningioma",
    "no_tumor": "No Tumor",
    "pituitary_tumor": "Pituitary",
}
REGISTRY_CLASSES = ["Glioma", "Meningioma", "No Tumor", "Pituitary"]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
SEED = 42
VALIDATION_FRACTION = 0.2


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def collect_images(data_dir):
    """Return list of (path, class_index) from the Training and Testing folders."""
    train_dir = Path(data_dir) / "Training"
    test_dir = Path(data_dir) / "Testing"

    if not train_dir.exists():
        sys.exit(
            f"Expected a 'Training' folder under {data_dir}. "
            "Did you extract the Kaggle ZIP fully?"
        )

    train_entries = []
    test_entries = []

    for folder_name, class_name in FOLDER_TO_CLASS.items():
        class_index = REGISTRY_CLASSES.index(class_name)
        for directory in [train_dir / folder_name, test_dir / folder_name]:
            if not directory.exists():
                continue
            for path in directory.iterdir():
                if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                    target = train_entries if directory.parent.name == "Training" else test_entries
                    target.append((str(path), class_index))

    if not train_entries:
        sys.exit(f"No training images found under {train_dir}.")

    print(f"  Training images : {len(train_entries)}")
    print(f"  Held-out test   : {len(test_entries)}")
    return train_entries, test_entries


def split_train_validation(entries, fraction):
    """Stratified 80/20 split that keeps class proportions."""
    by_class = {}
    for path, label in entries:
        by_class.setdefault(label, []).append((path, label))

    train = []
    validation = []
    for label, items in by_class.items():
        random.shuffle(items)
        cutoff = int(len(items) * (1 - fraction))
        train.extend(items[:cutoff])
        validation.extend(items[cutoff:])
    random.shuffle(train)
    return train, validation


class MriDataset(Dataset):
    def __init__(self, entries, train=False):
        self.entries = entries
        if train:
            self.transform = transforms.Compose([
                transforms.Resize((256, 256)),
                transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(12),
                transforms.ColorJitter(brightness=0.15, contrast=0.15),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ])
        else:
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ])

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, index):
        path, label = self.entries[index]
        image = Image.open(path).convert("RGB")
        return self.transform(image), label


@torch.no_grad()
def accuracy(model, loader, device):
    model.eval()
    correct = total = 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        predictions = model(images).argmax(dim=1)
        correct += (predictions == labels).sum().item()
        total += labels.size(0)
    return correct / total if total else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", required=True,
        help="Path to the extracted Kaggle 'brain-tumor-classification-mri' folder",
    )
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    args = parser.parse_args()

    set_seed()
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}\n")

    print("Scanning dataset:")
    train_val_entries, test_entries = collect_images(args.data_dir)
    train_entries, val_entries = split_train_validation(train_val_entries, VALIDATION_FRACTION)
    print(f"  Training split  : {len(train_entries)}")
    print(f"  Validation split: {len(val_entries)}\n")

    train_loader = DataLoader(
        MriDataset(train_entries, train=True), batch_size=args.batch_size, shuffle=True
    )
    val_loader = DataLoader(MriDataset(val_entries), batch_size=args.batch_size)
    test_loader = DataLoader(MriDataset(test_entries), batch_size=args.batch_size)

    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Linear(model.fc.in_features, len(REGISTRY_CLASSES))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val = 0.0
    started = time.time()

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for index, (images, labels) in enumerate(train_loader, start=1):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running += loss.item()
            if index % 20 == 0:
                print(
                    f"  epoch {epoch} batch {index}/{len(train_loader)} "
                    f"loss={running / index:.4f}",
                    end="\r",
                    flush=True,
                )
        scheduler.step()

        val_accuracy = accuracy(model, val_loader, device)
        print(
            f"  epoch {epoch}: train_loss={running / max(len(train_loader), 1):.4f} "
            f"val_acc={val_accuracy:.4f}          "
        )

        if val_accuracy > best_val:
            best_val = val_accuracy
            torch.save(model.state_dict(), OUT_PATH)
            print(f"    saved new best -> {OUT_PATH}")

    if best_val == 0.0:
        sys.exit("Training did not produce a usable model. Check the dataset path.")

    model.load_state_dict(torch.load(OUT_PATH, map_location=device))
    test_accuracy = accuracy(model, test_loader, device)

    print(f"\nBest validation accuracy : {best_val:.4f}")
    print(f"Held-out test accuracy   : {test_accuracy:.4f}")
    print(f"Training time            : {(time.time() - started) / 60:.1f} min")

    with open(os.path.join(WEIGHTS_DIR, "brain_tumor.train.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "dataset": "Kaggle: sartajbhuvaji/brain-tumor-classification-mri",
                "source_url": "https://www.kaggle.com/datasets/sartajbhuvaji/brain-tumor-classification-mri",
                "splits": {
                    "train": len(train_entries),
                    "validation": len(val_entries),
                    "test": len(test_entries),
                },
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.lr,
                "architecture": "resnet18 (ImageNet pretrained, fine-tuned)",
                "best_val_accuracy": round(best_val, 4),
                "quick_test_accuracy": round(test_accuracy, 4),
                "note": (
                    "Author-defined Testing split used as held-out test. Run "
                    "evaluate.py for full per-class metrics and false-negative rate."
                ),
            },
            fh,
            indent=2,
        )

    print("\nNext: python evaluate.py --disease brain_tumor --limit 300")


if __name__ == "__main__":
    main()
