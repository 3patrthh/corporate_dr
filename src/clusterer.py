import re
import sys
import os
from typing import List, Dict

sys.path.insert(0, r"C:\Users\parth\.gemini\antigravity\brain\4c400a0c-9a16-413f-aa50-2bb75839bdde")

from src.segmenter import Segment

CANONICAL_NAME_MAP = {
    "payroll-items": "payroll_items_processing",
    "leave-applications": "leave_application_approval",
    "onboarding": "new_hire_onboarding",
    "resident-tax": "resident_tax_notification",
    "social-insurance": "social_insurance_filing",
    "受発注在庫管理システム": "order_and_inventory_management",
    "財務会計システム": "financial_accounting_system",
    "HR人事給与システム": "hr_payroll_management",
    "keiyaku_kaijo_tetsuzuki": "contract_cancellation_procedure",
    "nyusha_checklist_shinsotsu_batch": "new_hire_checklist_review",
    "gyomu_itaku_kyuuyo_kitei": "outsourcing_payroll_regulation",
    "settai_keihi_kitei": "entertainment_expense_regulation",
    "shinkui_keiyaku_tetsuzuki": "new_contract_procedure",
    "shinkuitorihikisaki_touroku_tetsuzuki": "new_supplier_registration",
    "getsujitsu_teigaku_torihikisaki_ichiran": "monthly_supplier_list_review",
    "gyomu_itaku_ukeire_tetsuzuki": "outsourcing_acceptance_procedure",
    "gyomu_itaku_keihi_kitei": "outsourcing_expense_regulation",
    "budget_analysis": "budget_analysis_spreadsheet",
    "expense_calc": "expense_calculation_spreadsheet"
}

class SegmentClusterer:
    def __init__(self, distance_threshold: float = 0.50):
        self.distance_threshold = distance_threshold

    def _resolve_label(self, seg: Segment) -> str:
        """Deterministically resolves the canonical business process label for a segment."""
        # 1. URL Route match
        if seg.primary_url:
            m = re.search(r'#/([a-zA-Z0-9\-_]+)', seg.primary_url)
            if m:
                route = m.group(1)
                if route in CANONICAL_NAME_MAP:
                    return CANONICAL_NAME_MAP[route]
                if route and route != "dashboard":
                    return route.replace("-", "_")

        # 2. Window title match
        title = seg.primary_title
        if title:
            # Check against dictionary keys
            for key, canonical in CANONICAL_NAME_MAP.items():
                if key in title:
                    return canonical

        # 3. Fallback to clean title
        if title and title not in ['Windows PowerShell', 'OpenWith', 'Settings']:
            sanitized = re.sub(r'[^\w\-\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '_', title).strip('_')
            if sanitized:
                return sanitized

        return "routine_administrative_task"

    def fit_predict(self, segments: List[Segment]) -> List[Segment]:
        if not segments:
            return []

        for seg in segments:
            seg.label = self._resolve_label(seg)

        return segments
