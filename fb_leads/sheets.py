"""Google Sheets output via a service account."""

from __future__ import annotations

import json
import os

import gspread

from .leads import LEAD_COLUMNS, page_key


def _client() -> gspread.Client:
    creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not creds:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    if creds.startswith("{"):
        return gspread.service_account_from_dict(json.loads(creds))
    return gspread.service_account(filename=creds)


def open_worksheet(sheet_id: str, tab: str) -> gspread.Worksheet:
    spreadsheet = _client().open_by_key(sheet_id)
    try:
        ws = spreadsheet.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab, rows=1000, cols=len(LEAD_COLUMNS))
    if not ws.row_values(1):
        ws.append_row(LEAD_COLUMNS)
    return ws


def existing_keys(ws: gspread.Worksheet) -> set[str]:
    """Facebook URLs already in the sheet, so re-runs don't add duplicates."""
    header = ws.row_values(1)
    if "facebook_url" not in header:
        return set()
    col = ws.col_values(header.index("facebook_url") + 1)[1:]
    return {page_key(u) for u in col if u}


def append_leads(ws: gspread.Worksheet, leads: list[dict]) -> int:
    if not leads:
        return 0
    header = ws.row_values(1) or LEAD_COLUMNS
    rows = [[lead.get(col, "") for col in header] for lead in leads]
    ws.append_rows(rows, value_input_option="RAW")
    return len(rows)
