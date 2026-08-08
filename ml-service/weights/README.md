# Model weights

Large binaries are gitignored. Fetch them with `python fetch_weights.py`.

## Installed modules

| Module | File | Framework | Classes | Source |
|---|---|---|---|---|
| Knee Osteoarthritis | `knee_osteoarthritis.pth` | PyTorch | 3 | [shaina-12](https://github.com/shaina-12/Knee-Ostheoarthritis-Detection-and-Severity-Prediction) |
| Skin Cancer | `skin_cancer.h5` | Keras (legacy) | 3 | [sid321axn](https://github.com/sid321axn/skin_cancer_detection_webapp) |
| Diabetic Retinopathy | `diabetic_retinopathy.h5` | Keras (legacy) | 5 | [Akshar106](https://github.com/Akshar106/Diabetic-Retinopathy-Blindness-Detection-and-Staging) |
| Heart Disease (tabular) | `heart_disease_model.joblib` | scikit-learn | 2 | retrained from `heart.csv` |
| Brain Tumor | *(missing)* | PyTorch | 4 | upstream ships a notebook only |

## Accuracy claims: read this before the demo

**No accuracy figure is quoted for the three image modules.** The upstream
repositories publish accuracy numbers, but none of them were reproduced on a
held-out test set here, so quoting them would be repeating an unverified claim.
Each module reports a `provenance` string through `/diseases` saying exactly
this. To make a real claim, evaluate on a held-out split and write
`weights/<key>.metrics.json`.

Known taxonomy limits, surfaced in the API rather than hidden:

- **Knee OA** outputs a coarse 3-way band (`Normal` / `Non Severe OA` /
  `Severe OA`). It is *not* the 5-point Kellgren-Lawrence scale the project
  report originally described.
- **Skin Cancer** covers 3 classes only, not the full HAM10000 7-class
  taxonomy. Lesion types outside those 3 will be forced into the nearest class.
- **Diabetic Retinopathy** uses an ordinal sigmoid head decoded at the upstream
  threshold `0.3776`; scores are per-level sigmoids, not a softmax
  distribution. The API labels this via `score_semantics`.

### Heart disease is the one module with measured metrics

The upstream `RandomForestClassifier.pkl` was built on scikit-learn 1.0.1 and
**cannot be unpickled** on modern scikit-learn (incompatible tree node dtype),
so it is not used. `train_heart_model.py` retrains the same model type on the
same public `heart.csv`.

That dataset has **723 duplicate rows out of 1025**. Splitting it naively leaks
near-identical rows into the test set and reports ~99% accuracy. After
de-duplication the honest held-out accuracy is **~82%** (ROC-AUC 0.88). Both
numbers are recorded in `heart_disease.metrics.json`; quote only `held_out`.

## Adding the brain tumor model

Train a `torchvision.models.resnet18` with a 4-output `fc` layer and save the
`state_dict` as `weights/brain_tumor.pth`. Until then the module reports
`model_status: "UNTRAINED_BACKBONE"`, returns
`"Not Clinically Valid - Untrained Model"`, is never conclusive, and prints a
warning banner in the PDF.

Optional metrics sidecar, surfaced by the API:

```json
{
  "accuracy": 0.00, "precision": 0.00, "recall": 0.00, "f1": 0.00,
  "test_set": "held-out 15% stratified split",
  "trained_on": "Kaggle Brain Tumor MRI Dataset"
}
```

Never claim measured accuracy for a module whose status is not `TRAINED`.
