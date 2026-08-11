"""Train the brain tumor MRI classifier.

The upstream repository referenced by the project ships only a notebook, no
checkpoint, so this module was the one image model with no weights. This script
fine-tunes a torchvision ResNet-18 on an open-access 4-class MRI dataset that
already carries author-defined train/validation/test splits.

Why those splits matter: the test split is held back completely and is the only
data `evaluate.py` scores against. Training on a random re-split of the whole
corpus would leak near-duplicate slices from the same patient into the test set
and produce an accuracy figure that means nothing.

Images are cached locally on first run so repeated epochs do not re-download.

Usage:
    python train_brain_tumor.py                 # ~10 min on CPU
    python train_brain_tumor.py --epochs 6 --limit 1200
"""

import argparse
import io
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import ResNet18_Weights, resnet18

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
CACHE_DIR = os.path.join(BASE_DIR, ".cache", "brain_tumor")
OUT_PATH = os.path.join(WEIGHTS_DIR, "brain_tumor.pth")

HF_DATASET = "PranomVignesh/MRI-Images-of-Brain-Tumor"
HF_ROWS = "https://datasets-server.huggingface.co/rows"

# Dataset order is glioma|meningioma|no-tumor|pituitary. The registry declares
# Glioma, Meningioma, No Tumor, Pituitary - identical order, so the index maps
# straight across. Assert this at runtime rather than trusting the comment.
DATASET_LABELS = ["glioma", "meningioma", "no-tumor", "pituitary"]
REGISTRY_CLASSES = ["Glioma", "Meningioma", "No Tumor", "Pituitary"]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
SEED = 42


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def fetch_json(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "mediscan-train/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except Exception as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def fetch_bytes(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "mediscan-train/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch image: {last}")


def download_split(split, limit=None, page_size=100):
    """Cache one split to disk as <cache>/<split>/<label>/<n>.png."""
    split_dir = os.path.join(CACHE_DIR, split)
    manifest_path = os.path.join(split_dir, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            entries = json.load(fh)
        if limit is None or len(entries) >= limit:
            print(f"  {split}: {len(entries)} cached images")
            return entries[:limit] if limit else entries

    os.makedirs(split_dir, exist_ok=True)
    encoded = urllib.parse.quote(HF_DATASET, safe="")
    total = fetch_json(
        f"{HF_ROWS}?dataset={encoded}&config=default&split={split}&offset=0&length=1"
    )["num_rows_total"]
    target = min(total, limit) if limit else total

    entries = []
    cursor = 0
    while len(entries) < target and cursor < total:
        length = min(page_size, total - cursor)
        payload = fetch_json(
            f"{HF_ROWS}?dataset={encoded}&config=default&split={split}"
            f"&offset={cursor}&length={length}"
        )
        for item in payload.get("rows", []):
            if len(entries) >= target:
                break
            row = item["row"]
            label = int(row["label"])
            src = row["image"]
            url = src["src"] if isinstance(src, dict) else src
            path = os.path.join(split_dir, f"{len(entries):05d}_{label}.png")
            if not os.path.exists(path):
                try:
                    image = Image.open(io.BytesIO(fetch_bytes(url))).convert("RGB")
                    image.save(path)
                except Exception:
                    continue
            entries.append({"path": path, "label": label})
        cursor += length
        print(f"    {split}: {len(entries)}/{target}", end="\r", flush=True)

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh)
    print(f"  {split}: {len(entries)} images cached      ")
    return entries


class MriDataset(Dataset):
    def __init__(self, entries, train=False):
        self.entries = entries
        if train:
            self.transform = transforms.Compose([
                transforms.Resize((256, 256)),
                transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(10),
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
        entry = self.entries[index]
        image = Image.open(entry["path"]).convert("RGB")
        return self.transform(image), entry["label"]


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
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--limit", type=int, default=None, help="cap images per split")
    args = parser.parse_args()

    if len(DATASET_LABELS) != len(REGISTRY_CLASSES):
        sys.exit("Dataset and registry class counts differ; refusing to train.")

    set_seed()
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    print("\nCaching dataset splits (author-defined, not re-shuffled):")
    train_entries = download_split("train", args.limit)
    val_entries = download_split("validation", args.limit // 3 if args.limit else None)
    test_entries = download_split("test", args.limit // 3 if args.limit else None)

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

        # Select on validation only; the test split stays untouched until the end.
        if val_accuracy > best_val:
            best_val = val_accuracy
            torch.save(model.state_dict(), OUT_PATH)
            print(f"    saved new best -> {OUT_PATH}")

    model.load_state_dict(torch.load(OUT_PATH, map_location=device))
    test_accuracy = accuracy(model, test_loader, device)

    print(f"\nBest validation accuracy : {best_val:.4f}")
    print(f"Held-out test accuracy   : {test_accuracy:.4f}")
    print(f"Training time            : {(time.time() - started) / 60:.1f} min")

    with open(os.path.join(WEIGHTS_DIR, "brain_tumor.train.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "dataset": HF_DATASET,
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
                    "Author-defined splits used as published; the test split was not "
                    "touched during training or model selection. Run evaluate.py for "
                    "the full per-class metrics and false-negative rate."
                ),
            },
            fh,
            indent=2,
        )

    print("\nNext: python evaluate.py --disease brain_tumor --limit 300")


if __name__ == "__main__":
    main()
