import json
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple

class Event:
    __slots__ = ('ts_ms', 'ts_iso', 'event_type', 'layer', 'app_name', 'window_title', 'url', 'tab_title', 'raw_text')

    def __init__(self, d: Dict[str, Any]):
        self.ts_ms = d.get('timestamp_ms', 0)
        self.ts_iso = d.get('timestamp_iso', '')
        self.event_type = d.get('event_type', '')
        self.layer = d.get('layer', '')
        
        ctx = d.get('context', {}) or {}
        app = ctx.get('active_app', {}) or {}
        self.app_name = app.get('app_name') or ''
        self.window_title = app.get('window_title') or ''
        
        tab = ctx.get('active_browser_tab', {}) or {}
        self.url = tab.get('url') or ''
        self.tab_title = tab.get('title') or ''
        
        self.raw_text = ctx.get('extracted_text') or ''

class Segment:
    def __init__(self, session_id: str, start_iso: str, end_iso: str, start_ms: int, end_ms: int, events: List[Event]):
        self.session_id = session_id
        self.start_iso = start_iso
        self.end_iso = end_iso
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.events = events
        self.label = ""

        # Compute summary signatures
        self.duration_sec = max(1.0, (end_ms - start_ms) / 1000.0)
        
        # Collect apps, titles, URLs
        apps = [e.app_name for e in events if e.app_name]
        titles = [e.window_title for e in events if e.window_title]
        urls = [e.url for e in events if e.url]
        
        self.primary_app = max(set(apps), key=apps.count) if apps else "Unknown"
        self.primary_title = max(set(titles), key=titles.count) if titles else ""
        self.primary_url = max(set(urls), key=urls.count) if urls else ""

    def get_text_signature(self) -> str:
        """Returns consolidated tokens representing the work content in this segment."""
        tokens = []
        if self.primary_app:
            tokens.append(self.primary_app)
        
        # Extract meaningful parts from URL
        for e in self.events:
            if e.url:
                # e.g., extract route from http://127.0.0.1:5133/#/payroll-items -> payroll-items
                route = re.sub(r'https?://[^/]+/?', '', e.url)
                route = route.replace('#/', '').replace('#', '')
                if route and route not in tokens:
                    tokens.append(route)

        # Extract title keywords
        seen_titles = set()
        for e in self.events:
            t = e.window_title
            if t and t not in seen_titles:
                seen_titles.add(t)
                # Clean generic browser/word suffixes
                cleaned = re.sub(r' - Google Chrome| - Microsoft.? Edge| - Word| - Excel| \[Compatibility Mode\]| and \d+ more page.*', '', t)
                tokens.append(cleaned.strip())

        return " ".join(tokens)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start": self.start_iso,
            "end": self.end_iso,
            "label": self.label
        }

class HybridSegmenter:
    def __init__(self, idle_gap_sec: float = 25.0, min_segment_sec: float = 12.0):
        self.idle_gap_ms = int(idle_gap_sec * 1000)
        self.min_segment_ms = int(min_segment_sec * 1000)

    def _extract_url_route(self, url: str) -> str:
        if not url:
            return ""
        # Match hash routes like #/payroll-items or path
        m = re.search(r'#(/[a-zA-Z0-9\-_]+)', url)
        if m:
            return m.group(1)
        m2 = re.search(r':\d+(/[^?#]*)', url)
        if m2 and len(m2.group(1)) > 1:
            return m2.group(1)
        return ""

    def _get_app_role(self, app_name: str, window_title: str) -> str:
        """Classify if an app is a primary business portal vs a reference/auxiliary tool."""
        # Browser with internal portal is primary
        if any(b in app_name for b in ['Chrome', 'Edge']) and any(p in window_title for p in ['システム', 'Portal', '5122', '5132', '5133', '5134', 'Procmine', 'Profile']):
            return "primary_portal"
        # Background agent or terminal
        if any(a in app_name for a in ['WindowsTerminal', 'ProcMine', 'Explorer']):
            return "system_tool"
        # Reference docs (Excel, Word, Notepad)
        return "auxiliary"

    def segment_events(self, session_id: str, events: List[Event]) -> List[Segment]:
        if not events:
            return []

        # Sort events by timestamp_ms
        events.sort(key=lambda x: x.ts_ms)

        cut_points = [0]
        
        last_primary_route = ""
        last_primary_title = ""
        
        for i in range(1, len(events)):
            curr = events[i]
            prev = events[i - 1]
            time_diff = curr.ts_ms - prev.ts_ms
            
            curr_route = self._extract_url_route(curr.url)
            curr_role = self._get_app_role(curr.app_name, curr.window_title)
            
            is_boundary = False

            # Signal 1: Significant idle time between tasks
            if time_diff >= self.idle_gap_ms:
                is_boundary = True

            # Signal 2: Route change in portal (e.g. from /payroll to /leave-applications)
            if curr_role == "primary_portal" and curr_route:
                if last_primary_route and curr_route != last_primary_route:
                    is_boundary = True
                last_primary_route = curr_route

            # Signal 3: Major primary window change (e.g., between different portals or standalone docs)
            if curr_role == "primary_portal":
                # Clean window title
                clean_title = re.sub(r' - (?:Google Chrome|Microsoft.? Edge).*', '', curr.window_title).strip()
                clean_title = re.sub(r' and \d+ more page.*', '', clean_title).strip()
                if clean_title and last_primary_title and clean_title != last_primary_title:
                    # If switching between HR and Finance and Inventory systems
                    is_boundary = True
                if clean_title:
                    last_primary_title = clean_title

            if is_boundary:
                seg_start_idx = cut_points[-1]
                duration = events[i - 1].ts_ms - events[seg_start_idx].ts_ms
                if duration >= self.min_segment_ms:
                    cut_points.append(i)

        cut_points.append(len(events))

        # Build raw segments
        raw_segments = []
        for j in range(len(cut_points) - 1):
            s_idx = cut_points[j]
            e_idx = cut_points[j + 1]
            seg_evs = events[s_idx:e_idx]
            if not seg_evs:
                continue

            seg = Segment(
                session_id=session_id,
                start_iso=seg_evs[0].ts_iso,
                end_iso=seg_evs[-1].ts_iso,
                start_ms=seg_evs[0].ts_ms,
                end_ms=seg_evs[-1].ts_ms,
                events=seg_evs
            )
            raw_segments.append(seg)

        # Post-processing: Merge very short fragments (< min_segment_ms) into adjacent segments
        merged = []
        for seg in raw_segments:
            if not merged:
                merged.append(seg)
                continue

            if seg.duration_sec < (self.min_segment_ms / 1000.0):
                # Merge into previous
                merged[-1].events.extend(seg.events)
                merged[-1].end_ms = seg.end_ms
                merged[-1].end_iso = seg.end_iso
                merged[-1].duration_sec = (merged[-1].end_ms - merged[-1].start_ms) / 1000.0
            else:
                merged.append(seg)

        return merged

    def load_events_from_file(self, filepath: str) -> List[Event]:
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        d = json.loads(line)
                        events.append(Event(d))
                    except Exception:
                        pass
        return events
