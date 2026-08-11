"""Train a 7-class skin cancer detector on the full HAM10000 dataset.

The current skin_cancer module runs a third-party 3-class checkpoint that
misses 57% of melanomas and 71% of BCC. That checkpoint was trained on a small
subset and never sees four of the seven HAM10000 lesion types.

This script fine-tunes a pretrained EfficientNet-B0 on the full 7-class
taxonomy so the model covers the same classes the registry already declares:

    Actinic Keratosis, Basal Cell Carcinoma, Benign Keratosis,
    Dermatofibroma, Melanoma, Melanocytic Nevus, Vascular Lesion

It consumes the HAM10000 download from Kaggle — no API key needed:

    https://www.kaggle.com/datasets/kmader/skin-cancer-mnist-ham10000

Download, extract the ZIP, and point this script at the extracted folder with
--data-dir. Expected layout:

    <data-dir>/
    ├── HAM10000_images_part_1/
    ├── HAM10000_images_part_2/
    └── HAM10000_metadata.csv

The CSV maps each image file to its dx label. The script merges the two image
part folders and does an 80/10/10 train/val/test split stratified by class. The
test split is held back completely and scored by evaluate.py.

Usage:
    python train_skin_cancer_ham10000.py --data-dir C:/Downloads/ham10000
    python train_skin_cancer_ham10000.py --data-dir C:/Downloads/ham10000 --epochs 12
"""

import argparse
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
OUT_PATH = os.path.join(WEIGHTS_DIR, "skin_cancer.pth")

# HAM10000 dx codes -> registry class names. The registry already declares
# these seven; the checkpoint just never matched them.
DX_TO_CLASS = {
    "akiec": "Actinic Keratosis",
    "bcc": "Basal Cell Carcinoma",
    "bkl": "Benign Keratosis",
    "df": "Dermatofibroma",
    "mel": "Melanoma",
    "nv": "Melanocytic Nevus",
    "vasc": "Vascular Lesion",
}
REGISTRY_CLASSES = [
    "Actinic Keratosis",
    "Basal Cell Carcinoma",
    "Benign Keratosis",
    "Dermatofibroma",
    "Melanoma",
    "Melanocytic Nevus",
    "Vascular Lesion",
]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
SEED = 42
IMAGE_SIZE = 224
VALIDATION_FRACTION = 0.1
TEST_FRACTION = 0.1


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def collect_images(data_dir):
    """Return list of (image_path, class_index) from the HAM10000 download."""
    data_dir = Path(data_dir)
    csv_candidates = list(data_dir.glob("**/HAM10000_metadata.csv"))
    if not csv_candidates:
        sys.exit(f"Could not find HAM10000_metadata.csv under {data_dir}.")
    metadata = pd.read_csv(csv_candidates[0])

    image_dirs = []
    for candidate in ["HAM10000_images_part_1", "HAM10000_images_part_2"]:
        path = data_dir / candidate
        if path.exists():
            image_dirs.append(path)
    if not image_dirs:
        # Some extracts put images directly in the data dir.
        image_dirs = [data_dir]

    # Build a fast lookup from filename to full path.
    filename_to_path = {}
    for directory in image_dirs:
        for path in directory.iterdir():
            if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                filename_to_path[path.name] = path

    entries = []
    missing = 0
    for _, row in metadata.iterrows():
        dx = str(row["dx"]).strip().lower()
        if dx not in DX_TO_CLASS:
            continue
        class_index = REGISTRY_CLASSES.index(DX_TO_CLASS[dx])
        image_id = row["image_id"]
        # HAM10000 images are named "<image_id>.jpg"
        path = filename_to_path.get(f"{image_id}.jpg")
        if path is None:
            missing += 1
            continue
        entries.append((str(path), class_index))

    print(f"  matched images   : {len(entries)}")
    if missing:
        print(f"  missing images   : {missing} (check that both image parts are extracted)")
    return entries


def stratified_split(entries, val_fraction, test_fraction):
    by_class = {}
    for path, label in entries:
        by_class.setdefault(label, []).append((path, label))

    train, val, test = [], [], []
    for label, items in by_class.items():
        random.shuffle(items)
        n = len(items)
        n_test = max(1, int(n * test_fraction))
        n_val = max(1, int(n * val_fraction))
        test.extend(items[:n_test])
        val.extend(items[n_test : n_test + n_val])
        train.extend(items[n_test + n_val :])
    random.shuffle(train)
    return train, val, test


class DermoscopyDataset(Dataset):
    def __init__(self, entries, train=False):
        self.entries = entries
        if train:
            self.transform = transforms.Compose([
                transforms.Resize((IMAGE_SIZE + 32, IMAGE_SIZE + 32)),
                transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.8, 1.0)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomVerticalFlip(),
                transforms.RandomRotation(20),
                transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ])
        else:
            self.transform = transforms.Compose([
                transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
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
def evaluate(model, loader, device):
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
    parser.add_argument("--data-dir", required=True, help="Extracted HAM10000 folder")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    args = parser.parse_args()

    set_seed()
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}\n")

    print("Scanning HAM10000:")
    entries = collect_images(args.data_dir)
    train_entries, val_entries, test_entries = stratified_split(
        entries, VALIDATION_FRACTION, TEST_FRACTION
    )
    print(f"  train: {len(train_entries)}  val: {len(val_entries)}  test: {len(test_entries)}\n")

    # Class weights: HAM10000 is dominated by nv (~7000 of 10k). Up-weight the
    # six rare classes so the model actually learns to detect cancers instead
    # of guessing "nevus" for everything.
    class_counts = {}
    for _, label in train_entries:
        class_counts[label] = class_counts.get(label, 0) + 1
    total = sum(class_counts.values())
    weights = torch.tensor(
        [total / class_counts.get(i, 1) for i in range(len(REGISTRY_CLASSES))],
        dtype=torch.float32,
    )
    weights = weights / weights.mean()
    print(f"  class weights : {dict(zip(REGISTRY_CLASSES, [round(w.item(), 2) for w in weights]))}\n")

    train_loader = DataLoader(
        DermoscopyDataset(train_entries, train=True), batch_size=args.batch_size, shuffle=True
    )
    val_loader = DataLoader(DermoscopyDataset(val_entries), batch_size=args.batch_size)
    test_loader = DataLoader(DermoscopyDataset(test_entries), batch_size=args.batch_size)

    model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(REGISTRY_CLASSES))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss(weight=weights.to(device))
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
            if index % 30 == 0:
                print(
                    f"  epoch {epoch} batch {index}/{len(train_loader)} "
                    f"loss={running / index:.4f}",
                    end="\r",
                    flush=True,
                )
        scheduler.step()

        val_accuracy = evaluate(model, val_loader, device)
        print(
            f"  epoch {epoch}: train_loss={running / max(len(train_loader), 1):.4f} "
            f"val_acc={val_accuracy:.4f}          "
        )

        if val_accuracy > best_val:
            best_val = val_accuracy
            torch.save(
                {"state_dict": model.state_dict(), "classes": REGISTRY_CLASSES}, OUT_PATH
            )
            print(f"    saved new best -> {OUT_PATH}")

    if best_val == 0.0:
        sys.exit("Training did not produce a usable model.")

    checkpoint = torch.load(OUT_PATH, map_location=device)
    model.load_state_dict(checkpoint["state_dict"])
    test_accuracy = evaluate(model, test_loader, device)

    print(f"\nBest validation accuracy : {best_val:.4f}")
    print(f"Held-out test accuracy   : {test_accuracy:.4f}")
    print(f"Training time            : {(time.time() - started) / 60:.1f} min")

    with open(os.path.join(WEIGHTS_DIR, "skin_cancer.train.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "dataset": "HAM10000 (kmader/skin-cancer-mnist-ham10000)",
                "source_url": "https://www.kaggle.com/datasets/kmader/skin-cancer-mnist-ham10000",
                "splits": {
                    "train": len(train_entries),
                    "validation": len(val_entries),
                    "test": len(test_entries),
                },
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.lr,
                "architecture": "efficientnet_b0 (ImageNet pretrained, fine-tuned)",
                "best_val_accuracy": round(best_val, 4),
                "quick_test_accuracy": round(test_accuracy, 4),
            },
            fh,
            indent=2,
        )

    print("\nNext:")
    print("  1. Update model_registry skin_cancer to torch + efficientnet_b0")
    print("  2. python evaluate.py --disease skin_cancer --data-dir <folder>")


if __name__ == "__main__":
    main()
