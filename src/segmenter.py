import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

SYSTEM_NOISE_APPS = {
    'procmine-desktop-agent',
    'procmine-desktop-agent.exe',
    'WindowsTerminal',
    'WindowsTerminal.exe',
    'OpenWith',
    'OpenWith.exe',
    'Microsoft Teams',
    'ms-teams.exe',
    'Explorer',
    'explorer.exe'
}

class Event:
    __slots__ = ('ts_ms', 'ts_iso', 'event_type', 'layer', 'app_name', 'window_title', 'url', 'tab_title', 'raw_text')

    def __init__(self, d: Dict[str, Any]):
        self.ts_ms = d.get('timestamp_ms', 0)
        self.ts_iso = d.get('timestamp_iso', '')
        self.event_type = d.get('event_type', '')
        self.layer = d.get('layer', '')
        
        ctx = d.get('context') or {}
        app = ctx.get('active_app') or {}
        self.app_name = app.get('app_name') or ''
        self.window_title = app.get('window_title') or ''
        
        tab = ctx.get('active_browser_tab') or {}
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

        self.duration_sec = max(1.0, (end_ms - start_ms) / 1000.0)
        
        # Primary identifiers
        apps = [e.app_name for e in events if e.app_name and e.app_name not in SYSTEM_NOISE_APPS]
        self.primary_app = max(set(apps), key=apps.count) if apps else "Desktop"
        
        urls = [e.url for e in events if e.url and not e.url.endswith('/dashboard') and not e.url.endswith('/#/dashboard')]
        self.primary_url = max(set(urls), key=urls.count) if urls else ""
        
        titles = [self.clean_title(e.window_title) for e in events if e.window_title and e.app_name not in SYSTEM_NOISE_APPS]
        clean_titles = [t for t in titles if t and t not in ['Dashboard', 'New Tab']]
        self.primary_title = max(set(clean_titles), key=clean_titles.count) if clean_titles else ""

    @staticmethod
    def clean_title(title: str) -> str:
        if not title:
            return ""
        # Strip browser suffixes including Profile and zero-width spaces
        t = re.sub(r' - (?:Google Chrome|Microsoft.? Edge|Word|Excel|Notepad|Windows PowerShell).*', '', title)
        t = re.sub(r' and \d+ more page.*', '', t)
        t = re.sub(r' - Profile \d+.*', '', t)
        t = re.sub(r'  -  Compatibility Mode.*', '', t)
        t = re.sub(r' \[Compatibility Mode\].*', '', t)
        return t.strip()

    def get_text_signature(self) -> str:
        tokens = []
        if self.primary_url:
            m = re.search(r'#/([a-zA-Z0-9\-_]+)', self.primary_url)
            if m:
                tokens.append(m.group(1).replace('-', '_'))
        
        if self.primary_title:
            tokens.append(self.primary_title)

        if self.primary_app:
            tokens.append(self.primary_app)

        return " ".join(tokens)

class HybridSegmenter:
    def __init__(self, idle_gap_sec: float = 22.0, min_segment_sec: float = 8.0):
        self.idle_gap_ms = int(idle_gap_sec * 1000)
        self.min_segment_ms = int(min_segment_sec * 1000)

    def _extract_url_route(self, url: str) -> str:
        if not url:
            return ""
        m = re.search(r'#(/[a-zA-Z0-9\-_]+)', url)
        if m:
            route = m.group(1)
            # Treat dashboard as neutral / transit
            return route if route != '/dashboard' else ""
        return ""

    def _get_context_key(self, event: Event) -> str:
        """Derives the semantic operational context of an event."""
        if event.app_name in SYSTEM_NOISE_APPS:
            return "system_noise"

        route = self._extract_url_route(event.url)
        if route:
            return f"route:{route}"

        # Word Document context
        if "Word" in event.app_name:
            doc = Segment.clean_title(event.window_title)
            if doc:
                return f"doc:{doc}"

        # Excel Analysis context (e.g. budget_analysis, expense_calc)
        if "Excel" in event.app_name:
            sheet = Segment.clean_title(event.window_title)
            if sheet and sheet not in ['m1_reference']:
                return f"excel:{sheet}"

        # Legacy desktop systems (受発注在庫管理システム, 財務会計システム, HR人事給与システム)
        title = Segment.clean_title(event.window_title)
        if any(sys in title for sys in ['受発注在庫管理システム', '財務会計システム', 'HR人事給与システム']):
            for sys in ['受発注在庫管理システム', '財務会計システム', 'HR人事給与システム']:
                if sys in title:
                    return f"portal:{sys}"

        return ""

    def segment_events(self, session_id: str, events: List[Event]) -> List[Segment]:
        if not events:
            return []

        # Sort events by timestamp_ms
        events.sort(key=lambda x: x.ts_ms)

        # Filter initial and trailing pure noise events
        filtered_events = [e for e in events if e.app_name not in SYSTEM_NOISE_APPS or e.layer != 'SYSTEM']
        if not filtered_events:
            return []

        cut_points = [0]
        last_context = ""

        for i in range(1, len(filtered_events)):
            curr = filtered_events[i]
            prev = filtered_events[i - 1]
            time_diff = curr.ts_ms - prev.ts_ms
            
            is_boundary = False

            # Signal 1: Significant idle time (inactivity pause between cases)
            if time_diff >= self.idle_gap_ms:
                is_boundary = True

            # Signal 2: Distinct business context change
            curr_ctx = self._get_context_key(curr)
            if curr_ctx and curr_ctx != "system_noise":
                if last_context and curr_ctx != last_context:
                    is_boundary = True
                last_context = curr_ctx

            if is_boundary:
                seg_start_idx = cut_points[-1]
                duration = filtered_events[i - 1].ts_ms - filtered_events[seg_start_idx].ts_ms
                if duration >= self.min_segment_ms:
                    cut_points.append(i)

        cut_points.append(len(filtered_events))

        # Build raw segments
        raw_segments = []
        for j in range(len(cut_points) - 1):
            s_idx = cut_points[j]
            e_idx = cut_points[j + 1]
            seg_evs = filtered_events[s_idx:e_idx]
            if not seg_evs:
                continue

            # Check if this segment is purely system noise (e.g. only procmine agent or powershell)
            non_noise_events = [e for e in seg_evs if e.app_name not in SYSTEM_NOISE_APPS]
            if not non_noise_events and len(raw_segments) > 0:
                # Ignore standalone noise segment (like agent startup)
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

        # Merge transient / micro-segments into previous
        merged = []
        for seg in raw_segments:
            if not merged:
                merged.append(seg)
                continue

            if seg.duration_sec < (self.min_segment_ms / 1000.0) or not seg.primary_title and not seg.primary_url:
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
