# OCR Decision Model

The intent-aware planner converts page-level signals into a calibrated OCR decision. It does **not** aim to detect scanned vs digital PDFs. It aims to decide **whether OCR is necessary for reliable downstream extraction**. You are not classifying PDF types; you are optimizing downstream correctness.

## Domain Mode / Override Policy

Scope the decision layer to your use case via `domain_mode` or `override_policy`:

| domain_mode | override_policy   | Failsafe | Intent override |
|-------------|-------------------|----------|-----------------|
| `medical`   | `medical_strict`   | Yes      | Yes             |
| `generic`   | `failsafe_only`   | Yes      | No              |

Or set `override_policy` explicitly: `none` (scoring only), `failsafe_only`, `medical_strict`.

- **Medical pipelines:** Use `domain_mode="medical"` – intent overrides justified; intent contributes to scoring.
- **Generic/academic PDFs:** Use `domain_mode="generic"` – scoring only, no intent override, **intent weight = 0** (intent is domain-specific signal; in generic mode it is effectively off). Uses a higher balanced threshold (0.65) for precision.

## Terminal Overrides

When active per policy, the following conditions **always** trigger OCR (no subsequent logic may reverse):

1. **Extraction failure** – text extraction failed for the page
2. **Layout detection failure** – layout analysis was requested but no layout data for the page
3. **High-confidence OCR-critical intent** – page classified as prescription, diagnosis, chief_complaint, discharge_summary, or lab_report with score ≥ `intent_high_threshold`

**Decision invariant:** Once a terminal override fires, no subsequent logic may reverse the decision.

## Scoring Model

For non-overridden pages:

```
OCR_score = f(intent, image_coverage, text_weakness, extraction_risk)
```

The page is marked `needs_ocr=True` if:

```
OCR_score ≥ decision_threshold
```

### Signals Used

- **Intent confidence** – medical/business criticality from `classify_medical_intent`
- **Image coverage** – percentage of page covered by images (0–100)
- **Text coverage** – percentage of page covered by text (0–100)
- **Extraction risk** – very low text, abnormal entropy, replacement characters

## Decision Modes

| Mode      | Threshold (medical) | Threshold (generic) | Effect                    |
| --------- | ------------------- | ------------------- | ------------------------- |
| `safety`  | ~0.45               | ~0.45               | Lower threshold, favor recall |
| `balanced`| ~0.6                | ~0.65               | F1-optimized; generic uses higher threshold (less signal) |
| `cost`    | ~0.75               | ~0.75               | Higher threshold, reduce OCR usage |

Lower threshold → higher recall (fewer missed OCR). Higher threshold → lower OCR cost.

## Calibration

Thresholds are calibrated using a labeled validation set with page-level ground truth.

- **Primary metric:** F1 score on `needs_ocr=True`
- **Secondary:** Recall (minimize missed OCR), OCR cost rate (% pages sent to OCR)
- **Threshold sweep:** For thresholds in [0.4, 0.5, 0.6, 0.7, 0.8], compute precision, recall, F1; pick operating point by mode

Use `scripts/evaluate_planner.py` for threshold sweep and evaluation.

## Confidence

`confidence` represents the **estimated correctness of the decision** (need vs no-need for OCR). It is **not** OCR accuracy or text recognition quality.

| decision_type | Formula |
| ------------- | ------- |
| terminal_override (failsafe) | `0.65` fixed |
| terminal_override (intent_critical) | `intent_score` |
| scored | `margin = abs(score - threshold)`; `confidence = clamp(0.5 + margin, 0, 1)` |

## Debug Schema

Each page exposes:

```json
{
  "score": 0.72,
  "components": {
    "intent": 0.36,
    "image_dominance": 0.21,
    "text_weakness": 0.15,
    "failsafe_boost": 0.0
  },
  "terminal_override": false
}
```

When `terminal_override` is true, `override_reason` is `"failsafe"` or `"intent_critical"`.

## Configuration

- `decision_threshold` – primary knob; varies by mode and domain. Generic mode uses `decision_threshold_balanced_generic` (0.65) for balanced; medical uses 0.6.
- `intent_high_threshold` – score above which OCR-critical intent triggers override (default 0.7)
- Scoring weights – `get_intent_weight()` returns 0 in generic mode, else `intent_weight`; image_dominance and text_weakness apply in both modes.

### Fast-path

When `fast_path_image_coverage_threshold` > 0: if preocr says no OCR and all pages have image coverage below the threshold, the planner skips intent classification and scoring. Returns preocr decision with `decision_type="fast_path"`. Speeds up clearly digital PDFs.

- Default: 10%. Set to 0 to disable.

See `preocr.planner.config.PlannerConfig` for all options.
