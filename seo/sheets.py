import json
import os
import logging
from datetime import datetime
import gspread
from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEETS_SPREADSHEET_ID,
    SHEET_NAMES,
)
import governance

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = {
    "seo_runs": ["run_id", "date", "skill_id", "skill_name", "score", "issues_found",
                 "issues_critical", "duration_s", "status", "notes"],
    "seo_issues": ["issue_id", "first_seen", "last_seen", "skill_id", "severity",
                   "category", "url", "title", "description", "status", "occurrences"],
    "seo_scores": ["date", "skill_id", "skill_name", "score", "prev_score", "delta",
                   "cycle", "run_id"],
    "seo_reports": ["report_id", "date", "skill_id", "type", "title", "summary",
                    "file_path", "run_id"],
    "seo_incidents": ["incident_id", "date", "severity", "category", "title",
                      "description", "status", "resolved_date", "run_id"],
    "seo_ai_visibility": ["date", "title", "severity", "score", "description", "run_id"],
    "seo_competitors": ["date", "benchmark", "finding", "severity", "our_score",
                        "gap", "recommendation", "run_id"],
    "seo_cwv": ["date", "url", "metric", "value", "rating", "device", "run_id"],
    "seo_emails": ["date", "to", "subject", "status", "error", "run_id"],
    "seo_runtime_logs": ["timestamp", "run_id", "level", "skill_id", "message"],
}


class SheetsClient:
    def __init__(self):
        self._gc = None
        self._spreadsheet = None
        self._available = False
        self._init()

    def _init(self):
        if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_SHEETS_SPREADSHEET_ID:
            log.warning("Google Sheets credentials not configured — persistence disabled")
            return
        try:
            creds_data = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            self._gc = gspread.service_account_from_dict(creds_data, scopes=SCOPES)
            self._spreadsheet = self._gc.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
            self._available = True
            log.info("Google Sheets connected: %s", GOOGLE_SHEETS_SPREADSHEET_ID)
        except Exception as e:
            log.error("Google Sheets init failed: %s", e)

    @property
    def available(self):
        return self._available

    def _get_or_create_sheet(self, name: str) -> gspread.Worksheet:
        try:
            return self._spreadsheet.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            ws = self._spreadsheet.add_worksheet(title=name, rows=5000, cols=20)
            headers = SHEET_HEADERS.get(name, [])
            if headers:
                ws.append_row(headers)
            return ws

    def initialize_all_sheets(self):
        if not self._available:
            return False
        for name in SHEET_NAMES:
            self._get_or_create_sheet(name)
            log.info("Sheet initialized: %s", name)
        return True

    def append(self, sheet_name: str, row: list) -> bool:
        # Hard Stop 5: guard every write — only append operations reach this method
        governance.enforce_append_only(sheet_name, "append")
        if not self._available:
            return False
        try:
            ws = self._get_or_create_sheet(sheet_name)
            ws.append_row(row, value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            log.error("Sheets append error [%s]: %s", sheet_name, e)
            return False

    def clear_sheet(self, sheet_name: str) -> bool:
        """Clear a non-history sheet (e.g. seo_reports). Blocked on append-only sheets."""
        governance.enforce_append_only(sheet_name, "clear")
        if not self._available:
            return False
        try:
            ws = self._get_or_create_sheet(sheet_name)
            ws.clear()
            return True
        except Exception as e:
            log.error("Sheets clear error [%s]: %s", sheet_name, e)
            return False

    def get_all_records(self, sheet_name: str) -> list[dict]:
        if not self._available:
            return []
        try:
            ws = self._get_or_create_sheet(sheet_name)
            return ws.get_all_records()
        except Exception as e:
            log.error("Sheets read error [%s]: %s", sheet_name, e)
            return []

    def get_last_run(self) -> dict | None:
        records = self.get_all_records("seo_runs")
        return records[-1] if records else None

    def get_issue_by_id(self, issue_id: str) -> dict | None:
        records = self.get_all_records("seo_issues")
        for r in records:
            if r.get("issue_id") == issue_id:
                return r
        return None

    def update_issue_status(self, issue_id: str, status: str):
        if not self._available:
            return
        try:
            ws = self._get_or_create_sheet("seo_issues")
            records = ws.get_all_values()
            headers = records[0] if records else []
            id_col = headers.index("issue_id") + 1 if "issue_id" in headers else None
            status_col = headers.index("status") + 1 if "status" in headers else None
            last_seen_col = headers.index("last_seen") + 1 if "last_seen" in headers else None
            if not id_col or not status_col:
                return
            for i, row in enumerate(records[1:], start=2):
                if len(row) >= id_col and row[id_col - 1] == issue_id:
                    ws.update_cell(i, status_col, status)
                    if last_seen_col:
                        ws.update_cell(i, last_seen_col, datetime.utcnow().isoformat())
                    return
        except Exception as e:
            log.error("Issue update error: %s", e)

    def log_runtime(self, run_id: str, level: str, message: str, skill_id: int = 0):
        self.append("seo_runtime_logs", [
            datetime.utcnow().isoformat(),
            run_id,
            level,
            skill_id,
            message[:500],
        ])
