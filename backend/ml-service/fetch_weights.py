"""Download the third-party model checkpoints used by MediScan AI.

Weights are gitignored because of their size, so this script reproduces the
`weights/` directory from the original public repositories.

Usage:
    python fetch_weights.py
    python fetch_weights.py --force
"""

import argparse
import hashlib
import os
import sys
import urllib.request

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")

ARTIFACTS = [
    {
        "name": "knee_osteoarthritis.pth",
        "url": "https://raw.githubusercontent.com/shaina-12/Knee-Ostheoarthritis-Detection-and-Severity-Prediction/main/Model%20Version3.pth",
        "magic": b"PK\x03\x04",
    },
    {
        "name": "skin_cancer.h5",
        "url": "https://raw.githubusercontent.com/sid321axn/skin_cancer_detection_webapp/master/models/model_v1.h5",
        "magic": b"\x89HDF",
    },
    {
        "name": "diabetic_retinopathy.h5",
        "url": "https://raw.githubusercontent.com/Akshar106/Diabetic-Retinopathy-Blindness-Detection-and-Staging/main/model/dr.h5",
        "magic": b"\x89HDF",
    },
    {
        "name": "heart.csv",
        "url": "https://raw.githubusercontent.com/nilaymodak/HeartDiseasePrediction/main/heart.csv",
        "magic": b"age,",
    },
]


def download(entry: dict, force: bool) -> bool:
    target = os.path.join(WEIGHTS_DIR, entry["name"])
    if os.path.exists(target) and not force:
        print(f"  skip     {entry['name']} (already present)")
        return True

    print(f"  fetching {entry['name']} ...", end="", flush=True)
    try:
        with urllib.request.urlopen(entry["url"], timeout=900) as response:
            payload = response.read()
    except Exception as exc:
        print(f" FAILED ({exc})")
        return False

    if not payload.startswith(entry["magic"]):
        print(f" FAILED (unexpected content, got {payload[:8]!r})")
        return False

    with open(target, "wb") as fh:
        fh.write(payload)

    digest = hashlib.sha256(payload).hexdigest()
    print(f" ok  {len(payload) / 1e6:.1f} MB  sha256={digest[:16]}...")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    print(f"Downloading model artifacts into {WEIGHTS_DIR}")

    failures = [entry["name"] for entry in ARTIFACTS if not download(entry, args.force)]

    if failures:
        print(f"\nFailed: {', '.join(failures)}")
        return 1

    print("\nAll artifacts present.")
    print("Next: python train_heart_model.py   (builds the tabular heart model)")
    print("Note: weights/brain_tumor.pth is NOT available upstream and must be trained locally.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
