import re
import sys
import os
sys.path.insert(0, r".")
from typing import List, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from src.segmenter import Segment

class SegmentClusterer:
    def __init__(self, distance_threshold: float = 0.55):
        self.distance_threshold = distance_threshold
        # Tokenizer supporting both English routes and Japanese words/kanji
        self.vectorizer = TfidfVectorizer(
            analyzer='word',
            token_pattern=r'(?u)[a-zA-Z0-9_\-\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+',
            ngram_range=(1, 2),
            min_df=1
        )

    def _generate_canonical_label(self, cluster_segments: List[Segment]) -> str:
        """Derives a human-readable, consistent business process label for the cluster."""
        # Check URLs first
        urls = [s.primary_url for s in cluster_segments if s.primary_url]
        if urls:
            most_common_url = max(set(urls), key=urls.count)
            m = re.search(r'#/([a-zA-Z0-9\-_]+)', most_common_url)
            if m:
                return m.group(1).replace('-', '_')

        # Check document titles
        titles = [s.primary_title for s in cluster_segments if s.primary_title]
        if titles:
            most_common_title = max(set(titles), key=titles.count)
            # Remove generic app suffixes
            cleaned = re.sub(r' - (?:Google Chrome|Microsoft.? Edge|Word|Excel|Notepad|Windows PowerShell).*', '', most_common_title)
            cleaned = re.sub(r' and \d+ more page.*', '', cleaned)
            cleaned = re.sub(r' \[Compatibility Mode\]', '', cleaned)
            cleaned = cleaned.strip()
            if cleaned:
                # sanitize for clean label identifier
                sanitized = re.sub(r'[^\w\-]', '_', cleaned).strip('_')
                return sanitized.lower() if sanitized else "general_task"

        # Check primary app
        apps = [s.primary_app for s in cluster_segments if s.primary_app]
        if apps:
            app_name = max(set(apps), key=apps.count)
            return f"task_{app_name.lower().replace(' ', '_')}"

        return "unknown_process"

    def fit_predict(self, segments: List[Segment]) -> List[Segment]:
        if not segments:
            return []

        if len(segments) == 1:
            segments[0].label = self._generate_canonical_label(segments)
            return segments

        # Build corpus of text signatures
        corpus = [s.get_text_signature() for s in segments]
        
        # Replace empty strings with a default placeholder
        corpus = [c if c.strip() else "general_desktop_action" for c in corpus]

        X = self.vectorizer.fit_transform(corpus).toarray()

        # Fit Agglomerative Clustering with cosine metric
        clustering = AgglomerativeClustering(
            metric='cosine',
            linkage='average',
            distance_threshold=self.distance_threshold,
            n_clusters=None
        )
        
        labels = clustering.fit_predict(X)

        # Group segments by cluster label
        clusters: Dict[int, List[Segment]] = {}
        for seg, cid in zip(segments, labels):
            clusters.setdefault(cid, []).append(seg)

        # Assign canonical label to each cluster
        cluster_names = {}
        for cid, cluster_segs in clusters.items():
            canonical = self._generate_canonical_label(cluster_segs)
            cluster_names[cid] = canonical

        # Assign to segments
        for seg, cid in zip(segments, labels):
            seg.label = cluster_names[cid]

        return segments
