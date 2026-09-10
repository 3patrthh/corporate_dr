import os
import re
import json
import urllib.request
import time

BASE_DIR = r"."
DATASET_B_DIR = os.path.join(BASE_DIR, "data", "dataset_b")
os.makedirs(DATASET_B_DIR, exist_ok=True)

# Load subfolders_items.json to get Dataset B session folder IDs
with open(os.path.join(BASE_DIR, "scratch", "subfolders_items.json"), "r", encoding="utf-8") as f:
    drive_data = json.load(f)

dataset_b_sessions = drive_data["dataset_b"]
print(f"Total Dataset B sessions to process: {len(dataset_b_sessions)}")

def fetch_folder_items(folder_id):
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        match = re.search(r"window\['_DRIVE_ivd'\]\s*=\s*'((?:[^'\\]|\\.)*)';", html)
        if match:
            raw_str = match.group(1)
            decoded_str = raw_str.encode("utf-8").decode("unicode_escape")
            data = json.loads(decoded_str)
            items = data[0] if len(data) > 0 else []
            items_info = []
            for it in items:
                if isinstance(it, list) and len(it) > 3:
                    items_info.append({
                        "id": it[0],
                        "name": it[2],
                        "mime": it[3],
                        "size": it[14] if len(it) > 14 else None
                    })
            return items_info
    return []

for idx, session in enumerate(dataset_b_sessions, 1):
    sname = session["name"]
    sid = session["id"]
    sdir = os.path.join(DATASET_B_DIR, sname)
    os.makedirs(sdir, exist_ok=True)
    
    print(f"\n[{idx}/{len(dataset_b_sessions)}] Checking session: {sname} (ID: {sid})")
    
    # Check if already processed
    merged_events = os.path.join(sdir, "events.jsonl")
    if os.path.exists(merged_events) and os.path.getsize(merged_events) > 1000:
        print(f"  -> Already downloaded ({os.path.getsize(merged_events)} bytes). Skipping.")
        continue

    # Fetch chunk folders in session
    items = fetch_folder_items(sid)
    chunk_folders = [it for it in items if it["mime"] == "application/vnd.google-apps.folder" and it["name"].startswith("chunk_")]
    
    # Sort chunks chronologically by chunk name
    chunk_folders.sort(key=lambda x: x["name"])
    print(f"  Found {len(chunk_folders)} chunk(s): {[c['name'] for c in chunk_folders]}")
    
    # Download events.jsonl from each chunk and merge chronologically
    with open(merged_events, "w", encoding="utf-8") as out_f:
        for chunk in chunk_folders:
            citems = fetch_folder_items(chunk["id"])
            event_item = next((it for it in citems if it["name"] == "events.jsonl"), None)
            if event_item:
                print(f"    Downloading {chunk['name']}/events.jsonl...")
                dl_url = f"https://drive.google.com/uc?export=download&id={event_item['id']}"
                req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    chunk_content = resp.read().decode("utf-8", errors="ignore")
                    out_f.write(chunk_content)
                    if not chunk_content.endswith("\n"):
                        out_f.write("\n")
                print(f"    Appended chunk {chunk['name']} ({len(chunk_content)} chars)")
            time.sleep(0.5)

    print(f"  Session complete: {merged_events} ({os.path.getsize(merged_events)} bytes)")

print("\nAll Dataset B sessions downloaded and prepared successfully!")
