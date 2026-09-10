import os
import sys
import json
from datetime import datetime
from collections import Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_FILE = os.path.join(REPO_ROOT, "segments.jsonl")
DATASET_B_DIR = os.path.join(REPO_ROOT, "data", "dataset_b")

def validate():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("Validating Deliverable: segments.jsonl")
    print("=" * 60)

    if not os.path.exists(OUTPUT_FILE):
        print(f"ERROR: {OUTPUT_FILE} does not exist.")
        sys.exit(1)

    required_keys = {"session_id", "start", "end", "label"}
    sessions_seen = set()
    label_counter = Counter()
    total_duration_sec = 0.0
    line_count = 0
    errors = []

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                record = json.loads(line)
            except Exception as e:
                errors.append(f"Line {idx}: Invalid JSON syntax: {e}")
                continue

            # Check required keys
            missing = required_keys - set(record.keys())
            if missing:
                errors.append(f"Line {idx}: Missing fields: {missing}")

            # Check session_id
            sid = record.get("session_id", "")
            if not sid.startswith("ses_"):
                errors.append(f"Line {idx}: Unusual session_id format: '{sid}'")
            sessions_seen.add(sid)

            # Check start and end timestamps
            st_str = record.get("start", "")
            et_str = record.get("end", "")
            
            try:
                st = datetime.fromisoformat(st_str.replace("Z", "+00:00"))
                et = datetime.fromisoformat(et_str.replace("Z", "+00:00"))
                
                if et < st:
                    errors.append(f"Line {idx}: End timestamp {et_str} is before Start {st_str}")
                
                duration = (et - st).total_seconds()
                total_duration_sec += duration
            except Exception as e:
                errors.append(f"Line {idx}: Malformed timestamp: {e}")

            # Check label
            lbl = record.get("label", "")
            if not lbl:
                errors.append(f"Line {idx}: Empty label")
            label_counter[lbl] += 1

    print(f"Total Segments Parsed: {line_count}")
    print(f"Total Unique Sessions Covered: {len(sessions_seen)} / 15")

    print(f"Average Segment Duration: {total_duration_sec / max(1, line_count):.1f} seconds")
    print(f"Total Time Accounted For: {total_duration_sec / 3600.0:.2f} hours")

    print("\nUnique Business Process Labels Identified:")
    for lbl, count in label_counter.most_common():
        print(f"  - {lbl:<35}: {count:>3} segments")

    if errors:
        print(f"\nFAILED: Found {len(errors)} validation errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nSUCCESS: All schema and consistency checks passed perfectly!")

if __name__ == "__main__":
    validate()
