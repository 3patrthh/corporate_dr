import json
import os
import sys

sys.path.insert(0, r".")

from datetime import datetime
from typing import List, Dict, Any

from src.segmenter import HybridSegmenter, Segment
from src.clusterer import SegmentClusterer

def parse_iso(iso_str: str) -> float:
    # Convert ISO 8601 to epoch timestamp
    if not iso_str:
        return 0.0
    # Clean Z or +00:00
    cleaned = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    return dt.timestamp()

def evaluate_session(session_dir: str, segmenter: HybridSegmenter, clusterer: SegmentClusterer) -> Dict[str, Any]:
    gt_manifest_file = os.path.join(session_dir, "gt_manifest.json")
    if not os.path.exists(gt_manifest_file):
        raise FileNotFoundError(f"Missing gt_manifest.json in {session_dir}")

    with open(gt_manifest_file, "r", encoding="utf-8") as f:
        gt_manifest = json.load(f)

    # Extract GT intervals
    gt_executions = []
    for proc in gt_manifest.get("processes", []):
        pcode = proc.get("code")
        pname = proc.get("family_name")
        for ex in proc.get("executions", []):
            st = parse_iso(ex.get("start_ts"))
            et = parse_iso(ex.get("end_ts"))
            if st > 0 and et > 0 and et >= st:
                gt_executions.append({
                    "code": pcode,
                    "name": pname,
                    "start": st,
                    "end": et,
                    "duration": et - st
                })

    # Find events.jsonl
    events_files = []
    for root, _, files in os.walk(session_dir):
        if "events.jsonl" in files and "gt.jsonl" not in root:
            events_files.append(os.path.join(root, "events.jsonl"))

    all_events = []
    for ef in events_files:
        all_events.extend(segmenter.load_events_from_file(ef))

    sname = os.path.basename(session_dir)
    pred_segments = segmenter.segment_events(sname, all_events)
    pred_segments = clusterer.fit_predict(pred_segments)

    # Metric evaluation
    # For each GT execution, find best matching predicted segment by IoU
    matches = []
    ious = []
    time_tolerances = [5.0, 15.0, 30.0]
    boundary_hits = {tol: 0 for tol in time_tolerances}

    for gt in gt_executions:
        best_iou = 0.0
        best_pred = None
        for pred in pred_segments:
            pst = parse_iso(pred.start_iso)
            pet = parse_iso(pred.end_iso)
            
            inter = max(0.0, min(gt["end"], pet) - max(gt["start"], pst))
            union = max(gt["end"], pet) - min(gt["start"], pst)
            iou = inter / union if union > 0 else 0.0

            if iou > best_iou:
                best_iou = iou
                best_pred = pred

        ious.append(best_iou)
        if best_pred:
            pst = parse_iso(best_pred.start_iso)
            for tol in time_tolerances:
                if abs(gt["start"] - pst) <= tol:
                    boundary_hits[tol] += 1

    mean_iou = sum(ious) / len(ious) if ious else 0.0
    prec = len(ious) / len(pred_segments) if pred_segments else 0.0
    rec = sum(1 for i in ious if i > 0.3) / len(gt_executions) if gt_executions else 0.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return {
        "session": sname,
        "gt_count": len(gt_executions),
        "pred_count": len(pred_segments),
        "mean_iou": mean_iou,
        "boundary_hits_15s": boundary_hits[15.0],
        "boundary_accuracy_15s": boundary_hits[15.0] / len(gt_executions) if gt_executions else 0.0,
        "recall_iou30": rec,
        "f1_score": f1,
        "labels": list(set(s.label for s in pred_segments))
    }

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    sample_dir = r".\scratch\sample_session"
    seg = HybridSegmenter(idle_gap_sec=18.0, min_segment_sec=8.0)
    clust = SegmentClusterer(distance_threshold=0.5)
    res = evaluate_session(sample_dir, seg, clust)
    print("Evaluation Results on Dataset A Sample Session:")
    for k, v in res.items():
        print(f"  {k}: {v}")
