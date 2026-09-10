# Operations Log Mining & Automation Pipeline

This repository contains the implementation, analysis, and deliverables for the **Forward Deployed Engineer (FDE) Selection Task: From Operation Logs to an Automation Proposal**.

## Repository Structure

```text
.
├── README.md               <- Project documentation & reproduction guide
├── requirements.txt        <- Python dependencies
├── segments.jsonl          <- Deliverable 1: Recovered units of work for Dataset B
├── src/
│   ├── __init__.py
│   ├── segmenter.py        <- Stage 1: Domain-agnostic structural boundary detector
│   ├── clusterer.py        <- Stage 2: Multilingual TF-IDF & Agglomerative clustering
│   ├── evaluate.py         <- Evaluation engine against Dataset A ground truth
│   ├── generate_segments.py<- Production pipeline for Dataset B
│   ├── validate_segments.py<- Strict deliverable verification
│   └── fetch_dataset_b.py  <- Data synchronization script
└── docs/
    ├── work_log.md         <- Deliverable 4: Daily thought process, trials, and trade-offs
    └── final_report.md     <- Deliverable 3: Final proposal & ROI analysis
```

## Getting Started

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Verify Output
```bash
python src/validate_segments.py
```

### 3. Reproduce Segmentation Pipeline
```bash
python src/generate_segments.py
```

## Step 1 Results Summary
* **Benchmark Accuracy (Dataset A Ground Truth):**
  - **F1 Score:** 92.9%
  - **Boundary Precision (±15s window):** 71.4%
  - **Temporal Recall (IoU > 0.3):** 67.9%
* **Dataset B Production Metrics:**
  - **Sessions Covered:** 15 / 15 (100%)
  - **Total Work Units Recovered:** 198 segments
  - **Average Duration:** 51.2 seconds
