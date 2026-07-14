# AMAD — Automated Metallic Anomaly Detector

**Autonomous Spacecraft Hull Inspection & Edge Telemetry Software**

AMAD is a two-stage machine learning pipeline that autonomously detects, classifies, and logs structural faults (cracks, holes, pitting, corrosion) on spacecraft hull surfaces from live video, optimized for low-power edge deployment.

## Overview

Spacecraft hull inspection traditionally requires manual visual review, which is slow, subjective, and doesn't scale to continuous monitoring. AMAD automates this by combining an **unsupervised anomaly filter** with a **supervised defect classifier** in a cascaded pipeline — flagging both known fault types and entirely unseen anomalies in real time, without requiring large labeled datasets of spacecraft damage.

## Key Features

- **Two-stage cascaded detection** — a lightweight normalcy filter gatekeeps a heavier classifier, minimizing compute load
- **Zero-day anomaly detection** — flags never-before-seen structural damage out of the box
- **Edge-optimized inference** — INT8/FP16 quantized models (ONNX/OpenVINO) for CPU-only deployment
- **Real-time async pipeline** — multi-threaded frame capture with automatic stale-frame purging
- **Automated evidence capture** — annotated snapshots saved on every verified detection
- **Structured telemetry export** — Excel/CSV and text logs generated on shutdown
- **GPIO abstraction layer** — decoupled hardware signal integration (LEDs, buzzer, relay) without touching the ML codebase

## System Architecture

### Stage 1 — Unsupervised Normalcy Filter
Uses the **Intel Anomalib** framework (PaDiM / PatchCore backbone) pre-trained on pristine metallic surface textures. Instead of hardcoding defect signatures, it builds a statistical memory map of a "normal" surface and computes a reconstruction anomaly score for each frame. Frames scoring above a calibrated threshold `T` are escalated to Stage 2; everything else is discarded as nominal — keeping this stage extremely cheap to run continuously.

### Stage 2 — Defect Classification & Localization
Escalated frames are sent to a **YOLO model served via Roboflow** for precise bounding-box localization and classification. A strict label whitelist filters out irrelevant detections:

```python
STRICT_METAL_LABELS = ["defect", "crack", "scratch", "hole", "pitting", "damage", "rough_surface", "metal"]
```

### Severity Classification

| Severity | Score Range | Description |
|---|---|---|
| **MODERATE** | `T ≤ score < 0.65` | Superficial oxidation, micro-abrasions, low-contrast roughness |
| **CRITICAL** | `0.65 ≤ score < 0.85` | Deep pitting, severe degradation, distinct scratches |
| **DESTROYED / DAMAGE** | `score ≥ 0.85` | Hull punctures, deep fractures, hypervelocity impact holes |

### Data Pipeline
- Baseline dataset of scratch-free metallic surfaces for normalcy training
- 100-image validation pool sourced from NASA HVIT, the NEU Metal Defect Dataset, and lab-captured deformations
- Augmentation (brightness shift, flips, contrast normalization) expanding the effective dataset to 1,000+ variations
- All frames normalized to 640×640 before inference

## Performance Results (Live Evaluation Run — 28 June 2026)

| Metric | Value |
|---|---|
| Total frames processed | 415 |
| Validated faults detected | 99 |
| Nominal frames | 316 |
| Fault detection rate | 23.86% |
| Average inference latency | 107.7 ms (~9.28 FPS) |
| Stage 2 classifier idle time | 76.14% |
| Memory footprint reduction (quantization) | ~70% |

**Severity breakdown of detected faults:**
- Moderate: 12 frames
- Critical: 28 frames
- Destroyed/Damage: 59 frames

## Why the Cascaded Design Matters

Spacecraft computing platforms run under strict power budgets. By keeping the expensive classifier idle over 76% of the time and only activating it when the cheap Stage 1 filter flags a possible anomaly, AMAD significantly reduces onboard energy consumption — a critical constraint for space-deployed hardware. The unsupervised nature of Stage 1 also solves the "cold start" problem: real spacecraft damage data is scarce, so the system doesn't depend on large labeled fault datasets to catch novel damage types.

## Tech Stack

- **ML/CV:** Intel Anomalib (PaDiM/PatchCore), YOLO, Roboflow Inference API
- **Optimization:** ONNX, OpenVINO, INT8/FP16 quantization
- **Data/Logging:** pandas, openpyxl
- **Runtime:** Python, multi-threaded async processing (`queue.Queue`)
- **Hardware I/O:** GPIO abstraction layer for LED/buzzer/relay signaling

## Output

On shutdown, AMAD exports:
- `Detailed_Inspection_Telemetry.xlsx` — full structured fault log
- `Detailed_Summary.txt` — plain-text run summary
- `/Defect_Snapshots/` — annotated `.jpg` frames for every verified fault (with bounding boxes, class, and confidence score)

## Notes & Limitations

- The classifier was trained primarily on flat hull textures; deep geometric recesses (e.g., thruster nozzles) can currently be misclassified as holes. A production deployment would add a mask layer to whitelist known intentional geometries.
- Validated against both synthetic/lab damage samples and real aerospace imagery (including a Space Shuttle Endeavour hull scan) to confirm generalization beyond the training distribution.

---

*Developed for ISSP 2026.*
