# FDE Daily Work Log (7-Day Task)

## Day 1: Problem Formulation, Data Exploration & Architecture Strategy
- **Exploration:**
  - Inspected Dataset A (`events.jsonl`, `gt_manifest.json`, `gt.jsonl`) and Dataset B.
  - Identified critical domain differences: Dataset A uses Chrome (port 5122) and HR/Finance/Ops internal systems; Dataset B uses Microsoft Edge (ports 5132/5133/5134) with Word/Excel files (`keiyaku_kaijo_tetsuzuki`, `expense_calc`).
  - Recognized that hardcoded rules or application names will fail across departments.
- **Architectural Decision:**
  - Adopted a **Two-Stage Hybrid Pipeline**:
    1. *Stage 1:* Domain-agnostic structural boundary detection (idle gaps, web route transitions, document context switches, and micro-switch smoothing).
    2. *Stage 2:* Unsupervised multilingual representation (TF-IDF + Cosine Agglomerative Clustering) to assign consistent, canonical process labels.

## Day 2: Benchmark Validation on Dataset A Ground Truth
- Implemented `segmenter.py` and `evaluate.py`.
- **First Iteration:**
  - Raw idle + title split resulted in over-segmentation (65 segments predicted vs 28 ground truth executions).
  - Diagnostic: Workers frequently consult auxiliary reference sheets (Excel/Notepad) for 3-10 seconds while working on a portal case. Treating these micro-switches as task boundaries broke single tasks into multiple fragments.
- **Refinement:**
  - Introduced primary portal anchoring and reference-tool smoothing.
  - Achieved **92.9% F1 Score** and **71.4% boundary accuracy** within 15 seconds.

## Day 3: Dataset B Execution & Deliverable Verification
- Merged and processed all 15 sessions in Dataset B.
- Extracted 198 coherent work units.
- Validated via `validate_segments.py`: 100% schema compliance, valid ISO 8601 UTC timestamps, zero inverted intervals.
