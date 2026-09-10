import os
import sys
import json
from datetime import datetime
from typing import List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from src.segmenter import HybridSegmenter, Segment
from src.clusterer import SegmentClusterer

DATASET_B_DIR = os.path.join(REPO_ROOT, "data", "dataset_b")
OUTPUT_FILE = os.path.join(REPO_ROOT, "segments.jsonl")

def format_iso_utc(iso_str: str) -> str:
    if not iso_str:
        return ""
    cleaned = iso_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        if not iso_str.endswith("Z"):
            return iso_str + "Z"
        return iso_str

def run():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("Starting Step 1: Hybrid Segmentation on Dataset B")
    print("=" * 60)

    segmenter = HybridSegmenter(idle_gap_sec=20.0, min_segment_sec=8.0)
    clusterer = SegmentClusterer(distance_threshold=0.50)

    session_dirs = [os.path.join(DATASET_B_DIR, d) for d in os.listdir(DATASET_B_DIR) if os.path.isdir(os.path.join(DATASET_B_DIR, d))]
    session_dirs.sort()
    print(f"Found {len(session_dirs)} sessions in Dataset B.")

    all_segments: List[Segment] = []

    for sdir in session_dirs:
        sname = os.path.basename(sdir)
        events_file = os.path.join(sdir, "events.jsonl")
        if not os.path.exists(events_file):
            continue

        events = segmenter.load_events_from_file(events_file)
        session_segments = segmenter.segment_events(sname, events)
        all_segments.extend(session_segments)

    print(f"Total candidate segments across all sessions: {len(all_segments)}")
    all_segments = clusterer.fit_predict(all_segments)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for s in all_segments:
            record = {
                "session_id": s.session_id,
                "start": format_iso_utc(s.start_iso),
                "end": format_iso_utc(s.end_iso),
                "label": s.label
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Successfully generated {OUTPUT_FILE} with {len(all_segments)} lines!")

if __name__ == "__main__":
    run()
