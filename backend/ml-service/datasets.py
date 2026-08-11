"""Evaluation dataset adapters.

Each adapter streams labelled test images from an open-access source and maps
the dataset's native label space onto the registry's class list for that
module. Where a mapping is lossy or approximate that fact is recorded on the
adapter and propagated into the metrics file - a mapped evaluation is weaker
evidence than a native one and must not be presented as equivalent.
"""

import io
import json
import random
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from PIL import Image

HF_ROWS = "https://datasets-server.huggingface.co/rows"
USER_AGENT = "mediscan-eval/1.0"


@dataclass
class DatasetSpec:
    key: str
    disease: str
    hf_dataset: str
    split: str
    config: str = "default"
    # native dataset label index -> registry class index (None = drop the row)
    label_map: Dict[int, Optional[int]] = field(default_factory=dict)
    native_labels: List[str] = field(default_factory=list)
    mapping_note: str = ""
    exact_taxonomy: bool = True
    source_url: str = ""
    license_note: str = ""


DATASETS: Dict[str, DatasetSpec] = {
    "diabetic_retinopathy": DatasetSpec(
        key="diabetic_retinopathy",
        disease="diabetic_retinopathy",
        hf_dataset="sngsfydy/aptos_test",
        split="train",
        native_labels=["No DR", "Mild", "Moderate", "Severe", "Proliferative"],
        label_map={0: 0, 1: 1, 2: 2, 3: 3, 4: 4},
        exact_taxonomy=True,
        mapping_note=(
            "APTOS 2019 grades 0-4 map one-to-one onto the model's five DR levels."
        ),
        source_url="https://huggingface.co/datasets/sngsfydy/aptos_test",
        license_note="APTOS 2019 Blindness Detection (public Kaggle competition data).",
    ),
    "knee_osteoarthritis": DatasetSpec(
        key="knee_osteoarthritis",
        disease="knee_osteoarthritis",
        hf_dataset="SilpaCS/kneeosteoarthritis",
        split="train",
        native_labels=["KL-0", "KL-1", "KL-2", "KL-3", "KL-4"],
        # Model emits 3 coarse bands: Normal / Non Severe OA / Severe OA.
        # KL-0 -> Normal, KL-1..2 -> Non Severe, KL-3..4 -> Severe.
        # KL-1 ("doubtful") is genuinely ambiguous between Normal and Non Severe;
        # this is the main source of mapping error.
        label_map={0: 0, 1: 1, 2: 1, 3: 2, 4: 2},
        exact_taxonomy=False,
        mapping_note=(
            "5-point Kellgren-Lawrence grades collapsed into the model's 3 coarse "
            "bands (KL-0 -> Normal, KL-1/2 -> Non Severe OA, KL-3/4 -> Severe OA). "
            "KL-1 'doubtful' is ambiguous between Normal and Non Severe, so some "
            "disagreement reflects the mapping rather than the model."
        ),
        source_url="https://huggingface.co/datasets/SilpaCS/kneeosteoarthritis",
        license_note="Public knee osteoarthritis KL-grading dataset mirror.",
    ),
}

# Brain tumour uses the local Kaggle download's held-out Testing folder rather
# than a streaming source. The path is supplied at eval time via --data-dir.
BRAIN_SPEC = DatasetSpec(
    key="brain_tumor",
    disease="brain_tumor",
    hf_dataset="",
    split="Testing",
    native_labels=["glioma_tumor", "meningioma_tumor", "no_tumor", "pituitary_tumor"],
    exact_taxonomy=True,
    mapping_note="Kaggle download held-out Testing folder. Same source the model was trained on, never seen during training.",
    source_url="https://www.kaggle.com/datasets/sartajbhuvaji/brain-tumor-classification-mri",
    license_note="Kaggle public dataset.",
)

DATASETS["brain_tumor"] = BRAIN_SPEC


HAM_GT_URL = "https://dataverse.harvard.edu/api/access/datafile/6924466"
ISIC_IMAGE_URL = "https://isic-archive.s3.amazonaws.com/images/{isic_id}.jpg"

# HAM10000 dx code -> registry class index for the 3-class skin model.
# The checkpoint only knows BCC / Melanoma / Nevus, so the four remaining
# HAM classes have no corresponding output and are dropped rather than
# force-fitted into a class the model was never trained to represent.
HAM_LABEL_MAP = {
    "bcc": 0,
    "mel": 1,
    "nv": 2,
    "bkl": None,
    "df": None,
    "akiec": None,
    "vasc": None,
}

SKIN_SPEC = DatasetSpec(
    key="skin_cancer",
    disease="skin_cancer",
    hf_dataset="HAM10000 / ISIC2018 Task3 official test set",
    split="test",
    native_labels=["akiec", "bcc", "bkl", "df", "mel", "nv", "vasc"],
    exact_taxonomy=False,
    mapping_note=(
        "HAM10000 official test ground truth. The model covers only 3 of the 7 "
        "classes, so akiec/bkl/df/vasc rows are EXCLUDED from scoring rather than "
        "mapped. Real-world accuracy would be lower, because in deployment those "
        "lesion types still get forced into one of the 3 available classes."
    ),
    source_url="https://doi.org/10.7910/DVN/DBW86T",
    license_note="HAM10000 (CC BY-NC 4.0), ISIC 2018 Task 3 test split.",
)

DATASETS["skin_cancer"] = SKIN_SPEC


def _fetch_json(url: str, retries: int = 4, backoff: float = 2.0) -> dict:
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except Exception as exc:  # transient API/network failures
            last = exc
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def _fetch_bytes(url: str, retries: int = 4, backoff: float = 2.0) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception as exc:
            last = exc
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch image {url}: {last}")


def _ham_ground_truth() -> List[Tuple[str, int]]:
    """Return [(isic_id, mapped_index)] for HAM10000 test rows the model covers."""
    raw = _fetch_bytes(HAM_GT_URL).decode("utf-8", errors="replace")
    entries = []
    for line in raw.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        image_id = parts[1].strip().strip('"')
        dx = parts[2].strip().strip('"').lower()
        mapped = HAM_LABEL_MAP.get(dx)
        if mapped is None or not image_id:
            continue
        entries.append((image_id, mapped))
    return entries


def iter_skin_samples(
    limit: int, stride: int = 1, seed: int = 42
) -> Iterator[Tuple[Image.Image, int]]:
    del stride
    entries = _ham_ground_truth()
    random.Random(seed).shuffle(entries)
    produced = 0
    for image_id, label in entries:
        if produced >= limit:
            break
        try:
            payload = _fetch_bytes(ISIC_IMAGE_URL.format(isic_id=image_id))
            image = Image.open(io.BytesIO(payload)).convert("RGB")
        except Exception:
            continue
        yield image, label
        produced += 1


# Kaggle folder name -> registry class index for brain_tumor.
BRAIN_LABEL_FOLDERS = {
    "glioma_tumor": 0,   # Glioma
    "meningioma_tumor": 1,  # Meningioma
    "no_tumor": 2,       # No Tumor
    "pituitary_tumor": 3,  # Pituitary
}


def iter_brain_samples(data_dir: str, limit: int) -> Iterator[Tuple[Image.Image, int]]:
    """Yield (image, class_index) from the Kaggle download's held-out Testing folder."""
    test_dir = Path(data_dir) / "Testing"
    if not test_dir.exists():
        return
    entries = []
    for folder, label in BRAIN_LABEL_FOLDERS.items():
        folder_path = test_dir / folder
        if not folder_path.exists():
            continue
        for path in folder_path.iterdir():
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                entries.append((path, label))
    random.shuffle(entries)
    produced = 0
    for path, label in entries:
        if produced >= limit:
            break
        try:
            image = Image.open(path).convert("RGB")
        except Exception:
            continue
        yield image, label
        produced += 1


def total_rows(spec: DatasetSpec) -> int:
    url = (
        f"{HF_ROWS}?dataset={urllib.parse.quote(spec.hf_dataset, safe='')}"
        f"&config={spec.config}&split={spec.split}&offset=0&length=1"
    )
    return int(_fetch_json(url)["num_rows_total"])


def iter_samples(
    spec: DatasetSpec,
    limit: int,
    seed: int = 42,
    page_size: int = 100,
    stride: int = 1,
) -> Iterator[Tuple[Image.Image, int]]:
    """Yield (image, mapped_label_index) pairs from randomly chosen rows.

    These datasets are stored grouped by class, so any sequential or fixed-
    stride walk can land entirely inside one label and produce a meaningless
    single-class evaluation. Row indices are therefore drawn uniformly at
    random from the whole split using a fixed seed, which keeps the sample
    representative and the run reproducible. `stride` is accepted for
    interface compatibility and ignored.
    """
    del stride

    total = total_rows(spec)
    rng = random.Random(seed)

    # Oversample indices: some rows map to None or fail to download.
    budget = min(total, max(limit * 4, limit + 64))
    indices = rng.sample(range(total), budget)

    produced = 0
    for start in range(0, len(indices), page_size):
        if produced >= limit:
            break
        for row_index in sorted(indices[start : start + page_size]):
            if produced >= limit:
                break
            url = (
                f"{HF_ROWS}?dataset={urllib.parse.quote(spec.hf_dataset, safe='')}"
                f"&config={spec.config}&split={spec.split}"
                f"&offset={row_index}&length=1"
            )
            try:
                payload = _fetch_json(url)
            except RuntimeError:
                continue
            rows = payload.get("rows", [])
            if not rows:
                continue

            row = rows[0]["row"]
            mapped = spec.label_map.get(int(row["label"]))
            if mapped is None:
                continue

            src = row["image"]
            src_url = src["src"] if isinstance(src, dict) else src
            try:
                image = Image.open(io.BytesIO(_fetch_bytes(src_url))).convert("RGB")
            except Exception:
                continue

            yield image, mapped
            produced += 1
